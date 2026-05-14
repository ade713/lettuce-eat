from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.core.config import Settings
from app.services.upload_validation import read_valid_image_upload


def _upload_file(*, content: bytes, content_type: str) -> UploadFile:
    """Build an UploadFile for shared upload validation tests."""

    return UploadFile(
        filename="meal.jpg",
        file=BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


def _settings_with_max_upload_mb(max_upload_mb: int) -> Settings:
    """Build Settings with an upload limit without using env alias constructor kwargs."""

    return Settings.model_validate({"MAX_UPLOAD_MB": max_upload_mb})


async def test_read_valid_image_upload_returns_image_bytes():
    """Verify valid image uploads are read and returned unchanged."""

    image_bytes = b"fake-image-bytes"
    image = _upload_file(content=image_bytes, content_type="image/jpeg")

    result = await read_valid_image_upload(image=image, settings=_settings_with_max_upload_mb(10))

    assert result == image_bytes


async def test_read_valid_image_upload_rejects_unsupported_content_type():
    """Verify non-image uploads fail before callers store or analyze bytes."""

    image = _upload_file(content=b"not-an-image", content_type="text/plain")

    with pytest.raises(HTTPException) as exc_info:
        await read_valid_image_upload(image=image, settings=_settings_with_max_upload_mb(10))

    assert exc_info.value.status_code == 415
    assert exc_info.value.detail == "Upload must be a JPEG, PNG, WEBP, or non-animated GIF image."


async def test_read_valid_image_upload_rejects_empty_images():
    """Verify empty image uploads fail before callers store or analyze bytes."""

    image = _upload_file(content=b"", content_type="image/jpeg")

    with pytest.raises(HTTPException) as exc_info:
        await read_valid_image_upload(image=image, settings=_settings_with_max_upload_mb(10))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Image is empty."


async def test_read_valid_image_upload_rejects_oversized_images():
    """Verify oversized image uploads fail before callers store or analyze bytes."""

    image = _upload_file(content=b"01", content_type="image/jpeg")

    with pytest.raises(HTTPException) as exc_info:
        await read_valid_image_upload(image=image, settings=_settings_with_max_upload_mb(0))

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "Image exceeds 0 MB limit."
