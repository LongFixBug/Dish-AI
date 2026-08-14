"""Durable object storage abstraction for sanitized feedback images."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path, PurePosixPath
from typing import Protocol

import boto3
from botocore.config import Config

from backend.config import Settings


class ObjectStorage(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> tuple[bytes, str]: ...

    async def delete(self, key: str) -> None: ...

    async def healthcheck(self) -> None: ...


class FilesystemObjectStorage:
    """Development storage with the same key contract as S3."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        del content_type
        target = self._target(key)

        def write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        await asyncio.to_thread(write)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._target(key).unlink, missing_ok=True)

    async def get(self, key: str) -> tuple[bytes, str]:
        target = self._target(key)

        def read() -> tuple[bytes, str]:
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            return target.read_bytes(), content_type

        return await asyncio.to_thread(read)

    async def healthcheck(self) -> None:
        await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)

    def _target(self, key: str) -> Path:
        pure_key = PurePosixPath(key)
        if pure_key.is_absolute() or ".." in pure_key.parts:
            raise ValueError("Object key must stay inside the storage root")
        target = (self.root / Path(*pure_key.parts)).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError("Object key must stay inside the storage root")
        return target


class S3ObjectStorage:
    """S3-compatible storage for production and local MinIO."""

    def __init__(self, settings: Settings) -> None:
        options: dict[str, object] = {
            "region_name": settings.s3_region,
            "config": Config(
                connect_timeout=3,
                read_timeout=10,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        }
        if settings.s3_endpoint_url:
            options["endpoint_url"] = settings.s3_endpoint_url
        if settings.s3_access_key_id:
            options["aws_access_key_id"] = settings.s3_access_key_id
        if settings.s3_secret_access_key:
            options["aws_secret_access_key"] = settings.s3_secret_access_key
        self._client = boto3.client("s3", **options)
        self._bucket = settings.s3_bucket

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=key,
        )

    async def get(self, key: str) -> tuple[bytes, str]:
        response = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self._bucket,
            Key=key,
        )
        content = await asyncio.to_thread(response["Body"].read)
        return content, response.get("ContentType") or "application/octet-stream"

    async def healthcheck(self) -> None:
        await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)


def create_object_storage(settings: Settings) -> ObjectStorage:
    if settings.object_storage_backend == "s3":
        return S3ObjectStorage(settings)
    if settings.object_storage_backend == "filesystem":
        return FilesystemObjectStorage(settings.object_storage_root)
    raise ValueError(
        f"Unsupported object storage backend: {settings.object_storage_backend}"
    )
