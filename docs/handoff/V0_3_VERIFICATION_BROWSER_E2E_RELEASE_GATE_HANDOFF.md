# v0.3 Verification, Browser E2E & Release Gate Handoff

Plan: 10.2 — v0.3 Verification, Browser E2E & Release Gate

## Delivered

- The backend release contract has 21 isolated PostgreSQL tests, including Sample aggregate scope/identity/response freshness, MCP stdio/HTTP parity and Experiment shared-reference deletion.
- `GoldenCl2WorkflowFactory` supplies the repeat-safe synthetic Cl₂ acceptance fixture. `verify_seed`, `benchmark_object_graph`, `prepare_legacy_v02_fixture`, `verify_legacy_cutover` and `verify_no_legacy_runtime` are executable release checks.
- A clean migration reaches head with no Alembic warning or drift. A populated 0006 database migrates to canonical v0.3 kinds and has no remaining `legacy_*` tables.
- Formal Playwright tests cover a fresh no-seed project, Composer resolvers/binding fields/aggregate updates and Data/View/Claim/Experiment surfaces. Test evidence is retained on CI failure.
- MCP tests use `ClientSession` for both stdio and Streamable HTTP. Start logs alone are not accepted as contract proof.
- CI has six blocking gates and uploads browser reports, traces, videos, screenshots and API/web logs.

## Operational notes

- Use `npm run e2e:install` once to fetch Chromium, then run `npm run e2e` with `API_URL` and `WEB_URL` pointed at a migrated API and built web server.
- Browser guard failures include page errors, console errors, non-aborted failed requests and HTTP 5xx responses. Next.js intentionally aborts superseded RSC prefetches during navigation; those `net::ERR_ABORTED` events are not treated as application failures.
- `DELETE /api/v1/objects/{id}` is now available for canonical records. Deleting an Experiment removes its references but not shared targets. Foreign-key-protected records still return a semantic error rather than partially deleting data.
- The required final state is a clean branch pushed to `origin` with the six GitHub Actions jobs green.
