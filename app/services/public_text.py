"""Server-side public-copy sanitizer and versioning helper."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser


_PHONE = re.compile(r"(?<!\d)(?:(?:\+|00)98|0)?9\d{9}(?!\d)")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_COORDINATES = re.compile(r"(?<!\d)\d{1,3}\.\d{3,}\s*[,،]\s*\d{1,3}\.\d{3,}(?!\d)")
_ADDRESS = re.compile(r"(?im)(?:آدرس|address|نشانی)\s*[:：].*(?:$|\n)")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._blocked = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag.lower() in {"script", "style", "iframe", "object", "embed"}:
            self._blocked += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "iframe", "object", "embed"} and self._blocked:
            self._blocked -= 1

    def handle_data(self, data: str) -> None:
        if not self._blocked:
            self.parts.append(data)


@dataclass(frozen=True)
class SanitizedPublicText:
    text: str
    version_hash: str


def sanitize_public_text(value: str, *, max_length: int = 2000) -> SanitizedPublicText | None:
    parser = _TextExtractor()
    parser.feed(value or "")
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    text = _PHONE.sub("[اطلاعات تماس حذف شد]", text)
    text = _EMAIL.sub("[اطلاعات تماس حذف شد]", text)
    text = _COORDINATES.sub("[موقعیت دقیق حذف شد]", text)
    text = _ADDRESS.sub("[آدرس دقیق حذف شد]", text)
    text = text[:max_length].strip()
    if not text:
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SanitizedPublicText(text=text, version_hash=digest)
