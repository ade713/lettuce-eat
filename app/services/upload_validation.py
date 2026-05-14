from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
UNSUPPORTED_IMAGE_DETAIL = "Upload must be a JPEG, PNG, WEBP, or non-animated GIF image."
EMPTY_IMAGE_DETAIL = "Image is empty."


async def read_valid_image_upload(*, image: UploadFile, settings: Settings) -> bytes:
    """Read image bytes after applying shared upload constraints for meal photos."""

    if image.content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=UNSUPPORTED_IMAGE_DETAIL,
        )

    image_bytes = await image.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=EMPTY_IMAGE_DETAIL)
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Image exceeds {settings.max_upload_mb} MB limit.",
        )

    return image_bytes
