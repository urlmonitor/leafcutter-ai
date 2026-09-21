---
title: "KI-ACS-20260901-1520 — The ticket generator hard-codes `.py` on every test filename, so a browser test is declared as a Python file and the done-proof oracle routes on that extension"
description: "KI-ACS-20260901-1520 — The ticket generator hard-codes `.py` on every test filename, so a browser test is declared as a Python file and the done-proof oracle routes on that extension"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20260901-1520 — The ticket generator hard-codes `.py` on every test filename, so a browser test is declared as a Python file and the done-proof oracle routes on that extension

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1 (28 records affected today; 1 generated ticket already on disk)
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py:1453-1459`, against
  `scripts/ac_store/done_proof.py:1332-1334`

**Symptom.** `generate_ticket_from_ac.py` derives a test's `file` from the AC's `target_dir`
and appends a hard-coded `.py`:

```python
elif target_dir:
    file_path = f"{target_dir}/test_{slug}.py"
```

It does this regardless of what the same `test_spec` entry says its `framework` is. The
generated ticket for `BP-1400c-1-i` is already on disk and reads:

```yaml
- name: test_about_route_smoke
  file: leafcutter-web/tests/test_bp_1400c_1_i.py
  framework: playwright
  type: e2e
```

A Python filename for a headless-browser test — in `leafcutter-web/tests/`, a directory that
does not exist (the app's convention is `__tests__/`).

**Why it is not cosmetic.** `done_proof.py:1332-1334` routes the proof oracle **by file
extension**: `.py` goes to pytest, `.ts`/`.tsx` to vitest. So the wrong filename is not an
unread label — it decides which runner is asked for evidence. A ticket claiming a `.py` file
for a browser test will have pytest asked to prove it, against a path nothing writes.

**Why it is being filed NOW, ahead of the enum widening.** `framework` is currently constrained
to `["unittest", "pytest"]`, so the 28 records carrying `vitest` or `playwright` fail schema
validation — and that failure is presently the only thing drawing attention to this family at
all. Widening the enum (the correct fix, see KI-ACS-010) makes those records **validate**, and
a validating record with a wrong filename looks healthy. Filed first so the louder defect does
not take the quieter one with it when it goes.

**Fix direction.** Derive the extension from the declared framework rather than assuming
Python, and reject rather than guess when the two disagree — a `playwright` entry naming a
`.py` file is a contradiction the generator can see at write time. Note the ordering trap: the
same `test_spec` also names `target_dir`, and `leafcutter-web/tests/` does not exist, so a fix
that only corrects the extension still emits a path nothing will ever write. Both halves are
the same guess.

**Related.** `KI-ACS-010` (the enum this rides behind, and the change that will conceal it).

**Pattern:** `docs/reference/false-green-mechanisms.md` — a defect kept visible only by an
unrelated failure, which disappears when that failure is correctly repaired.

---
