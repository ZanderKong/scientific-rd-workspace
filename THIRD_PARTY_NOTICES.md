# Third-party notices

This project includes or depends on the following open-source software:

- Kiranism `next-shadcn-dashboard-starter` — MIT. Attribution and the original license are preserved in `web/LICENSE` and `third_party_licenses/`.
- JSON Forms (`@jsonforms/*`) — MIT.
- BlockNote (`@blocknote/core`, `@blocknote/react`, `@blocknote/shadcn`) — MPL-2.0. Phase 1 does not include any `@blocknote/xl-*` package.
- `next-intl` — MIT. Used only for the frontend message catalogs and locale presentation layer.
- LiteLLM Python SDK `1.99.0` — MIT (the exact version locked in `api/uv.lock`). Phase 3 embeds the SDK only; the LiteLLM Gateway/Proxy is not used.
- Langfuse Python SDK `4.15.1` — MIT (the exact version locked in `api/uv.lock`). Phase 3 uses it only as an optional, disabled-by-default trace projection.

This notice is informational and is not legal advice. Transitive dependency licenses remain recorded by the package manager lockfiles.
