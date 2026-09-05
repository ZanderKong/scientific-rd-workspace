from __future__ import annotations

import io

import pytest

from app.storage import LocalStorageProvider, S3StorageProvider, StorageRouter, sanitise_filename


def test_local_storage_hash_size_and_path_safety(tmp_path):
    storage = LocalStorageProvider(tmp_path)
    size, digest = storage.put("assets/example.txt", io.BytesIO(b"hello"))
    assert size == 5
    assert digest == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert storage.exists("assets/example.txt")
    assert storage.head("assets/example.txt")["size_bytes"] == 5
    assert storage.open("assets/example.txt").read_bytes() == b"hello"
    with pytest.raises(ValueError):
        storage.path_for("../outside.txt")
    storage.delete("assets/example.txt")
    assert not storage.exists("assets/example.txt")


def test_storage_policy_and_filename_sanitisation(tmp_path):
    local = LocalStorageProvider(tmp_path)
    router = StorageRouter(local, image_to_s3=False, large_file_threshold=10)
    assert router.choose(mime_type="image/png", size_bytes=1) is local
    assert sanitise_filename("../../unsafe/结果.png") == "__.png"


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes):
        self.objects[Key] = Body

    def get_object(self, *, Bucket: str, Key: str):
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, *, Bucket: str, Key: str):
        self.objects.pop(Key, None)

    def head_object(self, *, Bucket: str, Key: str):
        return {"ContentLength": len(self.objects[Key]), "ETag": '"etag"'}

    def generate_presigned_url(self, operation: str, *, Params: dict[str, str], ExpiresIn: int):
        return f"https://example.test/{Params['Key']}?expires={ExpiresIn}"


def test_s3_provider_uses_injected_client():
    storage = S3StorageProvider(
        endpoint_url=None,
        region=None,
        bucket="bucket",
        access_key_id=None,
        secret_access_key=None,
        client=FakeS3(),
    )
    size, digest = storage.put("asset.bin", io.BytesIO(b"payload"))
    assert size == 7
    assert storage.head("asset.bin")["size_bytes"] == 7
    assert storage.open("asset.bin").read() == b"payload"
    assert storage.presigned_url("asset.bin", expires_in=60).endswith("expires=60")
    storage.delete("asset.bin")
    assert not storage.exists("asset.bin")
