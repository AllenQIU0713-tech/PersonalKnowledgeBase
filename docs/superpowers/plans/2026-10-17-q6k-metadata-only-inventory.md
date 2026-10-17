# Q6_K Metadata-only Inventory Plan

> **For agentic workers:** Execute inline. Development gathers metadata and performs static consistency checks; independent testing and audit remain in their assigned chats.

**Goal:** Extend Q6_K approval preparation with exact authoritative artifact metadata while preserving `approval_blocked`.

**Architecture:** Gather only official JSON, index HTML, plain text checksums, PEP 658 metadata sidecars and artifact HEAD headers. Bind every receipt to its URL, retrieval time, byte count and digest. Produce a candidate dependency graph for CPython 3.12/macOS arm64 and explicitly retain unresolved provenance/toolchain/budget gates.

**Tech Stack:** Existing system Python and its installed pip-vendored packaging parser; no installation or package artifact transfer.

**Spec:** `docs/superpowers/plans/2026-10-11-s2-q6k-controlled-comparison.md`, `docs/audit/S2-q6k-non-download-preparation-review-20261017.md`.

## Global Constraints

- Preserve product candidate `391baf9db5afcffd8e2de4ba65782a05b6426a98`; do not modify product code, test oracles, run bundles or audit conclusions.
- No GET for wheels, model weights, source archives, installers or executable files; no installation, build, conversion, model launch or product tests.
- Use fixed llama.cpp commit `7fe450e19305b828c199d602c23a8337aaa1f03b` and its local `gguf-py==0.19.0`; include its build-system dependencies and exclude PyPI gguf.
- Report declared metadata separately from installed-file verification. Missing size/hash/license/closure or runtime provenance remains an approval blocker.

## Task 1: Record metadata and candidate dependency closure

**Files:** Create `docs/development/S2-q6k-metadata-v2/` with a metadata-only collector, raw text/JSON receipts, candidate inventory and stdout/stderr.

- [ ] Read exact fixed requirements/gguf build metadata; collect torch from the declared CPU index and other packages explicitly from PyPI to avoid index ambiguity.
- [ ] Resolve candidate versions using exact wheel compatibility and target markers, reading dependencies from each selected wheel's verified PEP 658 sidecar; reject missing sidecars and direct URLs.
- [ ] Record exact URL/index/name/tags/size/SHA, source-declared license, active dependency edges and exclusions. Do not represent the result as audit approval or install it.

## Task 2: Toolchain metadata and audit handoff

**Files:** Create `docs/development/S2-q6k-metadata-v2/status.md` and inventory JSON. Preserve old preparation records.

- [ ] Read official CMake checksums/release metadata and Python release metadata; distinguish supported runtime selection from older binary availability.
- [ ] Record installed runtime path as an observation, with provenance pending unless independently backed by original source metadata.
- [ ] Sum only exact confirmed items and list unknown source/runtime/budget items without inventing totals.
- [ ] Perform static document/digest checks only; commit developer-owned materials and send fixed identity and remaining gaps to audit and design/coordination chats.
