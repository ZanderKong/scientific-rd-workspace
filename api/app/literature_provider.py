"""Optional provider seam for future read-only Literature integrations.

Phase 2 deliberately ships manual/local Literature records only. Implementations
such as Zotero must map into the canonical LiteratureRecord through this seam and
must never expose provider payloads as the domain model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderLiterature:
    external_id: str
    title: str
    authors: list[dict[str, Any]]
    publication_year: int | None = None
    container_title: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    raw_json: dict[str, Any] | None = None
    provider_version: str | None = None


@dataclass(frozen=True)
class ProviderPage:
    items: list[ProviderLiterature]
    next_cursor: str | None = None


class LiteratureProvider(Protocol):
    provider_key: str

    def search(self, query: str, cursor: str | None = None) -> ProviderPage: ...

    def get_item(self, external_id: str) -> ProviderLiterature: ...
