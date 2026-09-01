from __future__ import annotations

import io

import pytest

from app.storage import LocalStorageAdapter, sanitise_filename


def test_storage_sanitises_names_and_keeps_keys_inside_root(tmp_path) -> None:
    assert sanitise_filename('../../notes:trial?.txt') == 'notes_trial_.txt'
    adapter = LocalStorageAdapter(tmp_path)
    size, digest = adapter.put('experiment/file.txt', io.BytesIO(b'hello'))
    assert size == 5
    assert digest == '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    assert adapter.open('experiment/file.txt').read_bytes() == b'hello'
    with pytest.raises(ValueError):
        adapter.path_for('../outside.txt')
