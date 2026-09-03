# Demo Scenario — v0.2 Research Object Graph

The seed is synthetic/anonymised and repeat-safe. It demonstrates a chlorine color-response material graph without claiming production scientific validity.

## Two-minute path

1. Open Overview and select `PRJ-001` — 氯气显色材料研发.
2. Open `EXP-001` and show its contained processes, samples and data.
3. Open `SMP-001`. Explain the distinction between direct producing process/material/equipment, current test data, upstream inputs and downstream branches.
4. Open `PRC-003` and use the composer: add a `uses` reference with `@MAT-003`, a `produces` sample, role and quantity, then save with Cmd/Ctrl+Enter.
5. Open a Data object. Show the XY payload summary, plot and source CSV provenance.
6. Create a revision with a note and show the immutable snapshot hash.

## Expected seed landmarks

- `PRJ-001`, `EXP-001`/`002`/`003`
- `MAT-001`…`005`, `EQP-001`…`004`
- `SMP-001`…`004`, `PRC-001`…`006`, `DAT-001`…`004`
- a downstream branch from `SMP-001` to `SMP-004`
- four small XY payloads with attachment/import provenance

## Setup

```bash
docker compose up -d postgres
cd api
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000

cd ../web
npm run dev
```

Start at `http://localhost:3000/dashboard/overview`. If PostgreSQL or the API is unavailable, the UI must show an explicit error state; it must not fall back to SQLite or fabricated runtime data.

## Deferred story

Compare, Literature, Evidence, AI finding and Evaluation are intentionally not part of this v0.2 demo. They require a separate Plan 2 after the object graph core is accepted.
