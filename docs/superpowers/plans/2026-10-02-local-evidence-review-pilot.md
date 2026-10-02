# Local Evidence Review Pilot Implementation Plan

> **For agentic workers:** Execute this plan inline in the development task. The user has assigned functional, browser, regression, and model-quality testing to a separate task, so this plan contains development build/static checks and a fixed handoff rather than tests in this checkout.

**Goal:** Deliver two truthful, versioned local evidence-review adapters and an isolated measurement entry point for the S2 comparison without enabling production question answering.

**Architecture:** Candidate A is a small persistent C++ process linked to the installed llama.cpp library; it applies Qwen's official causal reranker prompt and returns the raw final-token `yes` and `no` logits plus their two-class normalized score. Candidate B calls a separately started loopback llama-server with a constrained JSON schema, then rejects every response that is not structurally valid or whose supporting quotations are not contiguous substrings of the supplied passage. A Python measurement CLI applies the shared business-identifier gate, hashes all inputs and configuration, records bounded diagnostics, and never opens the production database.

**Tech Stack:** Python 3.9+ standard library, C++17, llama.cpp 0.5.0 shared library and loopback server, GGUF models.

**Spec:** `docs/superpowers/specs/2026-10-02-local-evidence-review-pilot-design.md`

## Global Constraints

- Keep the formal application in `calibration_required`; do not activate natural-language answering or a reviewer cache.
- Candidate A must use the official fixed template and actual `yes`/`no` token logits; generated text and llama.cpp's generic rerank endpoint are not substitutes.
- Candidate B runs Qwen3-4B-Instruct-2507 in non-thinking mode and accepts only strict `supported` JSON with at least one nonempty quotation found verbatim in the actual passage.
- Process at most 40 candidates, without an uncalibrated cosine acceptance threshold and without candidate-specific lexical rules.
- Apply the model-independent complete business-identifier gate after NFKC/casefold normalization; all identifiers in the query must occur as complete identifiers in the candidate.
- Reject invalid output, timeout, incompatibility, oversized input, and hallucinated quotation without retries or fallback to the other candidate.
- Use isolated fixture files only. Do not open the formal SQLite database, read unrelated personal data, contact DeepSeek, or download/update models during a query.
- Bind every measurement row to question/evidence hashes, qualification and content versions, model digest, quantization, prompt/config versions, and pipeline version.
- Keep questions and passage bodies out of ordinary logs and report metadata; raw synthetic fixture outputs belong only in the explicitly selected measurement file.
- Functional, browser, model-quality, performance, privacy, and regression testing belongs to the independent testing task.

---

### Task 1: Freeze provenance and interfaces

**Files:**
- Create: `pkb/evidence_review.py`
- Modify: `docs/THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Produces: fixed model digests, prompt/config/pipeline versions, `ReviewInput`, `ReviewResult`, `business_identifier_gate()`, and deterministic binding hashes.
- Consumes: the exact model source revisions and file digests recorded during authorized preparation.

- [ ] Record upstream revision, quantized artifact revision, SHA256, file size, license, runtime version, and conversion provenance for each candidate.
- [ ] Define immutable input limits and version strings; include them in a stable SHA256 configuration signature.
- [ ] Implement the generic business-identifier extractor using the existing S1 grammar and require the candidate to contain every identifier in the query.
- [ ] Ensure result metadata contains hashes and versions rather than persisted question/passage text.

### Task 2: Implement truthful Qwen3 reranker logits

**Files:**
- Create: `scripts/qwen-reranker-logits.cpp`
- Create: `scripts/build-reranker-logits.sh`
- Modify: `pkb/evidence_review.py`

**Interfaces:**
- Consumes: one tab-separated line containing hexadecimal UTF-8 query, title, and body.
- Produces: one bounded JSON object with `yes_logit`, `no_logit`, normalized `score`, and token count.

- [ ] Load the fixed GGUF once with llama.cpp, restrict the context, and reject an input that does not fit instead of truncating it.
- [ ] Tokenize the official prefix/body/suffix with special-token parsing and verify that lowercase `yes` and `no` are each exactly one token.
- [ ] Clear model memory between candidates, evaluate the full prompt, read final-position logits, and normalize only the two required logits.
- [ ] Add a Python process adapter that validates the exact output schema, finite numeric values, score range, process lifetime, model digest, and one-response-per-request behavior.
- [ ] Build the executable as a development check without running model inference.

### Task 3: Implement strict 4B instruction review

**Files:**
- Modify: `pkb/evidence_review.py`

**Interfaces:**
- Consumes: a fixed loopback llama-server port plus `ReviewInput`.
- Produces: `ReviewResult` containing the validated verdict and quotation offsets, or a closed failure reason.

- [ ] Build the fixed system/user messages that treat the passage as untrusted data and request entity/attribute/event/relationship/batch answerability.
- [ ] Send one low-randomness request to `127.0.0.1` with proxy and redirects disabled, a strict JSON schema, bounded output, and no tools.
- [ ] Reject non-JSON, extra or missing fields, invalid verdicts/types, oversized responses, empty quotations, and any quotation that is not a contiguous substring of the supplied body.
- [ ] Accept structurally only `supported` with verified quotation offsets; never use self-reported confidence and never retry or repair output.

### Task 4: Add isolated comparison measurement CLI

**Files:**
- Create: `pkb/review_measure.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: an explicit JSON dataset with passages and queries, candidate selection, fixed model file/digest, and either the reranker executable or loopback port.
- Produces: a JSON report with dataset/config hashes, per-pair raw candidate outputs, hard-gate decisions, latency, and version bindings.

- [ ] Validate the whole input schema, maximum 40 candidates per query, unique IDs, character limits, and explicit content/qualification versions before starting a model.
- [ ] Hash the dataset bytes and every question/evidence payload; preserve raw logits or strict verdict/quotes only in the requested report.
- [ ] Run one candidate only, preserve stable input order, count errors as rejected results, and avoid threshold selection or quality claims.
- [ ] Document exact build/start/measure commands, fixed loopback addresses, isolation requirements, and the fact that the CLI never reads the production data directory.

### Task 5: Create fixed development handoff

**Files:**
- Create: `docs/deliveries/S2-local-evidence-review-pilot.md`

**Interfaces:**
- Produces: commit-specific instructions for the independent testing and audit tasks.

- [ ] Run Python bytecode compilation, shell syntax, C++ compilation, and `git diff --check`; do not run either model or any functional/model-quality test.
- [ ] Record the exact commit, model paths/digests, runtime/build provenance, isolation commands, output locations, and remaining `calibration_required` state.
- [ ] Explicitly list the unperformed checks delegated to independent testing and audit, including real retrieval, 36-question blind set, 40-candidate resource measurement, loopback evidence, and `cloud_requests=0`.
- [ ] Commit only implementation, plan, README, notices, and delivery files; leave testing, audit, and acceptance evidence untracked and untouched.
