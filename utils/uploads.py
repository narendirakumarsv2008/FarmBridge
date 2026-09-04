"""Image upload helper (backward-compatible wrapper).

New code should use services.storage_service directly. This module keeps the
old `save_base64_image` interface so existing routes/tests stay unchanged.
"""

from services.storage_service import save_image


def save_base64_image(photo):
    """Save a data-URL/base64 image via the active storage provider.

    Returns (ok, image_url, image_path, error_message).
    """
    return save_image(photo)
