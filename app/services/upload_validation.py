from dataclasses import dataclass

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
UNSUPPORTED_IMAGE_DETAIL = "Upload must be a JPEG, PNG, WEBP, or non-animated GIF image."
EMPTY_IMAGE_DETAIL = "Image is empty."


@dataclass(frozen=True)
class ValidatedImageUpload:
    """Image upload bytes and metadata after shared validation has passed."""

    image_bytes: bytes
    content_type: str


async def read_valid_image_upload(*, image: UploadFile, settings: Settings) -> ValidatedImageUpload:
    """Read image bytes and content type after applying shared meal photo constraints."""

    content_type = image.content_type
    if content_type not in SUPPORTED_IMAGE_TYPES:
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

    return ValidatedImageUpload(image_bytes=image_bytes, content_type=content_type)
