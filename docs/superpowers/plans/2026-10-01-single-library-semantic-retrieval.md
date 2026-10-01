# Single Library Semantic Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the independent personal-memory product path with one local document library, safely migrate legacy memories into documents, and make calibrated local semantic retrieval the only natural-language evidence path.

**Architecture:** Add a fail-closed legacy migration layer and document qualification metadata to `Store`, then replace the current fallback-oriented vector adapter with a versioned single-index lifecycle and calibrated retrieval API. `Answers`, HTTP routes, UI, and backup/restore consume document sources only; legacy memory tables remain read-only for recovery and old-history cleanup.

**Tech Stack:** Python 3 standard library, SQLite, llama.cpp OpenAI-compatible loopback embeddings API, native HTML/CSS/JavaScript.

**Spec:** `docs/superpowers/specs/2026-09-30-single-library-semantic-retrieval-design.md` (S1)

## Global Constraints

- Development does not run functional, browser, regression, or model-quality tests; independent testing owns those results.
- Never edit or commit `docs/testing/`, `docs/audit/`, or `docs/acceptance/`.
- Only `127.0.0.1` may be used for embeddings; never download a model or call cloud embeddings automatically.
- `privacy=local`, unreviewed, inactive, conflicted, missing-source, or source-restricted content must be excluded before indexing and retrieval.
- Natural-language retrieval must stop when the semantic service, compatible complete index, or calibrated threshold is unavailable. There is no keyword fallback.
- Exact document lookup remains independent and cannot prepare an answer or cloud confirmation.
- No real DeepSeek request is made during development or independent calibration.
- Legacy memory rows are retained read-only; migration is deterministic, idempotent, backed up, manifest-recorded, and never merges by text similarity.
- New answers and outbound identifiers use document chunks only. All pre-upgrade confirmation tokens are invalid after restart and payload schema changes.

---

### Task 1: Document qualification and legacy-memory migration

**Files:**
- Create: `pkb/migration.py`
- Modify: `pkb/store.py`
- Modify: `pkb/backup.py`

**Interfaces:**
- Produces: `Store.question_eligible(db, document_id) -> (bool, reason)`.
- Produces: `Store.refresh_qualification(db, document_id)` and `Store.invalidate_document(db, document_id)`.
- Produces: `LegacyMemoryMigration(store).run(backup_path=None) -> dict`.
- Produces tables: `document_metadata`, `document_sources`, `legacy_memory_map`, `single_library_migrations`.

- [x] Add backward-compatible schema creation for document question state, content/qualification versions, migration metadata, lineage, and deterministic legacy mapping without altering old tables.
- [x] Implement qualification from current document parsing/status/privacy/question state and every source dependency; invalid, missing, local, or cyclic dependencies fail closed.
- [x] Implement deterministic legacy document IDs from old memory IDs, original UTF-8 bodies, original timestamps/privacy/status/origin/history/source links, conflict reasons, and exact one-row-per-memory idempotency.
- [x] Create a recoverable pre-migration ZIP through the existing backup mechanism and persist its path/hash plus source/created/mapped/blocked counts in the migration manifest before enabling the new path.
- [x] Keep `memories`, `memory_sources`, `memory_history`, `answer_memories`, and tombstones read-only after migration; preserve old answer cleanup through the legacy mapping.
- [x] Route old-backup restore through the same idempotent migration and current stricter privacy/tombstone rules.

### Task 2: Versioned single semantic index and readiness lifecycle

**Files:**
- Rewrite: `pkb/embedding.py`
- Create: `pkb/calibrate.py`
- Modify: `pkb/config.py`

**Interfaces:**
- Produces: `Embeddings.status() -> {state, reason, eligible, indexed, pending, excluded, signature, generation, calibrated, threshold}`.
- Produces: `Embeddings.retrieve(question, tag='', since='', until='') -> (items, retrieval)`; raises `SemanticUnavailable` unless state is `ready` or returns `no_evidence/no_match` as specified.
- Produces: `Embeddings.set_calibration(threshold, report_hash)` and calibration CLI `python3 -m pkb.calibrate`.

- [x] Create a new semantic-vector table binding chunk/document, normalized source hash, content/qualification version, model/template/query/pooling signature, dimension, and index generation.
- [x] Index only currently eligible parsed chunks with the fixed title/tag/body passage template; recheck source version and eligibility before writing without holding the database lock during embedding.
- [x] Represent `service_unavailable`, `indexing`, `index_error`, `calibration_required`, `no_evidence`, `no_match`, and `ready`; incomplete eligible indexes block all natural-language retrieval.
- [x] Validate finite normalized vectors, exact dimension/signature/generation compatibility, and fail instead of keyword fallback.
- [x] Implement thresholded top-40 semantic candidates, exact business-ID/title/tag/date ranking among those candidates, S1 RRF, stable tie breaks, six-chunk/two-per-document selection, and no low-score filling.
- [x] Add a calibration CLI that records fixed configuration and raw cosine scores from an isolated JSON dataset, and applies a measured threshold with a report hash; it never invents or auto-selects an unmeasured default.

### Task 3: Documents-only answers and confirmation binding

**Files:**
- Modify: `pkb/answers.py`

**Interfaces:**
- Consumes: `Embeddings.retrieve()` and current `Store.question_eligible()`.
- Produces documents-only `Answers.context`, payload schema `single-library-v1`, confirmation binding to semantic signature/generation/threshold and selected chunk versions.

- [x] Remove `Answers.memories`, memory evidence rendering, new `answer_memories` writes, and memory identifiers from outbound/cloud records.
- [x] Assemble at most six eligible chunks under the existing 6000/1200-character budgets and revalidate every document/chunk/version before use.
- [x] Make mock output documents-only and preserve the explicit local-simulation/non-advice statement.
- [x] Version the payload template, show exact truncated source text, and bind confirmation to payload, destination, semantic configuration, selected chunks, and current qualification/content versions.
- [x] Rebuild and revalidate semantic readiness, evidence, index generation, and payload before confirm; any change invalidates the token. Do not call DeepSeek during development.
- [x] Preserve old history and `answer_memories` only for read-only compatibility and mapped cleanup.

### Task 4: Single-entry HTTP API and user interface

**Files:**
- Modify: `pkb/server.py`
- Modify: `pkb/static/index.html`
- Modify: `pkb/static/app.js`
- Modify: `pkb/static/style.css`

**Interfaces:**
- Produces: exact lookup `/api/documents` independent of embeddings.
- Produces: semantic readiness `/api/semantic/status`, local retry `/api/semantic/retry`, and migrated document review `/api/documents/<id>/question-state`.
- Removes normal memory CRUD routes and UI.

- [x] Stop constructing or attaching `Memories` at runtime; run migration before exposing the server and retain its manifest for `/api/migrations`.
- [x] Make document search exact-only and label it as not understanding natural-language questions.
- [x] Return semantic readiness/progress/reasons; natural-language preview/mock/prepare errors remain actionable and never render fallback results.
- [x] Remove memory navigation, forms, rendering, cloud-confirmation section, and memory-specific copy.
- [x] Show migrated source/status/reason/lineage in document detail and allow explicit activation/deactivation only after server-side qualification recheck.
- [x] Show indexing/calibration/service errors, exact-search availability, and excluded/unparsed counts without exposing local content in logs.

### Task 5: Backup, restore, lifecycle cleanup, and operator workflow

**Files:**
- Modify: `pkb/backup.py`
- Modify: `README.md`
- Modify: `docs/THIRD_PARTY_NOTICES.md` only if the fixed runtime metadata changed
- Create: `docs/deliveries/S1-single-library-calibration-candidate.md`
- Modify: `docs/development-status.md`
- Modify: `docs/development-testing-handoff.md`

**Interfaces:**
- Produces a fixed calibration-candidate commit and exact commands for backup, migration, embeddings, indexing status, exact lookup, calibration measurement/application, app launch, and restore.

- [x] Export the new schema/mapping/manifest while excluding credentials; restore documents, lineage, tombstones, old compatibility tables, then migrate and rebuild rather than trusting archived vectors.
- [x] Ensure privacy tightening, deletion, edits, source invalidation, restore, model/template changes, and parsing changes invalidate vectors, answers, outbound records, and pending confirmations within existing safe scope.
- [x] Update operator documentation to the one-entry product, fixed Qwen/llama.cpp runtime, no-fallback readiness behavior, unencrypted-backup notice, and two-stage calibration workflow.
- [x] Record the exact migration/index/payload versions, static checks, known uncalibrated limitation, and unchanged DeepSeek consent boundary.
- [x] Run only `compile(...)`, JavaScript syntax parsing if an installed local runtime is available, and `git diff --check`; do not run application or quality tests.
- [x] Commit development-owned files only and notify independent testing with S1 migration, deterministic safety, historical assertion mapping, real-model calibration, browser, network, and zero-cloud requirements.

### Task 6: Freeze measured configuration after independent calibration

**Files:**
- Modify only files required to pin the measured threshold/configuration and delivery documentation.

**Interfaces:**
- Consumes independent test report containing fixed model/runtime/template/query/pooling/dimension, all calibration scores, selected threshold, validation results, and failure samples.
- Produces the final immutable S1 candidate for complete retest and audit.

- [ ] Review the independent calibration evidence without changing labels or adding lexical special cases.
- [ ] If no threshold satisfies S1, send raw scores and failures to product and keep natural-language retrieval unavailable.
- [ ] If a threshold satisfies S1, pin it with its configuration/report hash, invalidate previous indexes, and create a new fixed commit.
- [ ] Hand the new commit to independent testing for full validation and historical mapping, then to audit; do not treat calibration-candidate evidence as final-candidate evidence.
