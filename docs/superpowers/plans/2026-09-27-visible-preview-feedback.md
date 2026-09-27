# BUG-V11-002 Visible Preview Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local source-preview requests visibly responsive, accessible, race-safe, and explicit about the retrieval mode actually used.

**Architecture:** Preserve the existing local preview endpoint and privacy filtering. Add retrieval metadata at the embedding boundary, pass it through the answer context, then manage the browser interaction with a request sequence, an adjacent live region, and a focusable result heading.

**Tech Stack:** Python 3 standard library, vanilla JavaScript, semantic HTML, CSS.

**Spec:** `docs/superpowers/specs/2026-09-27-visible-preview-feedback-design.md`

## Global Constraints

- Development must not edit or commit `docs/testing/`, `docs/audit/`, or `docs/acceptance/`.
- Development does not execute the independent functional test suite; the fixed commit is handed to the existing test task.
- Previewing sources stays local and must not create an outbound record or call DeepSeek.
- Existing privacy filtering and per-request confirmation invalidation remain in place.
- Stale preview responses must not overwrite a newer question, result, live status, or confirmation state.

---

### Task 1: Report the retrieval mode used by one preview request

**Files:**
- Modify: `pkb/embedding.py`
- Modify: `pkb/answers.py`

**Interfaces:**
- Produces: `Embeddings.search_with_mode(query, tag='', since='', until='') -> (items, retrieval)` where `retrieval` is `{'mode': str, 'reason': str}`.
- Preserves: `Embeddings.search(...) -> items` for the document-search endpoint.
- Produces in answer context: `retrieval.mode` in `semantic`, `keyword`, or `keyword_fallback`, plus a short user-facing `retrieval.reason`.

- [ ] **Step 1: Separate result generation from the compatibility wrapper**

Move the existing search body into `search_with_mode`. Keep `search` as:

```python
def search(self, query, tag='', since='', until=''):
    items, _ = self.search_with_mode(query, tag, since, until)
    return items
```

- [ ] **Step 2: Return exact per-request mode metadata**

Use these stable results:

```python
if not self.port or not query.strip():
    return lexical, {
        'mode': 'keyword',
        'reason': '本地语义模型尚未启用，本次仅使用关键词检索。',
    }
```

Return `semantic` after a successful vector request and `keyword_fallback` from the existing exception branch. Do not include exception strings, ports, paths, or model hashes in `reason`.

- [ ] **Step 3: Pass retrieval metadata through the preview context**

In `Answers.context`, replace the direct search iteration with:

```python
items, retrieval = self.embeddings.search_with_mode(question)
for item in items:
    # existing privacy and source-budget logic remains unchanged
```

Add `'retrieval': retrieval` to the returned context without changing source filtering or payload construction.

- [ ] **Step 4: Review compatibility and security boundaries**

Confirm by code inspection that `/api/documents` still consumes a list from `search`, preview reasons contain no internal values, and the preview path has no cloud-provider call.

### Task 2: Add adjacent accessible status and race-safe result navigation

**Files:**
- Modify: `pkb/static/index.html`
- Modify: `pkb/static/app.js`
- Modify: `pkb/static/style.css`

**Interfaces:**
- Produces: `#preview-status` live region associated with `#preview-answer` and `#answer-result`.
- Produces: `focusPreviewResult(title)` to focus and reveal the latest result heading.
- Produces: `previewRequestSequence` integer used to discard stale responses.

- [ ] **Step 1: Add semantic status markup**

Place this immediately after the answer action buttons and before `#answer-result`:

```html
<p id="preview-status" class="hint preview-status" role="status"
   aria-live="polite" aria-atomic="true"></p>
<div id="answer-result" aria-live="off"></div>
```

Add `aria-describedby="preview-status"` and `aria-controls="answer-result"` to the preview button.

- [ ] **Step 2: Add focus and motion helpers**

Implement:

```javascript
function focusPreviewResult(title) {
  title.tabIndex = -1;
  title.focus({preventScroll:true});
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  title.scrollIntoView({behavior:reduceMotion?'auto':'smooth',block:'start'});
}
```

- [ ] **Step 3: Render a result heading and mode explanation**

Change `renderSelectable(data)` to prepend an `h3`. Use “可用片段” when sources exist and “没有检索到可用资料片段” otherwise. For `keyword` or `keyword_fallback`, append `data.retrieval.reason`; when no sources exist, also append “请尝试资料标题、代号或关键词。” Keep existing privacy, checkbox, memory, and local-only copy.

- [ ] **Step 4: Replace the generic preview click wrapper with a dedicated state machine**

Track `let previewRequestSequence = 0;`. On click:

```javascript
const sequence = ++previewRequestSequence;
const question = $('question').value.trim();
```

For an empty question, update the nearby status and focus `#question` without calling the API. Otherwise invalidate the confirmation, disable the button, set `aria-busy="true"`, change its text, and request the preview. Before every success, error, or `finally` UI write, require both `sequence === previewRequestSequence` and the current trimmed question to equal `question`.

On success, render the result, set a count-aware live message, and call `focusPreviewResult`. On failure, render an `h3` titled “无法查看可用片段” plus a concise error paragraph, update the live region, and focus the heading. Restore the button only for the current request.

- [ ] **Step 5: Invalidate pending preview UI on question edits**

In the existing question `input` listener, increment `previewRequestSequence` before clearing `answerPreview` and invalidating the confirmation. Clear stale preview status so an old completion is not announced for the new question.

- [ ] **Step 6: Add restrained status styling**

Give `.preview-status` a stable minimum height and small top margin. Add result-heading scroll margin. Under `prefers-reduced-motion: reduce`, disable smooth scrolling behavior at the CSS level as a defensive complement to JavaScript.

- [ ] **Step 7: Review the browser flow without running the test role's suite**

Inspect the final event sequence for empty input, success, no match, API error, input changes during a request, and a late stale response. Confirm every branch restores only the current button state and no branch calls a cloud endpoint.

### Task 3: Record the development fix and hand off a fixed commit

**Files:**
- Modify: `docs/development-status.md`
- Modify: `docs/development-testing-handoff.md`
- Create: `docs/deliveries/BUG-V11-002-development-fix.md`

**Interfaces:**
- Produces: one fixed Git commit identifier for independent testing.
- Consumes: `docs/acceptance/BUG-V11-002.md` without editing that file.

- [ ] **Step 1: Document root cause and final behavior**

Record that the endpoint succeeded but the result was written below the viewport, errors used only the global notice, and no request-level retrieval mode or race guard existed. List the new live status, focus/scroll behavior, mode metadata, and stale-response protection.

- [ ] **Step 2: State unchanged safety boundaries**

Record that privacy exclusion, selected-source confirmation, one-time confirmation invalidation, local-only preview, and zero real DeepSeek calls are unchanged.

- [ ] **Step 3: Review the exact diff**

Inspect only the planned product and development-document files. Ensure `docs/testing/`, `docs/audit/`, and `docs/acceptance/` remain untracked and unstaged.

- [ ] **Step 4: Commit the fixed candidate**

Stage only:

```text
pkb/embedding.py
pkb/answers.py
pkb/static/index.html
pkb/static/app.js
pkb/static/style.css
docs/development-status.md
docs/development-testing-handoff.md
docs/deliveries/BUG-V11-002-development-fix.md
docs/superpowers/plans/2026-09-27-visible-preview-feedback.md
```

Commit with `fix: make source preview feedback visible` and report the full hash to the test task.

- [ ] **Step 5: Request independent testing**

Ask the test task to cover long pages, mouse and keyboard flows, live-region/focus behavior, empty input, keyword no-match guidance, semantic failure fallback, API errors, duplicate and stale requests, `BL-2026`, prohibited red-fox data, confirmation invalidation, cancellation, outbound row count 0, and no real DeepSeek request.
