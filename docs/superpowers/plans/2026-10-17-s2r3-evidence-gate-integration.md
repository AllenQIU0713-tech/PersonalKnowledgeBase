# S2R3 Evidence Gate Integration Plan

> **Status:** Initial integration scope; its unresolved static-audit remediation is tracked by the authoritative follow-up plan `2026-10-17-s2r3-audit-remediation.md`.

> **For agentic workers:** Implement this plan inline in small reviewable steps. Independent testing is owned by the test task; the developer must not run tests or modify test oracles.

**Goal:** Wire a fail-closed evidence-review gate into the answer path, with an explicitly injected deterministic reviewer substitute usable only by isolated synthetic tests, while preserving the unchanged S2R2 candidate and formal `calibration_required` state.

**Architecture:** Add an answer-pipeline boundary that consumes eligible semantic candidates, validates every reviewer result and verbatim quote, and creates a bounded reviewed evidence snapshot. `Answers` exposes only reviewed chunks to answer preview, mock generation, cloud preparation, and confirmation rebuild. A missing reviewer makes QA unavailable; local semantic browsing remains on its existing independent route. Production startup does not auto-enable or instantiate a test reviewer.

**Tech Stack:** Python standard library, existing SQLite store/embedding adapters, existing `pkb.evidence_review` input and error types.

**Spec:** `docs/superpowers/specs/2026-10-17-s2r3-evidence-gated-answer-pipeline.md`

## Global Constraints

- Preserve S2R2 commit `4e8e8cac10452b5e0b565902bd191acba90dd26f` unchanged.
- Use synthetic data only for S2R3 candidate verification; never read the formal library or call real DeepSeek.
- Do not download, build, convert, or start Q6_K or any reviewer model.
- The synthetic reviewer is an explicitly injected test double and is not evidence of reviewer quality or formal QA availability.
- Missing reviewer, reviewer exceptions, invalid verdicts, and invalid/non-verbatim quotes fail closed.
- Only evidence that passes the gate may enter `sources`, mock answer context, cloud preparation, or confirmation reconstruction.
- Keep tests, audit, and acceptance in their assigned tasks; do not edit their oracle assets or run tests in the developer task.

---

## File Structure

- Create `pkb/evidence_pipeline.py` for evidence candidate conversion, reviewer orchestration, deterministic output validation, bounded selection, and reviewed-snapshot signatures.
- Modify `pkb/answers.py` to accept an injected pipeline, fail closed when none is configured, and consume reviewed snapshots consistently in preview, cloud prepare/rebuild, and mock generation.
- Modify `pkb/embedding.py` only as needed to expose an answer-specific candidate retrieval method capped at 40 while preserving `retrieve()` behavior for existing browse/retrieval callers.
- Modify `pkb/server.py` only to construct the production `Answers` instance without any synthetic reviewer, ensuring QA remains unavailable until a separately qualified reviewer is approved.
- Create `docs/development/S2R3-evidence-gate-handoff.md` documenting fixed candidate commit, interface and startup behavior, synthetic-only injection seam, tested scope for the independent test task, and explicit non-claims.

## Task 1: Candidate Retrieval Snapshot

**Files:**
- Modify: `pkb/embedding.py`

**Interface:**
- Produces `Embeddings.retrieve_answer_candidates(question, limit=40) -> (items, retrieval)`.
- Each item retains document/chunk IDs, full passage text up to the reviewer input bound, title, source type/label, content and qualification versions, semantic similarity, fused score, and page.
- The method uses current question eligibility and index integrity checks, does not apply the answerability threshold as a gate, sorts deterministically, and returns at most 40; existing `retrieve()` behavior stays unchanged.

- [ ] Extract shared scoring into a private helper without changing the current `retrieve()` response contract.
- [ ] Add the answer-candidate method with strict `1..40` limit validation and current eligibility/version checks.
- [ ] Return the index signature/generation/revision snapshot alongside candidates and propagate embedding/index failures as `SemanticUnavailable`.
- [ ] Review the diff to confirm browse paths and the fixed S2R2 commit remain untouched.

## Task 2: Fail-Closed Evidence Pipeline

**Files:**
- Create: `pkb/evidence_pipeline.py`
- Consume: `pkb/evidence_review.py:ReviewInput`

**Interface:**
- `EvidencePipeline(reviewer, pipeline_version)`; derives reviewer signature from `reviewer.configuration` and validates `reviewer.signature`
- `EvidencePipeline.review(question, candidates, index_snapshot) -> ReviewedSnapshot`
- Each reviewer implements `review(ReviewInput) -> mapping` with a fixed `candidate`, signature, and output shape.

- [ ] Define immutable `ReviewedSnapshot` with question hash, index signature/generation/revision, pipeline/reviewer signatures, `sources`, `related_sources`, and a snapshot digest.
- [ ] Convert at most 40 candidate rows into bounded `ReviewInput` values; do not send privacy-local/ineligible content to reviewer.
- [ ] Require exact verdict enum and exact result passage/question/version hashes; accept only `supported` with one or more non-empty quotes found verbatim in the full passage.
- [ ] Treat all exceptions, timeouts, malformed results, signature mismatch, uncertain, insufficient, mismatch, and quote failure as rejected candidates, recording only a safe reason code.
- [ ] Select at most 6 passing chunks, at most 2 per document, and 6000 total characters; cap each source at 1200 while ensuring every selected quote remains present after clipping, otherwise omit it.
- [ ] Keep rejected but locally browseable chunks only in `related_sources`; never reuse them as answer evidence.
- [ ] Add a deterministic `SyntheticReviewer` only in a test-support module or expose the injection seam without a production factory; it must require explicit construction and return fixed configured quotes/verdicts. Production startup must never instantiate it.

## Task 3: Answer and Consent Binding

**Files:**
- Modify: `pkb/answers.py`
- Modify: `pkb/server.py`

**Interface changes:**
- `Answers(store, embeddings, cloud_provider=None, evidence_pipeline=None)`
- `Answers.context(question)` returns a fail-closed unavailable state when the pipeline is absent; otherwise it returns reviewed `sources` plus local-only `related_sources`.
- Confirmation record binds the reviewed snapshot digest, evidence IDs/hashes, reviewer signature, and pipeline version in addition to current semantic index and source versions.

- [ ] Route answer preview through candidate retrieval and `EvidencePipeline.review()`; do not fall back to `Embeddings.retrieve()` when the pipeline is missing.
- [ ] Make `prepare()` reject unavailable QA, enforce selection only from reviewed sources, and bind all reviewer/evidence snapshot fields into the one-time record.
- [ ] Make `_rebuild()` rerun the same configured evidence gate and reject any changed snapshot, signature, passage, eligibility, or index version before confirmation.
- [ ] Ensure mock generation receives only reviewed `sources`; no-source output states evidence is insufficient.
- [ ] Keep production server construction with no pipeline until a real reviewer independently qualifies; local browse and exact lookup paths remain unchanged.

## Task 4: Developer Handoff

**Files:**
- Create: `docs/development/S2R3-evidence-gate-handoff.md`

- [ ] Record the new candidate commit and changed files.
- [ ] Document the injection interface, expected synthetic fixture setup, fail-closed cases, and the candidate's unavailable production QA state.
- [ ] State that no tests were run by development and list what the independent test task must execute against an immutable bundle.
- [ ] State that this candidate does not prove model quality, formal answerability, browser integration, real DeepSeek behavior, or release readiness.

## Scope Exclusions

No test suite, labels, case registry, manifest, freeze record, audit report, acceptance record, real library, cloud provider request, model download, model launch, reviewer calibration, production UI claim, or S2R2 commit is changed by this plan.
