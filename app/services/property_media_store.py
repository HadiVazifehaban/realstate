"""Media upload storage for the node's own photo/video vault.

The ingestion pipeline stores crawled photos as absolute CDN URLs in
``property_media.cloud_url``; anything an advisor uploads from the submit form
is different -- it is a file on the office machine, under
``settings.media_dir/<property_id>/`` -- and the browser reaches it through
``GET /api/v1/properties/media/file/{media_id}``, which streams the bytes back
with the stored MIME type.

Kept deliberately small: no transcoding, no thumbnails, no S3. A file lands,
its row lands, the gallery shows it. The LAN is the network; the office machine
is the storage.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import get_settings

# What the form accepts, mirroring the HTML `accept` hint. Anything else is
# refused here rather than landing in the vault as an unplayable file.
IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif"
}
VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm"
}

# A walkthrough shot on a phone runs to ~80 MB; a photo is a few MB. Both
# ceilings are per file, and the count is capped per request, so one submit
# cannot fill the node's disk.
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_VIDEO_BYTES = 200 * 1024 * 1024
MAX_FILES_PER_REQUEST = 20


class UnsupportedMediaError(ValueError):
    """Raised for a MIME type the vault refuses to store."""


def classify(content_type: str) -> tuple[str, str]:
    """Map a MIME type to ``(media_type, extension)``.

    ``media_type`` is the ``MediaType`` enum *value* (``IMAGE``/``VIDEO``), and
    the extension is the canonical one for that type -- not the client's, which
    is how a ``.png`` that is really a JPEG would otherwise land in the vault.
    """
    normalised = (content_type or "").split(";")[0].strip().lower()
    if normalised in IMAGE_TYPES:
        return "IMAGE", IMAGE_TYPES[normalised]
    if normalised in VIDEO_TYPES:
        return "VIDEO", VIDEO_TYPES[normalised]
    raise UnsupportedMediaError(
        f"فرمت پشتیبانی نمی‌شود: {content_type or 'نامشخص'}. "
        "عکس (JPEG/PNG/WebP/GIF/AVIF) یا ویدیو (MP4/MOV/WebM) بفرستید."
    )


def max_bytes_for(media_type: str) -> int:
    return MAX_VIDEO_BYTES if media_type == "VIDEO" else MAX_IMAGE_BYTES


def property_dir(property_id: uuid.UUID) -> Path:
    """This property's folder, created on demand."""
    settings = get_settings()
    directory = settings.resolve_path(settings.media_dir) / str(property_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def store(property_id: uuid.UUID, content: bytes, extension: str) -> tuple[Path, str]:
    """Write one file and return ``(path, stored name)``.

    The stored name is opaque: the original filename goes in the database row,
    and keeping it out of the path means a Persian filename with a slash or a
    space can never break the URL that serves it.
    """
    stored_name = f"{uuid.uuid4().hex}{extension}"
    path = property_dir(property_id) / stored_name
    path.write_bytes(content)
    return path, stored_name


def resolve_stored(local_path: str | None) -> Path | None:
    """The file behind a row, or ``None`` when it is gone from disk."""
    if not local_path:
        return None
    try:
        path = Path(local_path)
    except (TypeError, ValueError):
        return None
    return path if path.is_file() else None
