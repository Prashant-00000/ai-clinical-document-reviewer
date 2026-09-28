"""
LLM client abstraction + Google Gemini implementation.

The abstract LLMClient interface lets us swap providers without touching the
rest of the codebase.  GeminiClient uses the google-genai SDK with JSON mode,
timeouts, and clean error handling.
"""
from __future__ import annotations

import abc
import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class LLMClient(abc.ABC):
    """Provider-agnostic LLM interface."""

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str,
        images: list[bytes] | None = None,
        image_mime_types: list[str] | None = None,
    ) -> str:
        """Return free-form text from the model."""
        ...

    @abc.abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        images: list[bytes] | None = None,
        image_mime_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return parsed JSON from the model (uses JSON mode)."""
        ...


# ---------------------------------------------------------------------------
# Gemini implementation
# ---------------------------------------------------------------------------

class GeminiClient(LLMClient):
    """Google Gemini via the google-genai SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.MODEL_NAME
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is required. Set it in .env or as an environment variable."
            )
        # Lazy import so tests that mock this class don't need google-genai
        from google import genai  # type: ignore[import-untyped]

        self._genai = genai
        self._types = genai.types
        self._client = genai.Client(api_key=self.api_key)

    # -- helpers -------------------------------------------------------------

    def _build_contents(
        self,
        prompt: str,
        images: list[bytes] | None = None,
        image_mime_types: list[str] | None = None,
    ) -> list[Any]:
        parts: list[Any] = []
        if images:
            mtypes = image_mime_types or (["image/png"] * len(images))
            for img_bytes, mime in zip(images, mtypes):
                parts.append(
                    self._types.Part.from_bytes(data=img_bytes, mime_type=mime)
                )
        parts.append(prompt)
        return parts

    # -- public API ----------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        images: list[bytes] | None = None,
        image_mime_types: list[str] | None = None,
    ) -> str:
        contents = self._build_contents(prompt, images, image_mime_types)
        last_exc: Exception | None = None
        for attempt in range(1, 6):
            try:
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=self._types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.1,
                    ),
                )
                return response.text or ""
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if ("503" in err_str or "unavailable" in err_str or "resourceexhausted" in err_str or "429" in err_str) and attempt < 5:
                    wait_sec = min(attempt * 2, 8)
                    logger.warning("Transient Gemini error on attempt %d: %s. Retrying in %ds...", attempt, exc, wait_sec)
                    import time
                    time.sleep(wait_sec)
                    continue
                break
        logger.error("Gemini generate() failed after attempts: %s", last_exc)
        raise LLMError(f"LLM request failed: {last_exc}") from last_exc

    def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        images: list[bytes] | None = None,
        image_mime_types: list[str] | None = None,
    ) -> dict[str, Any]:
        contents = self._build_contents(prompt, images, image_mime_types)
        last_exc: Exception | None = None
        for attempt in range(1, 6):
            try:
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=self._types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                raw = (response.text or "{}").strip()
                # Clean optional markdown codeblocks if model returns ```json ... ```
                if raw.startswith("```"):
                    lines = raw.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw = "\n".join(lines).strip()
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                logger.error("LLM returned invalid JSON: %s", exc)
                raise LLMError(f"LLM returned invalid JSON: {exc}") from exc
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if ("503" in err_str or "unavailable" in err_str or "resourceexhausted" in err_str or "429" in err_str) and attempt < 5:
                    wait_sec = min(attempt * 2, 8)
                    logger.warning("Transient Gemini error on attempt %d: %s. Retrying in %ds...", attempt, exc, wait_sec)
                    import time
                    time.sleep(wait_sec)
                    continue
                break
        logger.error("Gemini generate_json() failed after attempts: %s", last_exc)
        raise LLMError(f"LLM request failed: {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Raised when the LLM call fails (network, API, bad JSON, etc.)."""
    pass


# ---------------------------------------------------------------------------
# Dependency helper
# ---------------------------------------------------------------------------

def get_llm_client() -> LLMClient:
    """FastAPI dependency — returns the configured LLM client."""
    return GeminiClient()
