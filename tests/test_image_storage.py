import hashlib

from app.services.image_storage import LocalImageStorageService


async def test_local_image_storage_writes_image_and_returns_metadata(tmp_path):
    """Verify local image storage writes bytes and returns dataset metadata."""

    image_bytes = b"fake-image-bytes"
    expected_hash = hashlib.sha256(image_bytes).hexdigest()
    service = LocalImageStorageService(storage_root=tmp_path)

    metadata = await service.store_image(image_bytes=image_bytes, content_type="image/jpeg")

    stored_path = tmp_path / metadata.image_storage_key
    assert metadata.storage_provider == "local"
    assert metadata.image_storage_key.startswith("meal-images/")
    assert metadata.image_storage_key.endswith(".jpg")
    assert metadata.image_content_type == "image/jpeg"
    assert metadata.image_size_bytes == len(image_bytes)
    assert metadata.image_sha256 == expected_hash
    assert stored_path.read_bytes() == image_bytes


async def test_local_image_storage_uses_binary_extension_for_unknown_content_type(tmp_path):
    """Verify unsupported image content types still get a safe local file extension."""

    service = LocalImageStorageService(storage_root=tmp_path)

    metadata = await service.store_image(
        image_bytes=b"bytes", content_type="application/octet-stream"
    )

    assert metadata.image_storage_key.endswith(".bin")
    assert (tmp_path / metadata.image_storage_key).exists()
