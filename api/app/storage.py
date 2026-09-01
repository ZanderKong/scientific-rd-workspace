from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import BinaryIO


def sanitise_filename(filename: str) -> str:
    name = Path(filename or "attachment").name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return name[:180] or "attachment"


class LocalStorageAdapter:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if self.root not in candidate.parents:
            raise ValueError("invalid storage key")
        return candidate

    def put(self, storage_key: str, source: BinaryIO) -> tuple[int, str]:
        path = self.path_for(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        digest = hashlib.sha256()
        with path.open("wb") as destination:
            while chunk := source.read(1024 * 1024):
                destination.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        return size, digest.hexdigest()

    def open(self, storage_key: str) -> Path:
        path = self.path_for(storage_key)
        if not path.is_file():
            raise FileNotFoundError(storage_key)
        return path

    def delete(self, storage_key: str) -> None:
        path = self.path_for(storage_key)
        if path.exists():
            path.unlink()
