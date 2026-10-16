# S2R3 Audit Remediation Implementation Plan

> **For agentic workers:** Implement this plan inline in small reviewable steps. Independent testing is owned by the test task; the developer must not run tests or modify test oracles.

**Goal:** Correct the static audit findings in a new isolated candidate by binding reviewer configuration, exposing truthful QA readiness, minimizing rejected-evidence preview data, and checking all supported evidence for cross-source conflicts with auditable fixed batches.

**Architecture:** Keep S2R2 unchanged. The answer pipeline recalls up to 40 eligible passages, performs per-passage review, selects up to 6 proposed sources under existing budgets, then asks the same injected reviewer to check the proposed set internally and against every other supported passage. Any invalid result, conflict, uncertainty, resource limit, or incomplete coverage blocks answer generation and cloud confirmation. Production has no qualified reviewer, so readiness remains blocked.

**Tech Stack:** Python standard library, existing local SQLite/index adapters, existing `ReviewInput`, HTTP UI.

**Spec:** `docs/superpowers/specs/2026-10-17-s2r3-audit-remediation-design.md`

## Global Constraints

- Preserve S2R2 `4e8e8cac10452b5e0b565902bd191acba90dd26f` and prior S2R3 candidate `9a5596e40c8904b42bd6f019de8e88a73f83decc` unchanged.
- Never read the formal library, call real DeepSeek, or download/build/launch Q6_K or reviewer models.
- Test doubles are marked `test-double`; their signature proves only isolated wiring, not model provenance or quality.
- No test/oracle/registry/freeze files are modified or executed in the developer task.
- Embedding/index failures and reviewer failures remain explicit unavailable states with no keyword fallback.
- Rejected evidence returns reason-code counts only; conflict evidence returns only verified conflicting sides as read-only quotes.

---

## File Structure

- Modify `pkb/evidence_review.py` to expose read-only verified configuration and signature fields for reviewer adapters.
- Modify `pkb/evidence_pipeline.py` for strict quote validation, per-passage candidate retention, fixed set-review batches, coverage ledger, and fail-closed budget states.
- Modify `pkb/answers.py` for QA readiness, minimal diagnostics, read-only conflicts, and reviewer/index snapshot revalidation.
- Modify `pkb/server.py`, `pkb/static/app.js`, and `pkb/static/index.html` for combined QA status and clear, non-selectable conflict display.
- Update `docs/development/S2R3-evidence-gate-handoff.md` with exact candidate, interface and independent-test scope.

## Task 1: Reviewer Identity and Quote Gate

- [x] Expose read-only reviewer `configuration` and `config_signature`; bind candidate, model/config SHA-256, quantization, template, settings, reviewer-pipeline version, runtime version and result-protocol version.
- [x] Have `EvidencePipeline` recompute and compare the adapter signature at construction, before and after each review, and before context return.
- [x] Require result hashes, versions and signatures to match. Accept quotes only when each is a continuous source substring, non-whitespace, contains a Unicode letter/number, and remains intact in output.
- [x] Keep synthetic doubles outside production wiring and require their own explicit `test-double` configuration signature.

## Task 2: Fixed Evidence-Set Review

**Limits:** 40 retrieved candidates; 6 proposed sources; 2 per document; 6000 source characters total; 1200 per source; at most 2 remaining candidates per set-review batch; 16,000 serialized characters per batch; 300,000 aggregate serialized characters; 20 batches; 120 seconds total.

- [x] Retain all individually supported candidates through rank 40, with source IDs, complete accepted quotes, source versions and local passage text; do not expose unselected or rejected bodies through the QA API.
- [x] Select the proposed answer set deterministically under the 6/2-per-document/6000-character rules without truncating a required quote.
- [x] Review the proposed set internally when it has at least two sources; then partition every remaining supported candidate in ranked groups of at most two and compare each group against the complete proposed set.
- [x] For each batch pass question, exact accepted quotes and source IDs, explicit `proposed_answer_evidence` / `remaining_supported_evidence` roles, exact pair plan and remaining timeout to the same reviewer.
- [x] Require exact question/evidence/plan digests, config signature, result protocol, source coverage and checked-pair coverage. For `consistent`, every required pair must be listed as checked. For `conflict`, every reported side must resolve to a current source ID and exact accepted quote.
- [x] Store an append-only in-memory coverage ledger sealed into the reviewed snapshot digest, with source IDs, pair-plan digest, input digest/size, verdict, conflicts/output summary and reason code. Any conflict, uncertainty, invalid output, signature drift, missing batch, exceeded budget or timeout produces no answer sources and no confirmation.
- [x] Verify all internally supported rank-7+ items receive selected-versus-remaining coverage before declaring consistency.

## Task 3: API/UI and Consent State

- [x] Keep semantic/index readiness and QA readiness separate. QA is ready only with complete embedding/index state and a formally qualified reviewer/collection gate; this candidate is always formal-blocked.
- [x] Have `/api/semantic/status` expose `qa.available/state/reason`; keep local browse status independent. Disable all QA UI controls when `qa.available` is false.
- [x] Return rejected evidence reason counts without rejected titles, bodies, or selectable IDs.
- [x] On conflict, return no selectable QA sources; render only validated source labels and quote spans for both sides. Cloud prepare/generate reject even if the caller posts a formerly visible conflicting ID.
- [x] Bind reviewer/config, full supported-set coverage ledger digest, source versions, index revision and reviewed snapshot into confirmation rebuild; drift invalidates old confirmations.

## Task 4: Handoff and Fixed Candidate

- [x] Run only static diff review; do not execute tests.
- [ ] Record new fixed candidate commit and changed files in the handoff.
- [ ] Send the candidate and immutable scope to independent test and audit tasks; state all non-claims explicitly.

## Scope Exclusions

No test suite, case registry, labels, run manifest, audit finding, acceptance record, model asset, formal data, cloud request, browser execution, test oracle, prior commit, or Q6 approval state is changed by this plan.
