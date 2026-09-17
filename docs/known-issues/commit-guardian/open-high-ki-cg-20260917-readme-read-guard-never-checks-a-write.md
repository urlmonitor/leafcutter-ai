---
title: "KI-CG-20260917-readme-read-guard-never-checks-a-write — `readme_read_guard` treats every Write as a trivial edit, because a Write carries no `old_string`/`new_string`"
description: "KI-CG-20260917-readme-read-guard-never-checks-a-write — `readme_read_guard` treats every Write as a trivial edit, because a Write carries no `old_string`/`new_string`"
type: reference
category: reference
status: active
created: '2026-09-17'
last_updated: '2026-09-17'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260917-readme-read-guard-never-checks-a-write — `readme_read_guard` treats every Write as a trivial edit, because a Write carries no `old_string`/`new_string`

> Index: [commit-guardian.md](../commit-guardian.md). Filename severity is the three-level
> index bucket (`high`); the original grading is the `**Severity:**` line below.

- **Severity:** high
- **Status:** open — owning AC `GE-130f`. The guard's other inertness (gated prefixes that
  stop matching through symlinks; `alembic/versions/` absent here) is recorded in `GE-120f`'s
  `doc_links` and notes, not as a known issue. This entry is a third, separate mechanism.
- **Occurrences:** 1 (found by reading the hook, confirmed by probe, 2026-09-17)
- **First seen:** 2026-09-17 · **Last seen:** 2026-09-17
- **Where:** `templates/hooks/readme_read_guard.py:223-230`, the trivial-edit skip; the hook
  is registered as `PreToolUse` on `Edit|Write` in `templates/settings.json`

**Symptom.** The guard exists to refuse an edit in a gated folder (`.claude/agents/`,
`.claude/skills/`, `.claude/hooks/`, `alembic/versions/`) until that folder's nearest README
has been read this session. It is registered for `Write` as well as `Edit`, and it never
refuses a `Write`, however large.

**Mechanism.** The skip runs before any README lookup:

```python
old_string = tool_input.get("old_string", "")
new_string = tool_input.get("new_string", "")
if (
    len(old_string) < TRIVIAL_EDIT_OLD_LEN          # 200
    and abs(len(new_string) - len(old_string)) < TRIVIAL_EDIT_DELTA   # 100
):
    sys.exit(0)
```

A `Write` payload is `{file_path, content}`: no `old_string` and no `new_string`. Both
default to `""`, so the test is `0 < 200 and 0 < 100`, which is always true. Every Write
exits 0 here. A full-file overwrite, the largest change the tool can make, is treated as the
smallest. `docs/reference/claude-code-hooks.md` documents the Write shape as
`{file_path, content}`, so the payload was known.

**Evidence — probe, 2026-09-17.** A throwaway repo in the session scratchpad (`.git/`,
`.claude/hooks/README.md`, no read marker), same 5,000-character body both times, with
`CLAUDE_SESSION_ID=probe`:

```text
Write {file_path: .claude/hooks/x.py, content: <5000 chars>}       -> exit 0
Edit  {file_path: .claude/hooks/x.py, old_string: <5000>, new_string: "b"} -> exit 2
      "readme_read_guard: BLOCKED ... have not read the nearest-ancestor README"
```

The README was unread in both calls. Only the Edit was refused.

**Why high.** The guard is silent in exactly the case it should care about most: a new file
or a rewrite in a gated folder. Its tests and its Edit behaviour both look correct, which
hides this. It also stacks with the `GE-120f` finding: where the prefixes do match, Writes
still pass.

**Fix direction.** Per `GE-130f`, repair before `GE-130a` widens the guard's reach.

- Branch on `tool_name` (or on the presence of `content`): a Write is never trivial, or it is
  measured by `len(content)` against the file's current size.
- Add a test that sends a Write payload to the deployed hook in a gated folder with no marker
  and asserts exit 2. No such test would pass today.

**Related.** `KI-CG-037` (the other guard `GE-130f` repairs), `KI-DS-003` (notes the same hook's `SKIP_LIST` excludes `docs`).

**Pattern:** `docs/reference/false-green-mechanisms.md`: a shortcut that reads absent input
as benign input.

---
