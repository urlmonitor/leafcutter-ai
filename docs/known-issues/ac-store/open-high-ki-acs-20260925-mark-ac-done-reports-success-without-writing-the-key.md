---
title: "KI-ACS-20260925-mark-ac-done-reports-success-without-writing-the-key — mark_ac_done.py replaces the first 'work_status: todo' anywhere in the file, so prose is edited, the real key stays todo, and the tool prints success"
description: "high — the sanctioned done-marker does an unanchored substring replace, then rewrites every line LF to CRLF on Windows; it exits 0 having changed prose instead of the key. approve_acs.py has the same unanchored replace for readiness."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
  - docs/known-issues/build-orchestration/resolved/resolved-high-ki-bo-022.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-ACS-20260925-mark-ac-done-reports-success-without-writing-the-key — mark_ac_done.py replaces the first 'work_status: todo' anywhere in the file, so prose is edited, the real key stays todo, and the tool prints success

- **Severity:** high. The tool CLAUDE.md and `build-ac` name for marking an AC done reports success on a write that did not happen, and silently rewrites prose.
- **Status:** open — no AC. Reproduced 2026-09-25 on scratch copies (including a copy of the real `BO-202.yaml`).
- **Where:** `scripts/ac_store/mark_ac_done.py:164-184`; same pattern in `scripts/ac_store/approve_acs.py:221-222` (`readiness: reviewed`, inferred).

## Symptom

On a record whose `criteria` or `notes` prose contains the literal `work_status: todo` above the real key:

```
$ python scripts/ac_store/mark_ac_done.py --ac-id ZZ-100 ...
marked ZZ-100 work_status=done        # exit 0
```

`yaml.safe_load` afterwards: the prose now reads `work_status: done`, the real `work_status` is still `todo`. On
Windows every line of the file was also rewritten from LF to CRLF (`od -c` shows `\r\n` on every line).

22 records in the store currently carry a `work_status: todo` or `readiness: reviewed` literal in prose before the
real key; `BO-202` is one and is active and `todo`.

## Mechanism

```python
raw_text = ac_file.read_text(encoding="utf-8")
if "work_status: todo" in raw_text:                       # substring, anywhere
    updated_text = raw_text.replace("work_status: todo", "work_status: done", 1)
...
ac_file.write_text(updated_text, encoding="utf-8")        # newline=None -> os.linesep
```

The anchored `re.sub(r"^(work_status:\s*).*$", ..., flags=re.MULTILINE)` exists only as the *fallback* branch. There
is no re-parse to confirm the key changed, and the write is not atomic.

## Fixed here, not there

The fast lane's `_fl_lifecycle._update_ac_work_status` (`scripts/build_orchestration/_fl_lifecycle.py:170-250`)
already solved all three problems: column-0 anchored match, `newline=""` with each line's own ending preserved
(KI-BO-022 fix, #602), atomic write, `ValueError` on ambiguity. None of it reached `mark_ac_done.py`. The same
LF→CRLF rewrite was reproduced in `approve_acs._promote_leaf` and `_gtfa_implemented_by._write_implemented_by`, and
is inferred for `epic_assembly`, `epic_ac_store`, `fix_ac_orphans`, `_xref_apply` and `backfill_readiness`.

## Detection

After any `mark_ac_done` call, re-parse the file and compare `work_status`; `git diff --stat` showing every line
changed on a one-field flip is the CRLF half.

## Fix direction

One shared `ac_record.set_field(path, key, value)`: column-0 YAML-aware match, byte-exact line endings, atomic
write, re-parse verifying the key changed and nothing else did, one typed error. `mark_ac_done`, `approve_acs`, the
fast lane and every other writer import it. Tracked as cluster 1 in the 2026-09-25 duplication analysis.
