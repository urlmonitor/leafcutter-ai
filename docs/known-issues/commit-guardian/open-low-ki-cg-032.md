---
title: "KI-CG-032 — The uniqueness pass's YAML fast path fabricates an id claim for records a full parse rejects"
description: "KI-CG-032 — The uniqueness pass's YAML fast path fabricates an id claim for records a full parse rejects"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-032 — The uniqueness pass's YAML fast path fabricates an id claim for records a full parse rejects

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Renumbered 2026-08-26: filed as `KI-CG-016` in PR #575, now `KI-CG-032`.** That number was
> already taken on `origin/main` by the `enforce_commit_delegation` entry above. The id was
> allocated by grepping a stale checkout and taking the max, and that copy stopped at
> `KI-CG-014` — `015`-`020` were already landed. The original `KI-CG-016` keeps its number: it
> was there first and is cited from `changelogs/2026-08-25-2312-*.md`. This entry is hours old
> and had exactly one inbound citation, repointed in the same commit.
>
> This is the fourth id collision in this register in two days and the second caused by
> allocating against a snapshot — the defect `KI-BO-028` describes, committed in the register
> that documents it.

- **Severity:** medium
- **Status:** open — **the code is on `main`**: PR #495 merged as `e429421e`
  (`feat(commit-guardian): whole-collection uniqueness pass ... (GE-122)`). The defect shipped
  with it and is still present (re-verified 2026-09-25, see note below).
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `templates/scripts/commit_guardian/_uniqueness_scanners.py:396-487` —
  `_fast_scan_top_level_id()`, against `_read_yaml_id()`'s contract

**Symptom.** `_read_yaml_id`'s contract is that an unparsable record yields **no** claim. The
fast path validates only the `id:` line and its immediate successor, and the caller falls back
to the full parse **only when the fast path returns `None`** — so a wrong non-`None` answer is
never corrected. Any YAML syntax error *after* the `id:` line produces a fabricated claim.

**Reproduced end-to-end** with the most realistic shape, an unquoted value containing a colon:

```yaml
id: GE-500
title: Fix: the parser      # -> yaml.ScannerError
```

`scan_acceptance_criteria` returns `passed=False` with the finding
`GE-500 claimed by [a_malformed.yaml, b_legit.yaml]`. Under the contract there is exactly one
claimant and no collision at all. **The author is blocked with a duplicate-id message when the
real fault is a YAML syntax error somewhere else** — so the diagnostic points at the wrong file
and the wrong problem. A fuzz comparison of the two paths diverged on 6 of 24 inputs; the others
were `- foo` after a mapping, tab indentation, an unclosed flow sequence, an undefined alias,
and `...\t` / `....` as a last line.

**Latent today, and the reason it is latent is itself the concern.** Audited against all 3,097
real AC files: **zero divergences**. But 3,096 of the 3,097 are answered by the fast path — the
full-parse safety net runs exactly once across the entire store. The fallback is not a
meaningful second opinion; it is unreachable in practice.

**Do not fix this with another token special-case.** Rounds 4, 5 and 6 of this PR's review each
added one, and rounds 4-6 each introduced the defect the next round found. The two durable
options are: have the fast path bail whenever any non-blank line it did not positively classify
appears after the `id:` line, or accept the divergence deliberately and re-scope the documented
contract so callers stop being promised a guarantee the fast path does not provide.

**Confirmed NOT broken, so nobody re-opens it:** the document-end token `...` is handled
correctly — lone trailing, with a trailing space, with a trailing comment, and with no trailing
newline all agree with the full parse. That round-6 fix is sound.

*Minor, same file:* `_is_document_boundary_token:311` hardcodes `raw_line[3]` and
`len(raw_line) > 3` rather than deriving from `len(token)`. Correct only because both tokens
happen to be three characters.

**Pattern:** an optimisation whose fallback is the correctness guarantee, and which answers
often enough that the fallback never runs.

**Re-verified 2026-09-25 (still open).** The original Status said the code was "not on
`main`" on unmerged PR #495. That is stale: #495 merged as `e429421e`, which is the only commit
touching `templates/scripts/commit_guardian/_uniqueness_scanners.py` on `main`. The `Where` line
refs (`_fast_scan_top_level_id` at 396-487, `_is_document_boundary_token` hardcode at 311) still
match. A probe against `main` (`d2fe85a1`) reproduced the defect:

- `id: GE-500` / `title: Fix: the parser`: `yaml.safe_load` raises `ScannerError`, but
  `_fast_scan_top_level_id` returns `GE-500`. `scan_acceptance_criteria` returns
  `passed=False`, with `GE-500` claimed by `[a_malformed.yaml, b_legit.yaml]`.
- The fast path still returns an id where the full parse fails for `- foo` after a mapping
  (`ParserError`), an unclosed flow sequence (`ParserError`), and an undefined alias
  (`ComposerError`).
- Tab indentation on the following line now declines (returns `None`) and agrees with the
  full parse.

---
