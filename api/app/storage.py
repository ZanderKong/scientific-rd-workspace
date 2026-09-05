from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import BinaryIO, Protocol


def sanitise_filename(filename: str) -> str:
    name = Path(filename or "asset").name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return name[:180] or "asset"


class StorageProvider(Protocol):
    backend: str

    def put(self, object_key: str, source: BinaryIO) -> tuple[int, str]: ...
    def open(self, object_key: str) -> Path | BinaryIO: ...
    def delete(self, object_key: str) -> None: ...
    def exists(self, object_key: str) -> bool: ...
    def head(self, object_key: str) -> dict[str, object]: ...


class LocalStorageProvider:
    backend = "local"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, object_key: str) -> Path:
        candidate = (self.root / object_key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ValueError("invalid storage key")
        return candidate

    def put(self, object_key: str, source: BinaryIO) -> tuple[int, str]:
        path = self.path_for(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        digest = hashlib.sha256()
        with path.open("wb") as destination:
            while chunk := source.read(1024 * 1024):
                destination.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        return size, digest.hexdigest()

    def open(self, object_key: str) -> Path:
        path = self.path_for(object_key)
        if not path.is_file():
            raise FileNotFoundError(object_key)
        return path

    def delete(self, object_key: str) -> None:
        path = self.path_for(object_key)
        if path.exists():
            path.unlink()

    def exists(self, object_key: str) -> bool:
        return self.path_for(object_key).is_file()

    def head(self, object_key: str) -> dict[str, object]:
        path = self.path_for(object_key)
        if not path.is_file():
            raise FileNotFoundError(object_key)
        return {"size_bytes": path.stat().st_size}


LocalStorageAdapter = LocalStorageProvider


class S3StorageProvider:
    backend = "s3"

    def __init__(
        self,
        *,
        endpoint_url: str | None,
        region: str | None,
        bucket: str,
        access_key_id: str | None,
        secret_access_key: str | None,
        client: object | None = None,
    ) -> None:
        if client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - optional dependency path
                raise RuntimeError("S3 storage requires boto3 or an injected client") from exc
            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=region,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )
        self.client = client
        self.bucket = bucket

    def put(self, object_key: str, source: BinaryIO) -> tuple[int, str]:
        content = source.read()
        self.client.put_object(Bucket=self.bucket, Key=object_key, Body=content)
        return len(content), hashlib.sha256(content).hexdigest()

    def open(self, object_key: str) -> BinaryIO:
        response = self.client.get_object(Bucket=self.bucket, Key=object_key)
        return io.BytesIO(response["Body"].read())

    def delete(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def exists(self, object_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_key)
        except Exception:
            return False
        return True

    def head(self, object_key: str) -> dict[str, object]:
        response = self.client.head_object(Bucket=self.bucket, Key=object_key)
        return {"size_bytes": response.get("ContentLength", 0), "etag": response.get("ETag")}

    def presigned_url(self, object_key: str, expires_in: int = 900) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": object_key}, ExpiresIn=expires_in
        )


class StorageRouter:
    def __init__(
        self,
        local: LocalStorageProvider,
        s3: S3StorageProvider | None = None,
        *,
        image_to_s3: bool = False,
        large_file_threshold: int | None = None,
    ) -> None:
        self.local = local
        self.s3 = s3
        self.image_to_s3 = image_to_s3
        self.large_file_threshold = large_file_threshold

    def choose(self, *, mime_type: str | None, size_bytes: int | None = None) -> StorageProvider:
        if self.s3 is None:
            return self.local
        if self.image_to_s3 and mime_type and mime_type.startswith("image/"):
            return self.s3
        if (
            self.large_file_threshold is not None
            and size_bytes is not None
            and size_bytes >= self.large_file_threshold
        ):
            return self.s3
        return self.local
