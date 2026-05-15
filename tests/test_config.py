from pathlib import Path

from app.core.config import Settings


def test_settings_default_local_storage_root():
    """Verify local image storage defaults to the project storage directory."""

    settings = Settings()

    assert settings.local_storage_root == Path("storage")


def test_settings_reads_local_storage_root_alias(monkeypatch):
    """Verify LOCAL_STORAGE_ROOT can move local image storage without code changes."""

    storage_root = Path("/tmp/lettuce-eat-images")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(storage_root))

    settings = Settings()

    assert settings.local_storage_root == storage_root
