---
title: "KI-CG-20261014-doc-length-gate-crashes-instead-of-reporting — check-doc-length has two paths that end in a Python traceback rather than a stated outcome: a set-aside document that matches no declared entry raises StopIteration, and a commit_guardian.json that is not valid UTF-8 raises UnicodeDecodeError past the DECLARATION PROBLEM report"
description: "low — (a) matching_entry() in _doc_length_set_aside.py is a bare next() over the declared entries, and render_population_report's caller catches only CurrentLengthUnmeasurableError, so a document the membership test calls set aside but no single entry matches crashes the gate. Unreachable with today's is_excluded, but two deliberate gate mutations during GE-127g-3 verification reached it, so any future change that lets membership and matching_entry disagree crashes the gate on every commit that stages such a document. (b) config.load_config() turns OSError into FileNotFoundError and re-raises JSONDecodeError, and load_doc_length_settings() catches exactly those two, so a UnicodeDecodeError (a ValueError) escapes at module import: traceback, exit 1, no DECLARATION PROBLEM text. Both still refuse the commit, so neither fails open. Code verified on origin/main 95961b718."
type: reference
category: reference
status: active
created: '2026-10-14'
last_updated: '2026-10-14'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/reference/document-length-standard.md
---

# KI-CG-20261014-doc-length-gate-crashes-instead-of-reporting — two traceback exits in `check-doc-length`

> Filed 2026-10-14 from GE-127g-3 verification. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`).

- **Severity:** low. Both paths refuse the commit (non-zero exit), so neither lets anything through.
  But the refusal is a Python traceback, not the gate's reported outcome. The author is told nothing
  about which document or which declaration is at fault, and a traceback reads as a broken hook, which
  invites `SKIP=check-doc-length`.
- **Status:** open, no AC.
- **Occurrences:** (a) reached twice, by deliberate gate mutations during GE-127g-3 verification on
  2026-10-14, never by an unmodified gate. (b) found by reading the code, not observed.
- **First seen:** 2026-10-14 · **Last seen:** 2026-10-14

## (a) A set-aside document that matches no entry raises `StopIteration`

- **Where:**
  - `templates/scripts/commit_guardian/_doc_length_set_aside.py:210-221` `matching_entry`:

    ```python
    return next(entry for entry in entries if is_excluded(filepath, (entry["path"],)))
    ```

    It has no default, so no match raises `StopIteration`.
  - `_doc_length_set_aside.py:259-260`: `render_population_report` calls it for every set-aside path.
  - `templates/scripts/commit_guardian/check_doc_length.py:464-471`: the call is wrapped in
    `except CurrentLengthUnmeasurableError` only. `main()` is called bare at `:523-524`.
- **Why it is unreachable today.** Membership (`select_set_aside_paths`, `:150-164`) asks
  `is_excluded(filepath, set_aside_paths)` over all paths at once. `matching_entry` asks the same
  function one entry at a time. `is_excluded` (`_doc_length_ratchet.py:246-266`) is a pure "any entry
  matches" loop, so the two agree. Membership paths come from `_SETTINGS.paths` and entries from
  `_SETTINGS.entries` (`check_doc_length.py:65-70`), one read.
- **Why it is still worth recording.** The agreement is a coincidence of two call shapes, not a
  checked invariant. During GE-127g-3 verification, two deliberate mutations of the gate's membership
  rule (made to prove the tests catch a wrong set-aside population) diverged it from
  `matching_entry`, and both produced this traceback rather than a report. Any future change with the
  same effect, such as normalising paths on one side, matching basenames, or adding a second membership
  source, crashes the gate on every commit that stages such a document.

## (b) A `commit_guardian.json` that is not valid UTF-8 escapes as `UnicodeDecodeError`

- **Where:**
  - `templates/scripts/commit_guardian/config.py:41-62` `load_config`: opens the file with
    `encoding="utf-8"` and `json.load`s it. It catches `OSError` (re-raised as `FileNotFoundError`,
    `:51-55`) and `json.JSONDecodeError` (re-raised, `:56-62`). A byte sequence that is not UTF-8 raises
    `UnicodeDecodeError` from the read, which is neither: it is a `ValueError` subclass, and
    `issubclass(UnicodeDecodeError, (OSError, json.JSONDecodeError))` is False.
  - `config.py:210-214`: the doc-length constants are computed at module import, so the error is raised
    by `import config`.
  - `_doc_length_set_aside.py:82-88` `load_doc_length_settings`: catches exactly `FileNotFoundError` and
    `json.JSONDecodeError` around `import config`. Those are the two outcomes that become a classified
    `("read", ...)` or `("interpreted", ...)` problem, rendered as `DECLARATION PROBLEM` by
    `render_declaration_problem` (`:102-113`).
  - `check_doc_length.py:65` calls `load_doc_length_settings()` at module level. So the
    `UnicodeDecodeError` surfaces as an import-time traceback, with exit 1 and no `DECLARATION PROBLEM`
    line. GE-127g-2-i's whole purpose is that an unreadable declaration is said so.

## Detection

A `check-doc-length` run whose output is a traceback ending in `StopIteration` (from `matching_entry`)
or `UnicodeDecodeError` (from `config.py`), rather than a `DECLARATION PROBLEM`, `INDETERMINATE`,
`PASSED` or refusal line.

## Workaround

(a): none needed today. If it appears, the membership rule and `matching_entry` have diverged. Find
the change that did it. (b): re-save `commit_guardian.json` as UTF-8.

## Suggested fix

- **(a)** Give `next()` a default and turn "set aside but no entry matches" into a stated outcome: an
  `INDETERMINATE` (exit 2) naming the document. Better, derive both answers from one function that
  returns the matching entry or `None`, so membership is defined as "has a matching entry" and the
  two cannot disagree. Add a test that monkeypatches membership to diverge and asserts a report, not a
  traceback.
- **(b)** Classify `UnicodeDecodeError` as a read or interpretation failure, either in `load_config`
  (re-raise as the `json.JSONDecodeError` path does) or by catching `ValueError` in
  `load_doc_length_settings`, so it reaches `render_declaration_problem`. Add a test that writes
  non-UTF-8 bytes into a temporary config and asserts the `DECLARATION PROBLEM` text. Other hooks
  that `import config` share the same gap.

**Pattern:** a gate whose stated outcomes are complete only for the failures its author pictured.
Anything else leaves as a traceback.
