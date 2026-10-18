# Assisted Retrieval Closeout Implementation Plan

> Execute inline in the developer chat. Independent testing/audit owns fixture, oracle, HTTP/browser execution and acceptance. Development runs no tests.

**Goal:** Deliver local related candidates for human comparison with visible provenance, bounds and exact current-passage navigation, without enabling formal QA.

**Spec:** `docs/superpowers/specs/2026-10-18-assisted-retrieval-fallback.md`, fixed `bfd54256a08c23c630a0a63ee0cb2c877403a23c`; audit scope `docs/audit/assisted-retrieval-fallback-20261018/report-and-closeout-scope.md`.

**Architecture:** Reuse `Embeddings.browse`, the existing GET semantic-search/document routes, and one vector table for collected/legacy_memory. Add truthful range metadata and thin browser presentation/navigation. Preserve the afa HTTP readiness mapping and all existing QA qualification/outbound checks.

## Existing capability / smallest gap

| Capability | Existing path | Work |
| --- | --- | --- |
| Two-source true cosine retrieval | `Embeddings.browse`, `_browseable_chunks`, one semantic_vectors table | Preserve ranking, eligibility and index/model signatures |
| Bounded candidates | HTTP default20; max2 passages/document; excerpt400 | Return actual result_limit/per_document_limit in browse status and display the scope |
| Full source/provenance | GET document returns metadata/versions/chunks | Show document/chunk ID, source/status/page, versions; use fetched current passage |
| Manual reading | semantic result opens whole document | Locate/focus matched chunk after checking current content/qualification versions |
| Local restricted/pending/inactive material | `Store.locally_browsable` and browse status | Preserve local-only labels and never feed selections into QA |
| Lifecycle | store edit/privacy/source/delete invalidates vectors | Clear stale UI candidates after mutations; reject changed/deleted clicked matches |
| QA and cloud | readiness remains blocked; typed failures409 | No change |

## Files and steps

- [x] `pkb/embedding.py`: add `result_limit` and `per_document_limit` to normal and no_evidence browse metadata; preserve all scoring/filter/selection logic and GET route.
- [x] `pkb/static/app.js`: make browse result cards visibly carry rank, cosine, source/status, document/chunk IDs, page and versions; state candidates need human judgment. Add query/detail request sequencing, current-version checks, exact-passage focus and selection clearing. Keep raw reading separate from answerPreview and all cloud/ticket functions.
- [x] `pkb/static/app.js`: reuse a current-document renderer for exact/semantic reading; invalidate only semantic result state after save/edit/privacy/legacy state/delete/retry so old responses cannot restore it. Ordinary exact lookup stays independent.
- [x] `pkb/static/index.html`, `style.css`: retain layout; add local query status, bounded/human-judgment explanation, readable IDs and focused-passage/active-card treatment, respecting reduced motion.
- [x] Statically review the diff and run `git diff --check` only. Do not run tests, app, model, browser or read formal data.
- [ ] Commit one new product/UI candidate. Freeze all pkb source/static hashes and the product spec; hand off exact routes, fields, bounds, changed/unchanged files and independent same-version acceptance scope.

## Guardrails

No new model/index/memory entry, pagination, unbounded results, similarity-as-answer correctness, auto-answer, new cloud path or reviewer bypass. No test/oracle/old result changes. Q6 is independent and no longer blocks this delivery. Keep afa/391/4e identities and failures. Candidate selection is only local reading; current formal QA, provider consent and restricted-material rules remain intact.

## Independent acceptance handoff

The assigned test task freezes a new same-candidate package covering real two-source embedding/cosine/rank, multiple indirect/insufficient/conflicting candidates, displayed bounds and provenance, actual local UI comparison/focus, concurrent query/navigation ordering, edit/privacy/legacy/source invalidation/delete, unavailable semantic service with distinct exact lookup, and no QA/provider/ticket success from manual selections. Existing HTTP400/409/preview200 behavior must remain on this candidate. Do not splice earlier version passes or require each candidate to be supported; development makes no test/acceptance claim.
