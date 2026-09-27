# BUG-V11-003 Offline Memory Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make offline simulated answers render every eligible source and memory supplied by the existing local context filter.

**Architecture:** Keep `Answers.context()` and `Memories.eligible()` as the sole eligibility boundary. Change only `MockProvider.answer()` to render two independently numbered evidence sections and retain the existing local-only persistence path.

**Tech Stack:** Python 3 standard library.

**Spec:** `docs/superpowers/specs/2026-09-27-offline-memory-evidence-design.md`

## Global Constraints

- Do not change cloud payload assembly, confirmation tokens, DeepSeek transport, memory eligibility, or privacy rules.
- Do not edit or commit `docs/testing/`, `docs/audit/`, or `docs/acceptance/`.
- Development performs syntax and diff checks only; the separate test task owns functional regression execution.
- The offline provider must not perform network access or insert `cloud_requests`.

---

### Task 1: Render source and memory evidence in the offline provider

**Files:**
- Modify: `pkb/answers.py`

**Interfaces:**
- Consumes: `context['sources']`, a list of source dictionaries containing `text`.
- Consumes: `context['memories']`, a list of eligible memory dictionaries containing `topic` and `text`.
- Produces: one plain-text offline simulation string with only non-empty evidence sections.

- [ ] **Step 1: Read both evidence collections**

At the start of `MockProvider.answer`, bind both collections without querying storage:

```python
sources = context['sources']
memories = context['memories']
```

- [ ] **Step 2: Handle the truly empty case**

Return this only when both collections are empty:

```python
'【离线模拟，未调用模型】没有符合当前使用条件的资料片段或个人记忆，无法生成有依据的回答；这不是模型建议。'
```

- [ ] **Step 3: Build independently numbered evidence sections**

Start with:

```python
sections = ['【离线模拟，未调用模型】以下仅展示本次允许使用的本地证据，不是模型建议。']
```

Append a `资料片段：` section only when `sources` is non-empty, formatting each item as `[资料 N] 正文`. Append a `个人记忆：` section only when `memories` is non-empty, formatting each item as `[记忆 N｜主题] 正文`. Join top-level sections with two newlines.

- [ ] **Step 4: Review the data boundary**

Confirm by code inspection that `MockProvider` still has no network dependency, `Answers.generate()` still writes `answer_sources`, `answer_memories`, and one `outbound` row with `simulated=1`, and `cloud_requests` is touched only by the confirmed cloud path.

### Task 2: Record and hand off the fixed development version

**Files:**
- Modify: `docs/development-status.md`
- Modify: `docs/development-testing-handoff.md`
- Create: `docs/deliveries/BUG-V11-003-development-fix.md`

**Interfaces:**
- Produces: one fixed commit for independent testing.
- Consumes: `docs/acceptance/BUG-V11-003.md` without editing it.

- [ ] **Step 1: Document root cause and implementation**

Record that `MockProvider.answer()` ignored already eligible memories and now renders non-empty source and memory sections with separate labels.

- [ ] **Step 2: Document unchanged safety behavior**

State that memory eligibility, privacy filtering, relation tables, simulated outbound records, cloud confirmation, payloads, endpoints, and dependencies did not change.

- [ ] **Step 3: Run development checks**

Run `git diff --check` and parse `pkb/answers.py` with Python `compile(...)`. Do not run the functional regression suite.

- [ ] **Step 4: Commit only development-owned files**

Stage `pkb/answers.py`, the development documents, and this plan. Commit with `fix: include memories in offline answers`. Keep testing, audit, and acceptance evidence unstaged.

- [ ] **Step 5: Request independent regression coverage**

Ask the test task to cover memory-only, source-only, mixed, empty, pending/conflicted/inactive/local/source-restricted memories, topic and body rendering, simulated records, `cloud_requests=0`, no network, UI/history, and cleanup after memory modification or deletion.
