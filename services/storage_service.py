"""
Storage service abstraction.

LocalStorageProvider is the default and is suitable for local development and
single-instance demos. Render's filesystem is ephemeral, so local uploads may
be lost on redeploy. Optional CloudinaryProvider can be enabled with
STORAGE_PROVIDER=cloudinary and the CLOUDINARY_* credentials. The app still
works locally when Cloudinary is not configured.
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


def _validate_and_decode(photo):
    """Return (is_valid, mime, raw_bytes, error_message)."""
    if not photo:
        return True, None, b'', None
    mime, raw = _data_url_parts(photo)
    if mime and mime not in config.ALLOWED_IMAGE_TYPES:
        return False, None, None, 'Unsupported image type. Use JPG, PNG, WEBP or GIF.'
    if not raw:
        # Already an external URL/path.
        return True, mime, None, None
    try:
        data = base64.b64decode(raw)
    except Exception:
        return False, None, None, 'Invalid image data'
    if len(data) > config.MAX_UPLOAD_BYTES:
        return False, None, None, 'Image too large. Max %d MB.' % config.MAX_UPLOAD_SIZE_MB
    try:
        Image.open(BytesIO(data)).verify()
    except Exception:
        return False, None, None, 'Image file is corrupted or not a valid image'
    return True, mime, data, None


class StorageProvider:
    name = 'base'

    def save_image(self, photo):
        raise NotImplementedError

    def delete_image(self, url):
        return True

    def get_image_url(self, url):
        return url


class LocalStorageProvider(StorageProvider):
    name = 'local'

    def save_image(self, photo):
        ok, mime, raw, err = _validate_and_decode(photo)
        if not ok:
            return False, None, None, err
        if raw is None:
            # Already an external URL/path.
            return True, photo, None, None
        os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
        ext = _EXT_MAP.get(mime, 'jpg')
        filename = '%s.%s' % (uuid.uuid4().hex, ext)
        path = os.path.join(config.UPLOAD_FOLDER, filename)
        with open(path, 'wb') as f:
            f.write(raw)
        return True, '/uploads/%s' % filename, path, None

    def delete_image(self, url):
        if not url or not url.startswith('/uploads/'):
            return True
        name = os.path.basename(url)
        path = os.path.join(config.UPLOAD_FOLDER, name)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        return True


class CloudinaryProvider(StorageProvider):
    name = 'cloudinary'

    def __init__(self):
        if not (config.CLOUDINARY_CLOUD_NAME
                and config.CLOUDINARY_API_KEY
                and config.CLOUDINARY_API_SECRET):
            raise ValueError('Cloudinary credentials are not configured')

    def save_image(self, photo):
        import cloudinary
        import cloudinary.uploader
        from cloudinary.utils import cloudinary_url

        ok, mime, raw, err = _validate_and_decode(photo)
        if not ok:
            return False, None, None, err
        if raw is None:
            return True, photo, None, None
        ext = _EXT_MAP.get(mime, 'jpg')
        # cloudinary.uploader can accept a byte file-like object.
        public_id = 'farmbridge/%s' % uuid.uuid4().hex
        result = cloudinary.uploader.upload(
            BytesIO(raw),
            public_id=public_id,
            resource_type='image',
            format=ext,
        )
        url = result.get('secure_url')
        return True, url, None, None

    def delete_image(self, url):
        if not url:
            return True
        try:
            import cloudinary.api
            public_id = url.split('/')[-1].split('.')[0]
            cloudinary.api.delete_resources([public_id], resource_type='image')
        except Exception:
            pass
        return True


def get_storage_provider():
    if config.STORAGE_PROVIDER == 'cloudinary':
        try:
            import cloudinary
            cloudinary.config(
                cloud_name=config.CLOUDINARY_CLOUD_NAME,
                api_key=config.CLOUDINARY_API_KEY,
                api_secret=config.CLOUDINARY_API_SECRET,
                secure=True,
            )
            return CloudinaryProvider()
        except Exception as e:
            print('[storage] Cloudinary not available (%s); falling back to local' % e)
    return LocalStorageProvider()


# Resolve lazily on first use so env/setting overrides apply after import.
_provider = None


def storage_provider():
    global _provider
    if _provider is None:
        _provider = get_storage_provider()
    return _provider


def save_image(photo):
    return storage_provider().save_image(photo)


def delete_image(url):
    return storage_provider().delete_image(url)
