from __future__ import annotations

import io
import logging
import mimetypes
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


@dataclass
class UploadedFile:
    file_url: str
    object_name: str  # Internal storage path for future retrieval
    file_name: str
    file_mime_type: str
    file_size: int


class StorageService(ABC):
    @abstractmethod
    def upload_file(
        self,
        *,
        file_data: bytes,
        original_name: str,
        mime_type: str,
        folder: str = "uploads",
    ) -> UploadedFile:
        ...

    @abstractmethod
    def get_file_url(self, object_name: str) -> str:
        ...

    @abstractmethod
    def delete_file(self, object_name: str) -> None:
        ...

    @abstractmethod
    def get_file_bytes(self, object_name: str) -> bytes | None:
        ...

    @abstractmethod
    def get_presigned_internal_path(self, object_name: str) -> str:
        """Returns path for nginx X-Accel-Redirect (e.g. /internal-storage/bucket/object?sig)."""
        ...


def validate_upload(file_data: bytes, original_name: str, mime_type: str) -> None:
    if len(file_data) > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit")

    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"File type '{mime_type}' not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )

    import os
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File extension '{ext}' not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Detect real MIME from magic bytes to prevent type spoofing
    detected = _detect_mime(file_data)
    if detected and detected not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Detected file type '{detected}' does not match allowed types")


def _detect_mime(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"%PDF":
        return "application/pdf"
    return None


class MinioStorageService(StorageService):
    def __init__(self) -> None:
        from app.core.config import get_settings
        settings = get_settings()
        self._internal_endpoint = settings.minio_endpoint
        self._public_endpoint = settings.minio_public_endpoint or settings.minio_endpoint
        try:
            from minio import Minio
            self._client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
            )
            self._bucket = settings.minio_bucket
            self._ensure_bucket()
        except Exception as exc:
            logger.warning("MinIO not available: %s", exc)
            self._client = None
            self._bucket = settings.minio_bucket

    def _ensure_bucket(self) -> None:
        if self._client and not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def upload_file(
        self,
        *,
        file_data: bytes,
        original_name: str,
        mime_type: str,
        folder: str = "uploads",
    ) -> UploadedFile:
        validate_upload(file_data, original_name, mime_type)

        import os
        ext = os.path.splitext(original_name)[1].lower()
        object_name = f"{folder}/{uuid.uuid4().hex}{ext}"

        if self._client:
            self._client.put_object(
                self._bucket,
                object_name,
                io.BytesIO(file_data),
                length=len(file_data),
                content_type=mime_type,
            )
        else:
            raise RuntimeError("MinIO is unavailable — file cannot be persisted")

        return UploadedFile(
            file_url=self.get_file_url(object_name),
            object_name=object_name,
            file_name=original_name,
            file_mime_type=mime_type,
            file_size=len(file_data),
        )

    def get_file_url(self, object_name: str) -> str:
        if self._client:
            url = self._client.presigned_get_object(self._bucket, object_name)
            if self._public_endpoint and self._internal_endpoint:
                url = url.replace(self._internal_endpoint, self._public_endpoint, 1)
            return url
        return f"/storage/{object_name}"

    def delete_file(self, object_name: str) -> None:
        if self._client:
            self._client.remove_object(self._bucket, object_name)

    def get_file_bytes(self, object_name: str) -> bytes | None:
        if not self._client:
            return None
        try:
            resp = self._client.get_object(self._bucket, object_name)
            return resp.read()
        except Exception as exc:
            logger.warning("Storage get_file_bytes failed for %s: %s", object_name, exc)
            return None

    def get_presigned_internal_path(self, object_name: str) -> str:
        if not self._client:
            raise RuntimeError("MinIO unavailable — cannot generate presigned path")
        presigned = self._client.presigned_get_object(
            self._bucket, object_name, expires=timedelta(hours=1)
        )
        parsed = urlparse(presigned)
        qs = f"?{parsed.query}" if parsed.query else ""
        return f"/internal-storage{parsed.path}{qs}"


@lru_cache(maxsize=1)
def get_storage() -> StorageService:
    return MinioStorageService()
