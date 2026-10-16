# S2R3 evidence-gate candidate handoff

Status: developer candidate prepared for independent review. This does not enable formal QA, certify any reviewer model, or change `calibration_required`.

## Candidate boundary

- Parent behavior baseline: S2R2 commit `4e8e8cac10452b5e0b565902bd191acba90dd26f`; that commit is unchanged.
- Candidate commit: `9a5596e40c8904b42bd6f019de8e88a73f83decc`.
- New pipeline version: `s2r3-evidence-gate-v1`.
- Production `server.py` constructs `Answers` without an evidence pipeline. Answer preview therefore reports `blocked_by_missing_reviewer`; cloud preparation and mock answer generation cannot bypass that state.
- Local semantic browsing remains on the separate `/api/documents/semantic-search` path.

## Test injection seam

`Answers(..., evidence_pipeline=...)` accepts an explicitly constructed `EvidencePipeline`. The test task must provide its own deterministic reviewer double, configured only against the isolated synthetic fixture. The reviewer receives one `ReviewInput` at a time and must return the existing evidence-review result shape with matching `question_sha256`, `evidence_sha256`, passage ID, content version, qualification version, `config_signature` equal to the injected fixed reviewer signature, a `supported` verdict, and verbatim `evidence_quotes`. A double must never be configured by production startup or read real library data.

`EvidencePipeline.review()` consumes at most 40 eligible semantic candidates. It rejects business-identifier mismatches before the reviewer, rejects non-supported verdicts and invalid quotes, and makes reviewer runtime/configuration failures unavailable. Only supported, quote-bearing passages can enter the 6-source, 2-per-document, 6000-character reviewed context. The quote must remain intact in the emitted source.

## Independent test scope

The tester should build a new immutable run bundle under the product's test-freeze contract and check at least:

- missing reviewer blocks QA and does not create an outbound confirmation;
- injected synthetic reviewer accepts a valid exact quote and preserves its source/version metadata;
- insufficient, mismatch, uncertain, business-ID mismatch, malformed result, forged quote, and runtime failure fail closed;
- passage/document and total context limits are enforced without dropping the required quote;
- cloud preparation accepts only reviewed chunk IDs and confirmation rebuild rejects changed reviewer/pipeline/evidence snapshots;
- source qualification/index changes invalidate the reviewed preview;
- local semantic browse continues independently.

This list describes developer-visible interfaces and expected coverage; the test task owns the executable oracle, registry, fixtures, and run manifests. Development did not run the test suite.

## Non-claims

This candidate does not prove reviewer quality, answerability accuracy, model calibration, formal local QA availability, full UI acceptance, real browser behavior, real DeepSeek behavior, cloud consent correctness end to end, security audit, release readiness, or Q6_K provenance. No formal-library data or real DeepSeek request was used. No model, package, or build tool was downloaded, installed, built, converted, or launched.
