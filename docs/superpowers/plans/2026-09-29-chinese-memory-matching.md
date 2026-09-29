# BUG-V11-004 Chinese Memory Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select eligible Chinese memories with deterministic topic, intent, and business-identifier matching while controlling false recall.

**Architecture:** Add pure normalization and scoring helpers to `pkb/memories.py`. Keep qualification and privacy checks in `Memories.eligible()`, score every qualified item, sort deterministically, and only then return the first five.

**Tech Stack:** Python 3 standard library (`re`, `unicodedata`).

**Spec:** `docs/superpowers/specs/2026-09-29-chinese-memory-matching-design.md`

## Global Constraints

- Preserve confirmed/allowed/no-conflict/source-allowed qualification before relevance scoring.
- Do not change offline rendering, cloud payloads, confirmation, endpoints, dependencies, or outbound persistence.
- Do not edit or commit `docs/testing/`, `docs/audit/`, or `docs/acceptance/`.
- Development performs syntax and diff checks; independent testing owns functional regression.

---

### Task 1: Add deterministic local matching helpers

**Files:**
- Modify: `pkb/memories.py`

**Interfaces:**
- Produces: `_compact(text) -> str` for NFKC/casefold Unicode letter-and-number normalization.
- Produces: `_question_text(question) -> str` with one explicit prefix and suffix removed.
- Produces: `_topic_core(topic) -> str` with one longest title suffix removed.
- Produces: `_business_ids(text) -> set[str]` with exact letter-and-digit identifier tokens.
- Produces: `_intent_match(question, anchor, body) -> (coverage_milli, matched_windows)` or `None`.
- Produces: `_relevance(item, question) -> tuple[int, int, int, int]` or `None`.

- [ ] **Step 1: Add normalization constants and helpers**

Import `re` and `unicodedata`. Define the approved prefix, suffix, title-suffix, generic-short-topic, and Unicode-hyphen constants as immutable tuples/sets. Sort variable-length affixes by length at definition time.

`_compact` must retain only characters whose Unicode category begins with `L` or `N`.

- [ ] **Step 2: Normalize one question frame**

`_question_text` calls `_compact`, removes at most one longest approved prefix, then at most one longest approved suffix. It must not remove words from the middle of a question.

- [ ] **Step 3: Derive one topic core**

`_topic_core` removes at most one longest approved trailing title suffix. It never strips `项目` or recursively strips another suffix.

- [ ] **Step 4: Parse exact business identifiers**

Normalize dash variants to `-`, then find boundary-delimited ASCII alphanumeric tokens with optional internal dashes. Keep only tokens of length at least four that contain at least one ASCII letter and one digit. Compare identifier sets for exact equality.

- [ ] **Step 5: Calculate body-intent coverage**

Find one exact normalized topic anchor in the framed question, remove it, then remove at most one adjacent `的`. Reject intent shorter than four. Generate all four-character windows, count unique windows present in normalized body, and return coverage in thousandths only when at least one window and at least 50 percent match.

- [ ] **Step 6: Score one candidate**

Return the highest path among exact identifier, exact full topic, exact topic core, full-topic-plus-intent, and core-plus-intent. Exact 2–3 character topics are allowed only when the query equals the topic, the topic includes a Unicode letter, and it is not in the generic-short set. Fuzzy topic-core paths require a core of at least four characters.

### Task 2: Filter, rank, and cap eligible memories

**Files:**
- Modify: `pkb/memories.py`

**Interfaces:**
- Consumes: `_relevance(item, question)` from Task 1.
- Produces: `Memories.eligible(question) -> list[dict]`, ordered by relevance and capped at five.

- [ ] **Step 1: Preserve qualification before scoring**

For every `self.list()` item, first reject invalid status, privacy, conflict, and source privacy. Only then call `_relevance`.

- [ ] **Step 2: Collect all matching candidates**

Append `(score, item)` for every relevant qualified item. Do not stop when five candidates are encountered.

- [ ] **Step 3: Apply deterministic stable sorting**

Use stable sorts from least to most significant: `id` ascending, `updated` descending, relevance tuple descending. Slice to five only after sorting and return the existing public fields `id`, `topic`, `text`, and `sources`.

- [ ] **Step 4: Review compatibility**

Confirm exact distinctive topics such as `旅行`, `目标`, and `备份` still match themselves; generic short topics and pure numbers do not. Confirm no helper performs I/O or network access.

### Task 3: Record and hand off the fixed candidate

**Files:**
- Modify: `docs/development-status.md`
- Modify: `docs/development-testing-handoff.md`
- Create: `docs/deliveries/BUG-V11-004-development-fix.md`

**Interfaces:**
- Produces: one fixed commit for independent testing.
- Consumes: `docs/acceptance/BUG-V11-004.md` without editing it.

- [ ] **Step 1: Document the root cause and full algorithm**

Record that the previous whitespace split could not match continuous Chinese and that the fix combines normalized topic anchors, four-character body intent coverage, exact business identifiers, deterministic ranking, and post-sort cap.

- [ ] **Step 2: Document unchanged privacy and network boundaries**

State that qualification remains before scoring, offline mock behavior remains local, `cloud_requests` is untouched, and cloud payload/confirmation behavior did not change.

- [ ] **Step 3: Run development checks**

Run `git diff --check` and parse `pkb/memories.py` with Python `compile(...)`. Do not run functional tests in the development task.

- [ ] **Step 4: Commit development-owned files**

Stage only `pkb/memories.py`, development status/handoff, the delivery document, and this plan. Commit with `fix: match continuous Chinese memories`.

- [ ] **Step 5: Request independent testing with the immutable fixture**

Send the exact real topic, body, and question plus all approved positive, negative, identifier-boundary, ordering, cap, privacy, browser, no-network, and full-regression cases to the test task. Require it to call real `Memories.eligible()` rather than construct a context manually.
