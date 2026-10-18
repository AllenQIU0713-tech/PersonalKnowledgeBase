# S2R4 HTTP Readiness Implementation Plan

> Execute inline in the developer chat. Independent testing/audit owns execution and oracle changes; development runs no tests.

**Goal:** Align typed evidence-readiness failures with the explicit HTTP 409 contract while retaining request validation HTTP 400 and structured preview responses.

**Spec:** `docs/superpowers/specs/2026-10-18-s2r4-http-readiness-contract.md`, product decision commit `787b51f`.

**Architecture:** Preserve all readiness checks and exception types. In `pkb/server.py`, import `EvidenceUnavailable` and catch it together with `SemanticUnavailable` before the generic validation branch. Preserve the existing 409 JSON error/semantic status structure. All other product files remain byte-identical to candidate 391baf9.

## Constraints

- Preserve fixed `391baf9db5afcffd8e2de4ba65782a05b6426a98` and S2R4 v1's failures/not_run and evidence identities.
- Do not alter test oracle, threshold, model, reviewer qualification, runtime, UI, routes, context selection or confirmation policy.
- `EvidenceUnavailable`/`SemanticUnavailable` escaping Handler become 409; normal ValueError/TypeError/UnicodeError stay 400. Returning a structured unavailable preview is still HTTP 200. Private functions do not gain HTTP endpoints.
- Semantic browse retains its existing GET route, as recorded in fixed product contract 787b51f. No new POST browse route is added.
- No tests, browser/model startup, downloads, formal-data reads or cloud requests in this chat.

## Steps

- [x] Confirm current/history exception-to-status mapping and bind the product contract.
- [x] Apply exactly the necessary import and typed `except` tuple in `pkb/server.py`.
- [x] Review the static diff: no other product-code changes; generic400, authentication, preview, browse and qualification code remain intact.
- [x] Commit a new immutable code candidate; generate the full pkb Git-blob SHA-256 source closure and a concise historical/current HTTP mapping handoff.
- [x] Deliver the fixed candidate to independent test and audit chats. New execution uses a new profile/package/witness; prior successful results keep their original SHA.
