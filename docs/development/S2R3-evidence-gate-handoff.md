# S2R3 evidence-gate candidate handoff

Status: fixed developer candidate; independent testing and audit pending. This does not enable formal QA, certify any reviewer model, or change `calibration_required`.

## Candidate boundary

- Parent behavior baseline: S2R2 commit `4e8e8cac10452b5e0b565902bd191acba90dd26f`; that commit remains unchanged.
- Previous static-review candidate: `9a5596e40c8904b42bd6f019de8e88a73f83decc`; preserve its audit evidence as-is.
- New code candidate commit: `391baf9db5afcffd8e2de4ba65782a05b6426a98` (`fix: close S2R3 evidence review audit gaps`). This commit contains the implementation; this handoff is finalized in a docs-only follow-up.
- Production `server.py` constructs `Answers` without an evidence pipeline. `/api/semantic/status` reports QA blocked when the vector index is ready but the reviewer is missing or unqualified; the UI disables QA controls from `qa.available`. Local semantic browsing reports its own index/service state and remains independent.
- `Answers.prepare`, `Answers.generate`, confirmation rebuild, and confirmation snapshot validation re-check formal QA readiness in the backend. A test double or a direct API call cannot create a cloud confirmation or simulated answer while the reviewer/collection gate is unqualified; the UI disablement is not the security boundary.
- Embedding/index failures stay explicit unavailable states; they do not become no-match results and never fall back to keyword retrieval.

## Reviewer identity and injection

`EvidencePipeline(reviewer)` reads a read-only `configuration` manifest and `config_signature` from the reviewer object. The manifest binds candidate identity, 64-character model/config digest, quantization, template version, settings, reviewer pipeline version, runtime version, and result-protocol version. `configuration_signature()` includes runtime and result-protocol versions; per-passage result envelopes bind the same fields. The pipeline recomputes and checks the signature at construction, before and after reviews, and before returning a preview. Each result must carry matching question/evidence/source-version hashes and config/pipeline/runtime/protocol identifiers. Configuration drift blocks the request and invalidates old preview/confirmation snapshots.

The independent test task may inject a deterministic `test-double` with its own explicit configuration digest and signature. That signature only proves wiring identity; it is not a real model source, model-quality, calibration, or formal QA claim. The double must implement both `review(input)` and `review_set(question, evidence, comparison_plan, timeout_seconds=...)` using the frozen S2R3 result protocol. Production startup never constructs the test double.

## Passage and evidence-set gates

The answer-specific embedding path recalls up to 40 eligible passages in one local cosine index. It does not apply the cosine threshold as an answerability gate. Each passage is locally reviewed before it can become supported. Quotes must be continuous original substrings, non-whitespace, and contain at least one Unicode letter or number; they must remain present after the source/context budget. Rejected items return only reason-code counts in the QA preview response, with no rejected passage text, title, or selectable ID. Open the independent local browse feature to inspect related material and its privacy/qualification state.

All supported candidates are retained internally for the consistency check. The proposed answer set is the deterministic ranked subset after the six-source, two-per-document, 6000-character rules. Candidate `s2r3-evidence-set-review-v1` policy is fixed:

1. If the proposed set has more than one item, check all proposed-to-proposed pairs in one batch.
2. Check every remaining supported candidate against the complete proposed set. Use ranked order and batches of at most two remaining candidates, so each batch has at most eight source records.
3. Each batch declares `proposed_answer_evidence` versus `remaining_supported_evidence` roles and the exact pair list. The reviewer returns exact source coverage, checked pairs, verdict, and for conflict each source ID with an exact accepted quote.
4. Per-batch serialized input cap is 16,000 characters; aggregate cap is 300,000 characters; maximum is 20 batches and 120 seconds total. The reviewer receives the remaining timeout for each batch. No passage or quote is silently truncated. Missing reviewer capability, invalid output, timeout, any conflict/uncertainty, budget exhaustion, or incomplete source/pair coverage blocks deterministic answers and cloud preparation.
5. Per-batch audit data binds source IDs, proposed/remaining roles, input digest/size, pair-plan digest, verdict, conflicts/output summary, and reason code. The public preview exposes only aggregate counts/digests, except verified conflict sides and their exact quotes.

A verified `consistent` result permits only the reviewed proposed evidence into `sources`. A `conflict` result displays both verified sides as read-only conflict groups, returns no selectable answer sources, and cannot be bypassed by posting one side's ID to cloud prepare. `uncertain` or incomplete coverage returns no source IDs or passages. Collection-level review remains candidate-only and cannot make the production readiness API report ready.

## Independent test scope

Use a new immutable run bundle under the product freeze contract. Preserve the previous candidate and audit files. Verify at least:

- missing reviewer with embedding/index ready: QA API/UI blocked while local browse remains ready; index failure remains visibly unavailable;
- empty/whitespace/punctuation-only/forged/truncated quotes reject; valid Chinese/date quotes can pass the wiring gate;
- reviewer manifest signature, result protocol, runtime/config drift and source-version mismatches fail closed;
- all supported candidates through rank 40 enter the fixed coverage ledger; a contradictory rank-7-or-later item blocks;
- selected-pair and selected-versus-remainder consistency, conflict, uncertain, malformed IDs/quotes, and invalid `checked_pairs` behave as specified;
- boundary exhaustion of per-batch/aggregate chars, batch count and elapsed time yields `uncertain` without truncation or a cloud ticket;
- conflict pages show both exact sides read-only, single-side prepare is rejected, and source/index/reviewer changes invalidate confirmation;
- rejected passage bodies and IDs do not appear in QA preview JSON; cloud payload, history and outbound records contain only selected consistent reviewed evidence.

These are handoff expectations, not developer-run tests. Include direct backend/API attempts against prepare, mock generate, confirmation rebuild, and confirm with a `test-double` reviewer that is not formally qualified; each must remain blocked even when its candidate-only evidence-set result is `consistent`. Also preview under the isolated test assembly, mutate reviewer runtime/protocol/config after preview and after any candidate confirmation fixture, then verify old results/tickets fail closed. Assert there is no real cloud request, no outbound success record, and no newly stored successful answer from blocked calls. The test task owns all executable oracle, registry, fixture, run bundle and execution. Development has not run tests.

## Non-claims

This candidate does not prove reviewer model quality, answerability accuracy, conflict-review accuracy, latency/resource acceptance, formal local QA availability, complete UI acceptance, real browser behavior, real DeepSeek behavior, security-audit completion, release readiness, or Q6_K provenance. Development performed static diff review only and ran no tests. No formal-library data or real DeepSeek request was used. No model, package, or build tool was downloaded, installed, built, converted, or launched.
