"""
Image upload handling.

Images are stored on disk (in `uploads/`) and only the URL/path is written to
the database — we never store big base64 blobs in MySQL. The same interface can
later be pointed at S3 / Cloudinary / Supabase Storage.

Validation performed here:
  * image type (JPEG / PNG / WEBP / GIF only)
  * file size (max `MAX_IMAGE_BYTES`)
  * unique, sanitised filenames (no user-controlled names → no path traversal)
"""

import base64
import io
import logging
import os
import uuid

import config

log = logging.getLogger("farmbridge.upload")

_FORMAT_EXT = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "GIF": ".gif",
}


def _decode(raw):
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw
    s = str(raw)
    if s.startswith("data:") and "," in s:
        s = s.split(",", 1)[1]
    try:
        return base64.b64decode(s)
    except Exception:
        return None


def save_image(raw):
    """
    Validate and persist an uploaded image.

    Returns (image_url, error_message). `image_url` is the public URL path
    (e.g. `/uploads/<uuid>.jpg`); `error_message` is None on success.
    """
    data = _decode(raw)
    if not data:
        return None, "No image data received"

    if len(data) > config.MAX_IMAGE_BYTES:
        return None, "Image too large (max %d MB)" % (config.MAX_IMAGE_BYTES // (1024 * 1024))

    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "").upper()
        if fmt not in _FORMAT_EXT:
            return None, "Unsupported image type (use JPG/PNG/WEBP/GIF)"
        # Force full decode so truncated/corrupt files are caught.
        img.load()
    except Exception as exc:
        log.warning("Image decode failed: %s", exc)
        return None, "Could not read image file"

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    filename = "%s%s" % (uuid.uuid4().hex, _FORMAT_EXT[fmt])
    path = os.path.join(config.UPLOAD_FOLDER, filename)
    with open(path, "wb") as fh:
        fh.write(data)

    return "/uploads/%s" % filename, None
