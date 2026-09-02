# UI Rebuild Plan 2 Handoff

## Verdict

`PLAN 2 PASS — FULL-SITE UI REBUILD + PORTFOLIO POLISH ACCEPTED`

Plan 2 was executed as one frontend plan. Checkpoints are recorded here as acceptance evidence, not as additional plans. No Plan 3 work was started.

## Commits and scope boundary

- Starting commit: `c093a6f31f9aa21962d840e2030f0de4d651bc66`
- Final frontend implementation commit: `150485f4d2138b6326e49839706474e3f76b1e67`
- 1024px evidence fix commit: `bdfdb0d85220d99b31526fcabc91e193b0a16021`
- Backend/API/schema change count: `0`
- Database migrations, API routes, canonical enums, scientific content, model/provider keys, uploads, environment variables and API keys: unchanged.
- No new dependency, React Flow package, graph endpoint, design-system package, backend feature or scientific product feature was added.

## Checkpoint acceptance

### Checkpoint 1 — Projects and experiments

- Projects is a searchable/status-filtered table with New Project and Open actions.
- Project detail remains a research-program surface with experiment table, status, revision/provenance context and New Experiment action.
- Experiment detail preserves the existing tabs and record/file/measurement/literature/revision behavior while adding stable identity, metrics and provenance presentation.
- New Experiment uses the official JSON Forms schema-driven surface as the primary structured input. Raw JSON is not the primary editor.

### Checkpoint 2 — Measurement, Compare, Literature and Evidence

- Measurement flow is organized as Import → List → Detail with stepper-like hierarchy, compact table/list, chart, summary and provenance.
- Compare has explicit selection, a visible maximum of five experiments, structured differences matrix, compatible overlays and secondary literature/evidence context.
- Literature is bibliography-first; add literature and evidence actions are attached to source rows through modal dialogs.
- Existing import, compare payload and evidence behaviors were exercised against the running local API.

### Checkpoint 3 — Analysis, Evaluation and traceability

- Analysis list exposes useful run history; Analysis detail separates gate, confidence, direct/curated support, limitations, missing evidence and append-only human review.
- Evaluation list separates Bad Cases, Reference Cases and Runs.
- Evaluation detail renders deterministic and optional judge output as structured score cells/summary, with case context and source/replay links; raw JSON is secondary or absent from the primary surface.
- The reusable traceability fallback is a read-only timeline/list built only from current API data. It does not invent links or require graph endpoints.
- The real critical path created a new analysis run, accepted/rejected findings, created an evaluation run, opened Evaluation Detail, and opened a gated Suggested Draft Experiment with prefilled schema-driven fields.

### Checkpoint 4 — polish, i18n, responsive behavior and delivery

- Empty, loading and error states continue to use the existing shared page state; selected/disabled/focus/hover/destructive/tab/scroll states were checked on the critical surfaces.
- Real local app route sweep passed at 1280px in zh-CN and en with no page-level horizontal overflow or runtime error. The 1024px supplement used the Codex In-app Browser (`iab`, Chromium-backed) with an explicit `1024×720` viewport at DPR 2 against the running local app and demo seed. Overview, Experiment Detail, Compare, Analysis Detail and Evaluation Detail were each opened in both zh-CN and en; Experiment Detail's Measurements tab and Compare's three real overlays/charts were also exercised. `document.documentElement` and `body` reported no page-level horizontal overflow on every checked route; sidebar/header/main were present and usable, visible long-label collision checks were clear, charts stayed within the viewport, action bars exposed wrapping containers, and no unbounded tab/table scroll was needed (any horizontal containment remains local to the component). After closing the external TanStack Query Devtools overlay, all route checks reported zero console errors, zero hydration errors and zero runtime/application errors.
- Light mode was checked across all five routes in zh-CN and en. Dark mode was checked across all five routes in en and with an additional Evaluation Detail spot-check in zh-CN; the same overflow/header/chart/runtime checks passed.
- `<html lang>` changed correctly between `zh-CN` and `en`; the route stayed unchanged when switching locale. Translation catalogs remain parity-checked.
- Curated real-data screenshots are in `docs/assets/ui/`: Overview, Experiment Detail, Compare, Analysis Detail and Evaluation Detail. The README presents them as the finished product.
- `docs/UI_SPEC.md` records the final UI contract. This handoff records exact dependencies, tests, browser evidence and limitations.

## Shared implementation

- `web/src/features/workspace/components/scientific-ui.tsx`: minimal scientific UI primitives and traceability timeline.
- `web/src/features/workspace/presentation.ts`: bounded selection, readable structured value formatting, score normalization and traceability node normalization.
- Updated presentation surfaces: Overview, ProjectList, ExperimentCreate, ExperimentDetail, MeasurementData, CompareView, LiteratureView, AnalysisList, AnalysisDetail, EvaluationList and EvaluationDetail.
- 1024px audit fix: canonical measurement types now map to existing locale keys (`spectralResponse`, `timeSeries`, `otherXY`), removing the missing `Measurements.spectral_response` runtime message without changing the scientific enum.
- Updated catalogs: `web/messages/zh-CN.json` and `web/messages/en.json`.

## Dependencies and i18n

No dependency versions changed or were added in Plan 2. The implementation uses the repository's pinned versions:

- `next-intl@4.14.2` — existing locale provider, cookie persistence and UI translation boundary.
- `@jsonforms/core@3.8.0`, `@jsonforms/react@3.8.0`, `@jsonforms/vanilla-renderers@3.8.0` — existing schema-driven experiment form and official i18n prop.
- `@blocknote/core@0.54.0`, `@blocknote/react@0.54.0`, `@blocknote/mantine@0.54.0` — existing rich record editor and official locale dictionaries.
- React Flow was evaluated as optional and not added; the bounded read-only `TraceabilityTimeline` fallback is used.

Locale contract remains: `zh-CN` default, `en` fallback, no locale prefixes, `<html lang>` follows active locale, and first-party cookie `scientific_workspace_locale` persists the selection. API/DB enums and scientific prose remain canonical and untranslated.

## Verification evidence

Local frontend gates run from `web/`:

- `npm run format` — passed.
- `npm run format:check` — passed.
- `npm run lint` — passed; only pre-existing baseline warnings remain in calendar, kbar render-result and info-button.
- `npm run typecheck` — passed.
- `npm run test` — passed: 4 files, 14 tests, including bounded selection, structured value/score rendering and traceability normalization.
- `npm run build` — passed locally with Next.js 16.2.12/Turbopack; all 12 app routes compiled.

CI evidence retained from the project baseline:

- [Phase 1 frontend/CI run](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33616425820)
- [Phase 3 completion/CI run](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33616425909)
- [Plan 2 closeout Phase 1 CI run](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33651754023) — passed on `d6a94e9`.
- [Plan 2 closeout Phase 3 Scientific AI CI run](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33651754079) — passed on `d6a94e9`.

## Browser matrix

| Surface | zh-CN | en | 1280 | 1024 | dark | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Overview / Projects / Project Detail | checked | checked | checked | real `1024×720` | checked via shared shell | pass |
| Experiment Detail / New Experiment | checked | checked | checked | real `1024×720` | checked via shared shell | pass |
| Measurements / Compare / Literature | checked | checked | checked | real `1024×720` | checked via shared shell | pass |
| Analysis List / Analysis Detail | checked | checked | checked | real `1024×720` | checked via shared shell | pass |
| Evaluations / Evaluation Detail | checked | checked | checked | real `1024×720` | checked | pass |

Critical path used real local seed data: `Overview → Projects → PRJ-001 → EXP-041/044/045 → Compare → Analysis → human review → Evaluations → Evaluation Detail → Suggested Draft Experiment`.

## Limitations

- The upstream JSON Forms vanilla array/table renderer exposes the literal `Valid` header in its own renderer output; this is a known Plan 1 limitation and was not forked or replaced.
- Scientific source content and seeded Finding prose remain English by contract; UI chrome and status presentation are bilingual.
- Traceability is intentionally a bounded timeline/list fallback, not a graph editor or a new relationship service.
- README screenshots are curated 1280px local demo captures, not a claim of production data or deployment hosting.

## Closeout record

- Final frontend implementation commit: `150485f4d2138b6326e49839706474e3f76b1e67`
- Documentation closeout commit: the final `HEAD` after this handoff is committed.
- Final CI runs: Phase 1 `33651754023` and Phase 3 `33651754079`, both passed.
- Worktree clean after final documentation commit: `yes`
- No new tag created.

`PLAN 2 PASS — FULL-SITE UI REBUILD + PORTFOLIO POLISH ACCEPTED`
