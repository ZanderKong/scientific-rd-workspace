# Scientific R&D Workspace Web

Next.js 16 frontend for Scientific R&D Workspace. It provides the Chinese-first Project/Vault shell, typed object lists and details, keyboard-first process composer, bounded provenance context views, and data import/payload surfaces.

```bash
npm ci
npm run dev
```

The API defaults to `http://localhost:8000/api/v1`; override it with `NEXT_PUBLIC_API_URL`. See the repository root README and `docs/UI_SPEC.md` for the active product contract.

Validation:

```bash
npm run lint
npm run typecheck
npm test -- --run
npm run build
```
