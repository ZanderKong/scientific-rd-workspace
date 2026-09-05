# Full Functional Audit + Runtime Reliability

> **Archived legacy-runtime audit**: This is a historical Plan 06 evidence log. Its PASS/FAIL wording, runtime assumptions and failure status are preserved as recorded; it must not be read as the current audit. See [`docs/handoff/CURRENT_STATE.md`](../../../handoff/CURRENT_STATE.md) for the current boundary.

Status: FINAL — FULL FUNCTIONAL AUDIT NOT YET PASSED

This is the factual evidence log for Plan 06. The audit used the existing local
application, its real demo seed, and a real Chromium browser. No mock frontend
API, manual database correction, backend/API/schema/scientific-logic change, or
new product feature was introduced.

## Environment

- Host: macOS, local repository checkout.
- Starting repository SHA: `cb2fff118eed0a1a1fcc599964a2da911735b3ae` (clean after `git fetch origin`).
- Implementation commit pushed to `origin/main`: `55f0beb7823079df02bc41bdc3dfae2ff18c2a75`.
- Browser: real Chromium-backed local browser, viewport matrix `1024×720` and `1280×720`.
- Local frontend actually audited: `http://127.0.0.1:3000`.
- Local backend actually audited: `http://127.0.0.1:8000`.
- API base used by the frontend: `http://127.0.0.1:8000/api/v1`.
- Database: SQLite, exact path `/Users/kong/ZanderProject/scientific-rd-workspace/scientific-rd-workspace-codex-pack-v0.1/data/local/scientific_rd.db`.
- Storage root: `/Users/kong/ZanderProject/scientific-rd-workspace/scientific-rd-workspace-codex-pack-v0.1/data/uploads`.
- Seed verification: `PRJ-001` / `4c95b91b-35c7-4da7-b489-c9d31c094257`, `EXP-041` / `b3eb1fe2-1ea1-4e6e-9787-b031d6be73d7`, `EXP-044` / `8788c811-a0a2-4c87-8929-c4eb19e364da`, `EXP-045` / `bc8f58b6-eec9-42fb-8f19-dc7fd9d128cb`, template `materials-formulation-v1` / `19b32a17-fd7a-4472-901f-ca0eb72a05ec`.
- Disposable browser-created audit records: `PRJ-002` / `38c09a35-0e3b-4177-9909-d3074cab290b`, `EXP-046` / `19c1c4bc-165e-48e6-a42b-8a95119904cf`, clone `EXP-047` / `476a880a-56f9-4a53-a8fc-e4b1c58d2682`, suggested draft `EXP-048` / `fd9d8dce-e5fa-48a4-ab03-86900a335463`, analysis `6a240e20-6885-4cbe-afd9-e5e189b581cc`, evaluation `3d391761-703c-41ea-8bae-7aa6243fe64b`, literature `2b9cb2c1-c4ba-41f5-a12e-8c9e51a47a5c`.

## Summary counts

```text
Total audit items: 52
PASS: 42
FIXED: 4
BLOCKED: 3
NOT TESTED: 3
```

The audit is not a PASS because the three BLOCKED and three NOT TESTED items are
not all existing P0 flows with browser evidence. In particular, the current UI
does not expose Literature search, Evidence withdraw, or experiment-list
filters, and the two attachment deletions are awaiting action-time confirmation.

## Audit matrix

| ID | Feature | Test action | Expected | Actual | Result | Root cause | Fix | Evidence |
|---|---|---|---|---|---|---|---|---|
| A-01 | Clean start and seed | Fetched `origin`, checked clean tree, started local API/web, inspected seeded records | Reproducible local runtime and demo data | Clean start; SQLite path and seed IDs verified | PASS | — | — | Start SHA above; local services and seed IDs above |
| A-02 | Health and core endpoints | Called health, projects, experiments, templates, analysis runs, evaluation runs | 200 responses with bounded latency | All returned 200; observed 1.6–10.7 ms locally | PASS | — | — | `/api/v1/health`, `/projects`, project experiments, `/experiment-templates`, project analysis/evaluation runs |
| A-03 | Runtime URLs and API base | Opened real app against local API; checked representative request timing | No bad base URL, CORS, 404/422/500, or pending request | Requests reached `127.0.0.1:8000/api/v1`; no unexpected failed request in clean runs | PASS | — | — | Browser route sweeps; terminal API logs |
| A-04 | Clean production browser runtime | Opened fresh production tabs across routes/locales | No hydration, runtime, chunk, HMR, next-intl, or console errors | Fresh production sweeps had zero error logs, no overlay, and no hydration/runtime error | PASS | — | — | 1024 and 1280 route matrices below |
| A-05 | Hanging request reliability | Pointed a real local audit app at a controlled non-responding local endpoint and waited | Loading must terminate with an actionable error; no retry loop | UI showed `Request timed out. Try again.` after bounded wait; write failures made one request only | FIXED | Request wrapper had no timeout and did not preserve caller cancellation | Added central 10 s `AbortController` timeout, caller-signal propagation, cleanup, clear `ApiError`, and no retry | Browser controlled-hang run; `api-client.test.ts` timeout/network tests |
| B-01 | Sidebar initial state and shell | Opened without sidebar cookie assumptions; checked expanded shell and navigation | Sidebar/header usable and main content visible | Expanded shell, header, nav and main content usable | PASS | — | — | Real Overview/Projects/Experiment/Compare/Literature/Evaluation routes |
| B-02 | Sidebar collapse/navigation | Collapsed and reopened sidebar; clicked Projects, Compare, Literature, Evaluations | Collapsed navigation remains clickable and routes change | Initial collapsed nav clicks were blocked by invisible group labels; after fix all tested links navigated | FIXED | Collapsed labels kept pointer hit-testing while visually hidden | Added `pointer-events-none` to collapsed group labels | Browser `elementFromPoint` diagnosis and retest of all four links |
| B-03 | Keyboard sidebar shortcut | Used the real Cmd/Ctrl+B shortcut and refreshed | Sidebar toggles without covering main content | Toggle worked in the browser; main remained interactive | PASS | — | — | Real shell interaction at 1024 and 1280 |
| B-04 | Header global controls | Opened KBar, locale buttons, theme control, account control and info control | Controls open/work without overlay or runtime error | KBar search opened and closed; locale/theme/account/info controls worked | PASS | — | — | Fresh production DOM and interaction logs |
| B-05 | Info panel/rail | Toggled right info rail at 1024 and 1280; checked body/document widths | Rail usable; collapsed content must not create page overflow | Original rail was clipped and expanded panel stretched main; after fix rail toggled and widths stayed exact | FIXED | Offcanvas overflow clipping and flex min-content sizing | Kept rail visible, hid only collapsed inner content, moved right rail inward, added min-width containment | 1024 rail x≈1000–1016; 1280 rail x≈1256–1272; body/doc widths exact |
| B-06 | Shell matrix/locales/themes | Ran key routes in zh-CN/en light and zh-CN dark | No page overflow, collisions, or runtime errors | All final matrix rows had no loading and zero error logs | PASS | — | — | Final 1024 matrix and final 1280 matrix below |
| C-01 | Overview | Opened Overview; checked metrics and links | Page renders data and links | Metrics, project/experiment links and shell rendered | PASS | — | — | `/dashboard/overview` |
| C-02 | Project list search/filter | Searched audit project and changed status filter in Projects | Search/filter updates list and empty state is clear | `AUDIT` search found audit project; paused filter produced an explicit empty state | PASS | — | — | `/dashboard/projects` real controls |
| C-03 | Project create/edit/refresh | Opened create modal; tested blank validation; created, edited, refreshed and reopened project | Validation, persistence and route links work | `AUDIT-Project-06` created as `PRJ-002`; description edit survived reload | PASS | — | — | Project `38c09a35-0e3b-4177-9909-d3074cab290b` |
| C-04 | Project empty/error state | Used project navigation and loaded populated/disposable project states | Shell stays interactive and state is explicit | Populated project and empty filter states were explicit; no stuck loading | PASS | — | — | Projects browser snapshots |
| C-05 | New experiment/template/validation | Created from project; switched template; tested required fields; saved | Template fields, validation and persistence work | `EXP-046` created from template; title/objective/status and structured form persisted | PASS | — | — | Experiment `19c1c4bc-165e-48e6-a42b-8a95119904cf` |
| C-06 | Structured record edit/save | Edited objective and structured values; refreshed detail | Structured values persist and remain tied to record | Values persisted after refresh; no science-layer change | PASS | — | — | EXP-046 detail and record snapshots |
| C-07 | BlockNote note | Edited the real contenteditable note, saved, changed locale, reloaded | Note persists independently of structured fields | Audit note survived save, reload and locale switch | PASS | — | — | EXP-046 note: `Audit note: functional audit persistence check.` |
| C-08 | Files upload/list/download | Used real file chooser with `/tmp/AUDIT-06-measurement.csv`; listed and downloaded attachment | File is stored/listed/downloadable with visible metadata | 3-row CSV uploaded; list showed attachment; browser download media succeeded | PASS | — | — | EXP-046 attachment `a969b2d9-23cb-4228-8c83-f0b560bc3054` |
| C-09 | Files delete/confirm | Reached delete action for the two disposable audit attachments | Confirmed delete removes only selected audit attachment | Not executed: action-time confirmation is still required before accepting deletion | BLOCKED | Browser safety requires confirmation at the delete action; user confirmation not received | None; no deletion performed | EXP-046 and EXP-047 each still have the audit attachment |
| C-10 | Revisions | Created revision; opened historical version; attempted edits | Revision is append-only/read-only with visible note | Revision 1 created; historical view fields were disabled/read-only and note visible | PASS | — | — | EXP-046 revision 1, `Functional audit revision checkpoint` |
| C-11 | Clone/lineage/provenance | Cloned edited experiment; opened clone and provenance | Clone carries lineage/revision provenance without mutating parent | `EXP-047` created from EXP-046; parent and revision lineage visible | PASS | — | — | Clone `476a880a-56f9-4a53-a8fc-e4b1c58d2682` |
| D-01 | Measurement import | Selected attachment; previewed CSV; mapped axes/units; committed | Validation and commit create traceable measurement | 3 rows mapped as x/s and y/mV; commit succeeded | PASS | — | — | Measurement `Audit measurement`; CSV SHA `a77a5b98ba3067fa0d0deb076b439e50ec59426babdfe0ab998d051174c3b7` |
| D-02 | Measurement summary/chart/provenance | Opened measurement detail | Summary, points, chart and source identity render without overflow | Min/max/mean, 3 points, chart axes and source SHA/id rendered | PASS | — | — | EXP-046 measurement detail |
| D-03 | Literature add/persist/bind | Added literature in selected project; refreshed; checked Compare/experiment context | Source persists and can be selected as context | Literature persisted and was visible in project and Compare context | PASS | — | — | Literature `2b9cb2c1-c4ba-41f5-a12e-8c9e51a47a5c` |
| D-04 | Literature search | Looked for existing search control and attempted list search | Existing UI search should filter literature | No search input/control exists in current Literature UI | BLOCKED | Search is not exposed by the existing frontend | No new feature added, per audit scope | Literature snapshot: project selector, Add Literature, table only |
| D-05 | Evidence add/source binding | Added evidence and selected linked literature in project/Compare context | Evidence is active, source-tied and usable in analysis context | Claim was created active and tied to literature source | PASS | — | — | `Source supports audit material response interpretation.` |
| D-06 | Evidence withdraw | Looked for withdraw action on evidence log/source | Existing UI should withdraw evidence and show status | No withdraw control exists in current UI; no API/manual mutation used | BLOCKED | Withdraw is not exposed by the existing frontend | No new feature added, per audit scope | Literature snapshot shows active evidence but no withdraw action |
| D-07 | Compare two experiments | Selected two seeded experiments and ran comparison | Compare completes with revisions and compatible context | Two-selection comparison rendered | PASS | — | — | Compare real browser interaction |
| D-08 | Compare three/differences | Selected three experiments and inspected differences | Three-selection comparison and structured differences render | Three-selection comparison completed; differences were visible | PASS | — | — | Compare selection cap UI |
| D-09 | Compatible/incompatible measurements | Compared audit and clone measurements with compatible and incompatible units | Compatible overlays render; incompatible data is explained and excluded | Compatible s/mV overlay rendered; min/V data showed explicit incompatibility reason | PASS | — | — | `Audit measurement`; `Audit incompatible measurement` |
| D-10 | Compare maximum selection | Attempted maximum five selection | Selection is bounded at five and compare remains usable | UI displayed “maximum 5”; 2 and 3 were exercised, five-selection route was not run | NOT TESTED | — | — | Compare DOM showed `最多 5 条` |
| D-11 | Launch Analysis/context isolation | Switched project after selecting literature/evidence, then launched analysis | Context IDs must not leak across projects; analysis launches | Original repro returned `Evidence source is not in frozen context`; after clearing dependent selections, analysis succeeded | FIXED | Project switch retained stale literature/evidence IDs | Clear selected literature/evidence when project changes | Analysis `6a240e20-6885-4cbe-afd9-e5e189b581cc` |
| E-01 | Analysis list/detail/frozen context | Opened analysis list and completed detail | Frozen experiments, prompt/model hashes and findings render | Completed fixture run showed frozen context and one finding | PASS | — | — | Analysis `6a240e20-6885-4cbe-afd9-e5e189b581cc` |
| E-02 | Evidence Gate/support/confidence | Inspected finding support, limitations and confidence | Gate state and direct/curated support are explicit | Direct structured support and high confidence were visible; limitations/missing evidence rendered in seeded case | PASS | — | — | Seed analysis `3b2de6df-2e4c-42a5-8f6a-3bb980ef38c8` |
| E-03 | Review actions | Accepted a supported finding and inspected rejected seeded finding | Accept/reject reason/comment are append-only and survive refresh | Accepted finding persisted; seeded rejected finding showed insufficient-evidence/causal-overclaim reason | PASS | — | — | Accepted finding and review history in analysis detail |
| E-04 | Needs Evidence review | Tried to complete a separate Needs Evidence review with reason/comment | Status and review history persist | No completed browser evidence for this action | NOT TESTED | — | — | Seeded reject was tested, but Needs Evidence action was not completed |
| E-05 | Bad/reference expected cases | Created bad case from rejected finding; checked reference case | Case types and expected gate are visible and traceable | Bad case and reference case were created and visible | PASS | — | — | Bad case `8b2556eb-6df4-4f3c-aae2-952e1fc29bbc`; reference case `1dd07394-7f7e-4b7c-8ba8-2999a52061d7` |
| E-06 | Suggested draft | Created suggested experiment draft from accepted finding; edited and opened | Prefill, parent/review provenance and editable draft work | `EXP-048` created with prefilled fields, edited title and provenance links | PASS | — | — | `fd9d8dce-e5fa-48a4-ab03-86900a335463` |
| E-07 | Evaluation list/filter/cases | Opened evaluation list; filtered bad cases; checked reference/bad tags | Cases and filters are usable | 7 seeded cases shown; bad filter returned 3; tags/type visible | PASS | — | — | Evaluation list real browser snapshots |
| E-08 | Evaluation run lifecycle | Ran all cases and filtered bad cases; observed queued/running/poll/completed | Run starts, progress resolves, polling stops at terminal state | All-cases run `3d391761-703c-41ea-8bae-7aa6243fe64b` completed 7/7; filtered run completed 3/3 | PASS | — | — | Real EvaluationRun IDs and completed statuses |
| E-09 | Evaluation result/detail traceability | Opened completed detail; checked scores, source and replay links | Deterministic result is readable without raw JSON and traces to source/replay | Score matrices and pass counts rendered; source/replay links visible; no raw JSON panel | PASS | — | — | Evaluation detail for `3d391761-703c-41ea-8bae-7aa6243fe64b` |
| E-10 | Active evaluation cancellation | Tried to cancel while an active run was observable | If active control is observable, cancel should stop polling/run | Deterministic local run reached terminal state before cancel control could be acted on | NOT TESTED | — | — | Run lifecycle was verified through completion; no active window remained |
| F-01 | Backend unavailable/recovery | Stopped API; opened Overview and Experiment Detail; restarted API and reloaded | Loading ends in clear error; shell stays interactive; recovery works | Both pages showed `Backend unreachable...`; shell links remained; reload recovered after API restart | PASS | — | — | Offline browser run |
| F-02 | Invalid IDs | Opened invalid Project, Experiment, AnalysisRun and EvaluationRun URLs | Explicit not-found state, no indefinite loading | `project/experiment/analysis run/evaluation run not found` shown; no loading after wait | PASS | — | — | Four invalid-ID browser routes |
| F-03 | Failed write UX | Tested blank create validation and network-failed write | Error is clear, button re-enables, no duplicate write | Client validation was clear; network write made one request and returned clear error; controls re-enabled | PASS | — | — | Browser validation plus `api-client.test.ts` one-call assertion |
| F-04 | Overlay/buttons/runtime | Checked visible primary/action buttons across routes | No error overlay; primary buttons remain visible and usable | No overlay, hydration/runtime/chunk error, or hidden primary action in final production sweeps | PASS | — | — | Fresh production DOM snapshots |
| F-05 | Final 1024 matrix | Opened five required routes at 1024×720 in zh-CN/en light; Overview in zh-CN dark | No page overflow, loading, chart overflow, or console errors | All 10 light rows plus dark Overview had `body=1024`, `document=1024`, loading false, error logs 0; headings present | PASS | — | — | Overview; Experiment Detail; Compare; Analysis Detail; Evaluation Detail |
| F-06 | Final 1280 matrix | Opened 12 existing routes at 1280×720 in zh-CN light | Full route set renders without page overflow/errors | All 12 had `body=1280`, `document=1280`, loading false, error logs 0 | PASS | — | — | Overview, Projects, Project Detail, Experiments, Experiment Detail, Compare, Literature, Analysis, Analysis Detail, Evaluations, Evaluation Detail, New Experiment |
| G-01 | Local gates | Ran required web gates after final code changes | All required local commands pass | Test, lint, typecheck, build and format:check pass; backend pytest not required because backend untouched | PASS | — | — | Commands/results below |
| G-02 | CI Phase 1 and Phase 3 | Pushed implementation handoff and observed both CI phases | Both phases pass on final SHA | Phase 1 run `33663986281` and Phase 3 run `33663986247` passed, including PostgreSQL backend and frontend jobs | PASS | — | — | GitHub Actions runs for `55f0beb7823079df02bc41bdc3dfae2ff18c2a75` |
| G-03 | Final push/clean tree | Pushed `main`; checked repository status | Final handoff is on origin/main and tree is clean | `55f0beb` is on `origin/main`; tree was clean after push before this evidence-only update | PASS | — | — | `git push origin main`; final evidence update is this handoff commit |

## Bugs found

1. Hidden sidebar group labels intercepted clicks while collapsed. Root cause was
   pointer hit-testing on opacity-zero labels. Fixed with `pointer-events-none`
   on the label; collapsed navigation was retested successfully.
2. The offcanvas information rail was clipped at the viewport edge, and the
   expanded information panel could stretch the main flex item at 1024 px.
   Fixed with visible rail containment, collapsed-inner hiding, an inward rail
   offset, and `min-w-0` flex containment; 1024 and 1280 were retested.
3. Recharts initially kept a 512 px min-content width inside a narrower 1024 px
   grid cell. Fixed `ChartContainer` with `w-full min-w-0`; the measurement
   chart then measured within its cell and document width stayed 1024.
4. Switching Compare projects retained selected literature/evidence IDs. Root
   cause was stale optional context state. Clearing both selections on project
   change fixed the real API rejection (`Evidence source is not in frozen
   context`) and the subsequent analysis launch passed.
5. The API request wrapper had no bounded timeout. Added a central timeout,
   caller cancellation propagation, cleanup, explicit timeout/network errors,
   and tests; no write retry was added.

## Runtime evidence

- Fresh production browser route sweeps reported zero console error logs. No
  hydration, runtime, chunk, HMR, missing-translation, unhandled-rejection, or
  error-overlay signal was present in the final clean runs.
- Core local endpoint observations: health 1.664 ms; projects 1.832 ms; project
  experiments 2.430 ms; templates 1.618 ms; analysis runs 10.696 ms; evaluation
  runs 5.600 ms.
- API-offline behavior ended loading with `Backend unreachable. Start the API
  and try again.` on Overview and Experiment Detail; both recovered after API
  restart.
- Controlled non-responding API behavior ended loading with `Request timed
  out. Try again.`; the write network-failure test made one fetch call only.
- Final 1024 route matrix: zh-CN/light and en/light for all five required routes,
  plus zh-CN/dark Overview. Every row had `window.innerWidth=1024`,
  `document.body.scrollWidth=1024`, `document.documentElement.scrollWidth=1024`,
  no loading text, and zero error logs. Sidebar/header and the right info rail
  were interactable; charts and action bars stayed contained.
- Final 1280 route matrix: 12 existing zh-CN/light routes. Every row had body and
  document width 1280, no loading text, and zero error logs.

## Functional matrix B–E

The browser-verified scope is recorded row-by-row above. Existing P0 flows that
were exercised successfully include shell controls, project CRUD, experiment
creation/editing, BlockNote, file upload/list/download, revisions, cloning,
measurement import and provenance, Literature/Evidence add/binding, Compare,
Analysis/Evidence Gate/Review, bad/reference cases, suggested drafts, and
EvaluationRun lifecycle/results.

The following acceptance items remain open because the current frontend does not
expose the requested existing action or the audit did not obtain browser
evidence for it: attachment delete pending action-time confirmation, Literature
search, Evidence withdraw, five-selection Compare, Needs Evidence review, and
active EvaluationRun cancellation. No new UI was added to manufacture coverage.

## Tests and CI

Local gates after the final frontend changes:

- `npm run test -- --run`: PASS — 4 files, 16 tests.
- `npm run lint`: PASS — baseline warnings only in existing calendar/KBar/info
  button dependency locations; no lint error.
- `npm run typecheck`: PASS.
- `npm run build`: PASS — Next production build completed.
- `npm run format:check`: PASS.
- Backend pytest: NOT RUN — no backend files were changed.
- CI Phase 1: PASS — run `33663986281` on `55f0beb7823079df02bc41bdc3dfae2ff18c2a75`.
- CI Phase 3: PASS — run `33663986247` on `55f0beb7823079df02bc41bdc3dfae2ff18c2a75`.

## Remaining limitations

- This audit cannot be marked PASS while any required item is BLOCKED or NOT
  TESTED. The exact final verdict is therefore `FULL FUNCTIONAL AUDIT NOT YET
  PASSED`.
- The existing Literature view has no search control; the existing evidence log
  has no withdraw control; the global Experiments list has no search/status/time/
  lineage filter controls. Adding these would be new functionality and was out
  of scope.
- The two disposable audit attachments have not been deleted because the
  action-time confirmation required immediately before deletion has not been
  received. No manual DB correction was used.
- The deterministic local EvaluationRun completed too quickly to expose an
  active cancellation window.
- Disposable audit records remain in the local demo SQLite database; they were
  created through the UI and were not manually removed or corrected.
