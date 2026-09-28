"""
Document processor — handles text, PDF, and image inputs.

Responsibilities:
  • Magic-byte verification (not just extension).
  • PDF text extraction via pdfplumber, with scanned-PDF fallback
    (PyMuPDF page→image → vision model transcription).
  • Image transcription via the vision model.
  • Corrupt / unreadable file detection.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field

import fitz  # PyMuPDF
from PIL import Image

from app.core.config import settings
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS: set[str] = {"pdf", "png", "jpg", "jpeg", "webp"}
IMAGE_EXTENSIONS: set[str] = {"png", "jpg", "jpeg", "webp"}

MAGIC_BYTES: dict[str, bytes] = {
    "pdf": b"%PDF",
    "png": b"\x89PNG",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "webp": b"RIFF",
}

MIME_MAP: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "pdf": "application/pdf",
}

# Minimum chars to consider a PDF as having "real" extracted text
_PDF_TEXT_THRESHOLD = 50

# ---------------------------------------------------------------------------
# Transcription prompts for vision model
# ---------------------------------------------------------------------------

TRANSCRIPTION_SYSTEM_PROMPT = (
    "You are a clinical document transcription specialist. "
    "Faithfully transcribe all text from the provided clinical document image(s)."
)

TRANSCRIPTION_PROMPT = (
    "Transcribe ALL text visible in this clinical document image(s) faithfully and completely.\n\n"
    "Rules:\n"
    "1. Transcribe exactly what you see — do not paraphrase or summarise.\n"
    "2. Preserve the original structure (headings, lists, sections).\n"
    "3. For any text that is unclear or illegible, mark it as [illegible] "
    "or [partially illegible: best guess].\n"
    "4. NEVER guess or invent text you cannot read.\n"
    "5. If handwritten, note [handwritten] at the start.\n"
    "6. Preserve medical abbreviations as written.\n"
    "7. If multiple pages, separate with --- Page Break ---."
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProcessedDocument:
    """Result of document processing."""
    text: str
    images: list[bytes] | None = None
    image_mime_types: list[str] | None = None
    input_type: str = "text"  # text | pdf | pdf_scanned | image
    quality_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_extension(filename: str) -> str:
    """Extract lowercase extension from a filename."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def verify_magic_bytes(file_bytes: bytes, extension: str) -> bool:
    """Return True if the file's leading bytes match the expected signature."""
    expected = MAGIC_BYTES.get(extension)
    if expected is None:
        return False
    if extension == "webp":
        return (
            len(file_bytes) >= 12
            and file_bytes[:4] == b"RIFF"
            and file_bytes[8:12] == b"WEBP"
        )
    return file_bytes[: len(expected)] == expected


def validate_file(file_bytes: bytes, filename: str) -> str:
    """Validate a file upload.  Returns the normalised extension or raises."""
    ext = get_extension(filename)

    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '.{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if len(file_bytes) > settings.max_upload_bytes:
        raise FileTooLargeError(
            f"File size ({len(file_bytes) / 1_048_576:.1f} MB) exceeds "
            f"the {settings.MAX_UPLOAD_MB} MB limit."
        )

    if not verify_magic_bytes(file_bytes, ext):
        raise InvalidFileError(
            f"File content does not match the expected format for '.{ext}'. "
            "The file may be corrupted or mislabelled."
        )

    return ext


# ---------------------------------------------------------------------------
# PDF processing
# ---------------------------------------------------------------------------

def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract selectable text from a PDF using PyMuPDF."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        logger.warning("PyMuPDF text extraction failed: %s", exc)
        return ""

    parts = [page.get_text() for page in doc[: settings.MAX_PDF_PAGES]]
    doc.close()
    return "\n\n".join(parts).strip()


def _pdf_to_images(file_bytes: bytes) -> list[tuple[bytes, str]]:
    """Convert PDF pages to PNG images using PyMuPDF."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise InvalidFileError(f"Cannot open PDF: {exc}") from exc

    images: list[tuple[bytes, str]] = []
    for i, page in enumerate(doc):
        if i >= settings.MAX_PDF_PAGES:
            break
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        images.append((pix.tobytes("png"), "image/png"))
    doc.close()
    return images


def _process_pdf(file_bytes: bytes, llm_client: LLMClient) -> ProcessedDocument:
    """Process a PDF — try text extraction, fall back to vision for scanned PDFs."""
    text = _extract_pdf_text(file_bytes)
    quality_notes: list[str] = []

    if len(text) >= _PDF_TEXT_THRESHOLD:
        return ProcessedDocument(text=text, input_type="pdf", quality_notes=quality_notes)

    # Scanned / image-based PDF → convert to images, transcribe via vision
    quality_notes.append("PDF appears to be scanned; used vision model for text extraction.")
    logger.info("PDF text extraction yielded < %d chars — falling back to vision.", _PDF_TEXT_THRESHOLD)

    page_images = _pdf_to_images(file_bytes)
    if not page_images:
        raise InvalidFileError("Could not extract any pages from the PDF.")

    img_bytes_list = [b for b, _ in page_images]
    mime_list = [m for _, m in page_images]

    transcription = llm_client.generate(
        prompt=TRANSCRIPTION_PROMPT,
        system_prompt=TRANSCRIPTION_SYSTEM_PROMPT,
        images=img_bytes_list,
        image_mime_types=mime_list,
    )

    if not transcription.strip():
        raise InvalidFileError("Vision model could not extract any text from the scanned PDF.")

    return ProcessedDocument(
        text=transcription,
        images=img_bytes_list,
        image_mime_types=mime_list,
        input_type="pdf",
        quality_notes=quality_notes,
    )


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------

def _process_image(file_bytes: bytes, ext: str, llm_client: LLMClient) -> ProcessedDocument:
    """Transcribe an image via the vision model."""
    # Validate the image can actually be opened
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
    except Exception as exc:
        raise InvalidFileError(f"Invalid or corrupted image file: {exc}") from exc

    mime = MIME_MAP.get(ext, "image/png")
    quality_notes = ["Text extracted from image via vision model."]

    transcription = llm_client.generate(
        prompt=TRANSCRIPTION_PROMPT,
        system_prompt=TRANSCRIPTION_SYSTEM_PROMPT,
        images=[file_bytes],
        image_mime_types=[mime],
    )

    if not transcription.strip():
        raise InvalidFileError("Vision model could not extract any text from the image.")

    return ProcessedDocument(
        text=transcription,
        images=[file_bytes],
        image_mime_types=[mime],
        input_type="image",
        quality_notes=quality_notes,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def process_document(
    text: str | None,
    file_bytes: bytes | None,
    filename: str | None,
    llm_client: LLMClient,
) -> ProcessedDocument:
    """Route input to the appropriate processor.

    Exactly one of *text* or *file_bytes* should be provided (caller validates).
    """
    if text and not file_bytes:
        return ProcessedDocument(text=text.strip(), input_type="text")

    if not file_bytes or not filename:
        raise ValueError("file_bytes and filename are required for file processing.")

    ext = validate_file(file_bytes, filename)

    if ext == "pdf":
        return _process_pdf(file_bytes, llm_client)

    if ext in IMAGE_EXTENSIONS:
        return _process_image(file_bytes, ext, llm_client)

    # Should never reach here after validate_file, but be safe.
    raise UnsupportedFileTypeError(f"No processor for extension '.{ext}'.")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class UnsupportedFileTypeError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


class TextTooLongError(Exception):
    pass


class InvalidFileError(Exception):
    pass
