"""Image upload validation and local storage.

Development stores uploaded images locally under UPLOAD_FOLDER and stores the
relative URL in the database. The same interface is designed so a future S3 /
Cloudinary / Supabase Storage provider can be dropped in without changing
route handlers.
"""

import base64
import os
import re
import uuid
from io import BytesIO

from PIL import Image

from config import config

_EXT_MAP = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/gif': 'gif',
}


def _data_url_parts(photo):
    if not photo:
        return None, None
    match = re.match(r'^data:([^;]+);base64,(.*)$', photo, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None, photo


def save_base64_image(photo):
    """Store a data-URL/base64 image locally.

    Returns (ok, image_url, image_path, error_message).
    photo may already be a URL/path, in which case it is returned unchanged.
    """
    if not photo:
        return True, None, None, None

    mime, raw = _data_url_parts(photo)
    if mime and mime not in config.ALLOWED_IMAGE_TYPES:
        return False, None, None, 'Unsupported image type. Use JPG, PNG, WEBP or GIF.'
    if not raw:
        # Already a URL or file path supplied by a future storage provider.
        return True, photo, None, None

    try:
        data = base64.b64decode(raw)
    except Exception:
        return False, None, None, 'Invalid image data'
    if len(data) > config.MAX_UPLOAD_BYTES:
        return False, None, None, 'Image too large. Max %d MB.' % config.MAX_UPLOAD_SIZE_MB

    ext = _EXT_MAP.get(mime, 'jpg')
    try:
        img = Image.open(BytesIO(data))
        img.verify()
    except Exception:
        return False, None, None, 'Image file is corrupted or not a valid image'

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    filename = '%s.%s' % (uuid.uuid4().hex, ext)
    path = os.path.join(config.UPLOAD_FOLDER, filename)
    with open(path, 'wb') as f:
        f.write(data)
    relative = '/uploads/%s' % filename
    return True, relative, path, None
