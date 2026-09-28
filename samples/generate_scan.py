"""
Generate synthetic scanned documents:
1. clean_note.pdf — searchable text-layer PDF from clean_note.txt
2. scanned_note.png — simulated scanned handwritten document (font, noise, rotation, blur)
3. scanned_note.pdf — image-only PDF with zero text layer (triggers vision fallback)
"""
from __future__ import annotations

import os
import random
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SAMPLES_DIR = Path(__file__).resolve().parent


def generate_clean_note_pdf():
    """Generate a clean PDF with a real text layer using PyMuPDF."""
    txt_path = SAMPLES_DIR / "clean_note.txt"
    pdf_path = SAMPLES_DIR / "clean_note.pdf"

    if not txt_path.exists():
        raise FileNotFoundError(f"Missing {txt_path}")

    text = txt_path.read_text(encoding="utf-8")

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # Standard Letter size

    # PyMuPDF text insertion (creates a real, selectable text layer)
    rect = fitz.Rect(54, 54, 558, 738)
    page.insert_textbox(rect, text, fontsize=10, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()
    print(f"Created {pdf_path} (searchable text layer)")


def find_handwriting_font():
    """Find a handwriting-style font on the system or fall back to default."""
    candidates = [
        r"C:\Windows\Fonts\Inkfree.ttf",
        r"C:\Windows\Fonts\segoepr.ttf",      # Segoe Print
        r"C:\Windows\Fonts\segoesc.ttf",      # Segoe Script
        r"C:\Windows\Fonts\comic.ttf",        # Comic Sans
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, 22)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_scanned_png():
    """Generate scanned_note.png with handwriting font, paper texture, noise, rotation, and blur."""
    png_path = SAMPLES_DIR / "scanned_note.png"

    width, height = 850, 1100
    # Slightly aged off-white paper color
    bg_color = (252, 250, 242)
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    font = find_handwriting_font()
    header_font = find_handwriting_font()

    # Draw subtle ruled lines like a medical chart pad
    line_color = (220, 228, 238)
    for y in range(120, height - 80, 36):
        draw.line([(60, y), (width - 60, y)], fill=line_color, width=1)
    # Red left margin line
    draw.line([(100, 80), (100, height - 80)], fill=(240, 200, 200), width=1)

    lines = [
        "CLINICAL CONSULTATION NOTE (HANDWRITTEN)",
        "Date: 2026-06-18   Time: 14:15",
        "Patient: Maria Garcia, 38 yo female",
        "Chief Complaint: Severe throbbing headache x 48 hours",
        "",
        "HPI: 38 yo F reports acute left-sided throbbing migraine.",
        "Associated with nausea, photophobia, and phonophobia.",
        "Denies fever, neck stiffness, or focal neurological deficits.",
        "",
        "Vitals: BP 118/76 mmHg, HR 80 bpm, Temp 36.9 C, RR 16, SpO2 99%",
        "Allergies: Sulfa drugs (triggers skin rash)",
        "",
        "Current Meds: Sumatriptan 50mg PO as needed",
        "Exam: Alert, oriented x 4, photophobic. Cranial nerves intact.",
        "Impression: Acute migraine without aura",
        "",
        "Plan:",
        "1. Sumatriptan 50mg PO at onset of symptoms",
        "2. Rest in quiet, dark environment; hydration",
        "3. Follow up with neurology if episodes exceed 3x / month",
    ]

    # Pen ink: dark navy / black ballpoint
    ink_color = (28, 38, 68)

    y_cursor = 100
    for line in lines:
        if line:
            # Slight jitter in line placement for realistic handwriting
            jitter_x = random.randint(-2, 2)
            draw.text((120 + jitter_x, y_cursor), line, fill=ink_color, font=font)
        y_cursor += 36

    # 1. Add paper grain / scanner noise
    pixels = img.load()
    for _ in range(25000):
        nx = random.randint(0, width - 1)
        ny = random.randint(0, height - 1)
        noise_val = random.randint(-20, 20)
        r, g, b = pixels[nx, ny]
        pixels[nx, ny] = (
            max(0, min(255, r + noise_val)),
            max(0, min(255, g + noise_val)),
            max(0, min(255, b + noise_val)),
        )

    # 2. Slight rotation (skew typical of flatbed scanner feed)
    angle = -1.2
    rotated = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=bg_color)

    # 3. Slight lens/scan blur
    scanned = rotated.filter(ImageFilter.GaussianBlur(radius=0.55))

    scanned.save(str(png_path), "PNG")
    print(f"Created {png_path} (scanned handwriting simulation)")
    return png_path


def generate_scanned_pdf(png_path: Path):
    """Generate scanned_note.pdf — pure image PDF with zero text layer."""
    pdf_path = SAMPLES_DIR / "scanned_note.pdf"

    doc = fitz.open()
    with Image.open(png_path) as img:
        img_width, img_height = img.size

    # 72 points per inch standard PDF coordinates
    page = doc.new_page(width=img_width * 72 / 96, height=img_height * 72 / 96)
    rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
    page.insert_image(rect, filename=str(png_path))
    doc.save(str(pdf_path))
    doc.close()
    print(f"Created {pdf_path} (image-only, no text layer)")


if __name__ == "__main__":
    generate_clean_note_pdf()
    png_file = generate_scanned_png()
    generate_scanned_pdf(png_file)
