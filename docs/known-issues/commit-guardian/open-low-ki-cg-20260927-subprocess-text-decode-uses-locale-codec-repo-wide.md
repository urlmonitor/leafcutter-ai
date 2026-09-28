---
title: "KI-CG-20260927-subprocess-text-decode-uses-locale-codec-repo-wide — 212 subprocess calls under scripts/ and templates/scripts/ decode child output with text=True and no encoding, so on Windows UTF-8 git content is read as cp1252: mostly silent mojibake, sometimes a crash"
description: "medium — a sweep entry. The pattern has been fixed one file at a time (check_ac_governance ACS-400e-5; test_doc_length_blocking_ratchet on feature/windows-portable-tests) while 123 sites remain in commit-guardian scripts alone. Names the content-reading hooks most at risk."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260914-contract-guard-crashes-on-diff-bytes.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-20260914-build-crashes-on-a-cp1252-stdout.md
---

# KI-CG-20260927-subprocess-text-decode-uses-locale-codec-repo-wide — 212 subprocess calls under scripts/ and templates/scripts/ decode child output with text=True and no encoding, so on Windows UTF-8 git content is read as cp1252: mostly silent mojibake, sometimes a crash

- **Severity:** medium. Each confirmed instance so far has been either a false block or a crash on Windows only. Most sites read ASCII-only output (paths, SHAs, branch names) and are harmless in practice. The risk is concentrated in the handful of sites listed below.
- **Status:** open — no AC. This is a sweep entry: counts are from an AST scan, and the sites listed as riskiest were read in code. Each site's actual failure has not been reproduced individually.
- **Occurrences:** 3 instances confirmed and fixed or filed one at a time: `check_contract_shrinking.py` (`KI-CG-20260914-contract-guard-crashes-on-diff-bytes`, still open), `check_ac_governance.py` (ACS-400e-5, `a1dfb37e`), and `unit_tests/.../test_doc_length_blocking_ratchet.py` (fixed on `feature/windows-portable-tests`, 2026-09-25)
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-25
- **Where:** repo-wide; see the count and the list of riskiest sites below.

## Mechanism

`subprocess.run(..., text=True)` with no `encoding=` decodes the child's pipe with
`locale.getpreferredencoding()`, which is cp1252 on a default Windows install. `PYTHONIOENCODING`
does not change this. Git emits file content, diffs and commit messages as UTF-8. cp1252 leaves only five
byte values undefined (`0x81 0x8D 0x8F 0x90 0x9D`), so the usual result is **silent mojibake**
(`—` becomes `â€"`), not an exception. A crash happens only when one of those five bytes appears,
as it did for `…`-heavy merge diffs in KI-CG-20260914. Mojibake is the worse case for a hook that
compares HEAD content with the working tree: the working-tree read uses `encoding="utf-8"` and the
HEAD read does not, so non-ASCII text looks changed. That is exactly what ACS-400e-5 fixed in one hook.

## Evidence — the count (AST scan, tracked files only, 2026-09-27)

| Tree | Calls with `text=True`/`universal_newlines=True` and no `encoding`/`errors` | Files |
|---|---|---|
| `templates/scripts/` | 154 | 73 (123 calls in 67 files under `commit_guardian/`) |
| `scripts/` (tracked, non-template) | 58 | 30 |

About 85% of the calls invoke `git`. Most read `--name-only`, `rev-parse` or `status` output, which is ASCII in practice.

## Evidence — riskiest sites (read content, not names)

- `templates/scripts/commit_guardian/check_presence_only_assertions.py:110` runs a full `git diff --cached`. This is the same shape as the contract-guard crash, so it is expected to fail on large merges.
- `check_contract_shrinking.py:352` is still unfixed; tracked by KI-CG-20260914.
- HEAD-vs-working-tree comparisons, the ACS-400e-5 shape: `doc_validators.py:145` (`git show HEAD:`), `_ac_pattern_deletion_guard.py:100`, `check_ac_pattern_refs.py:329`, and the fallback path of `check_ac_schema.py:288`. The batch path at `:168` already reads bytes.
- Content diffs: `doc_validators.py:378`, `check_infra_docs.py:103` (`-U0`), and `check_adr_coverage.py:70`, `:131`, `:154`.
- Index reads of the registry: `hooks/check_agent_spawn_consistency.py:77` and `hooks/check_agent_verification_consistency.py:79` (`git show :0:config/agent_registry.json`). The registry currently holds 42 non-ASCII bytes. They decode as mojibake without crashing, and agent ids are ASCII, so this is low risk today.
- Child stdout: `hooks/check_ac_done_on_merge.py:150` runs `mark_ac_done.py` and captures its text output.

## Fix direction

- One helper, for example `_run_git_text(args, **kw)` in `commit_guardian/`, that always passes `encoding="utf-8", errors="replace"`. Migrate the content-reading sites above first, then the rest mechanically.
- A lint gate: an AST check (the scan above, about 30 lines) that fails on `subprocess.*(text=True)` without `encoding`, scoped to `templates/scripts/` and ratcheted like `check-file-size`, so the count can only go down.
- A Windows regression test: stage a file containing `…` and `—`, and run each content-reading hook as a subprocess with `PYTHONIOENCODING` removed. Assert a verdict with no traceback and no false "changed" report.

**Pattern:** a platform default that is correct on the CI platform and wrong on the developer's, fixed one symptom at a time while the count stays put.
