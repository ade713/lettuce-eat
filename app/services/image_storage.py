import asyncio
import hashlib
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.schemas.nutrition import ImageStorageMetadata


_IMAGE_EXTENSIONS_BY_CONTENT_TYPE = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class ImageStorageService(Protocol):
    """Define how uploaded meal images are persisted before AI analysis."""

    async def store_image(self, *, image_bytes: bytes, content_type: str) -> ImageStorageMetadata:
        """Store image bytes and return metadata needed for later dataset records."""

        ...


class LocalImageStorageService:
    """Store uploaded meal images on the local filesystem for the MVP."""

    storage_provider = "local"

    def __init__(self, *, storage_root: Path) -> None:
        """Create a local image store rooted at the given directory."""

        self._storage_root = storage_root

    async def store_image(self, *, image_bytes: bytes, content_type: str) -> ImageStorageMetadata:
        """Write image bytes locally and return stable storage metadata."""

        image_sha256 = hashlib.sha256(image_bytes).hexdigest()
        image_storage_key = self._build_storage_key(content_type=content_type)
        image_path = self._storage_root / image_storage_key

        await asyncio.to_thread(self._write_image, image_path, image_bytes)

        return ImageStorageMetadata(
            storage_provider=self.storage_provider,
            image_storage_key=image_storage_key,
            image_content_type=content_type,
            image_size_bytes=len(image_bytes),
            image_sha256=image_sha256,
        )

    def _build_storage_key(self, *, content_type: str) -> str:
        """Build a storage key that keeps meal images grouped and uniquely named."""

        extension = _IMAGE_EXTENSIONS_BY_CONTENT_TYPE.get(content_type, ".bin")
        return f"meal-images/{uuid4()}{extension}"

    def _write_image(self, image_path: Path, image_bytes: bytes) -> None:
        """Create parent directories and write the image bytes to disk."""

        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image_bytes)
