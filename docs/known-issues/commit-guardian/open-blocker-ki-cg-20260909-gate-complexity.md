---
title: "KI-CG-20260909-gate-complexity — `check-complexity` judges every function absolutely, so registering it refuses 49 existing files including the two most-edited in the repo"
description: "high (as a blocker to registration) — the gate itself is dormant and harms nothing today."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260909-gate-complexity — `check-complexity` judges every function absolutely, so registering it refuses 49 existing files including the two most-edited in the repo

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high (as a blocker to registration) — the gate itself is dormant and harms nothing today.
- **Status:** open — no AC. Needs its own session.
- **Occurrences:** measured once, `df1f0cfb5`. · **First seen:** 2026-09-09 · **Last seen:** 2026-09-09
- **Where:** `templates/scripts/commit_guardian/check_complexity.py:197` (`main`), `:130` (`process_staged_file`); limit `MAX_COMPLEXITY_SCORE = 15` from `config.py`.

**The numbers.** 49 of 915 tracked `.py` files contain at least one function over 15. Worst: `scripts/ac_store/generate_ticket_from_ac.py` (75), `scripts/build_helpers.py` (65), `scripts/build.py` (44), `scripts/knowledge_query.py` (44), `scripts/build_referential_integrity.py` (41), `scripts/build_phases.py` (39), `templates/scripts/commit_guardian/check_ac_governance.py` (46), `scripts/build_orchestration/fast_lane.py` (26). Excluded dirs are only `alembic` and `legacy`.

**Why it cannot be registered as-is.** `main()` recomputes each staged file's scores from current content and refuses on any over-limit function. There is no reference to `HEAD` anywhere in the module. So the refusal is not "you made this worse" — it is "this file contains an old offender", which blocks an unrelated docstring fix, and blocks the very commit that would start decomposing the offending function. `build.py` and `fast_lane.py` being on the list means routine work stops.

**Ratchet shape — NOT `check-file-size`'s.** Line count is one scalar per file; complexity is a score *per function*, so there is no single number to compare. Two workable designs, cheapest first: (a) per-file count of over-limit functions must not increase versus `HEAD` — simple, robust to renames within a file, but permits swapping a 16 for a 75; (b) per-function comparison keyed by qualified name, refusing a new over-limit function or an increase in an existing one — accurate, but needs a name-matching story for renamed/moved functions. Start with (a); it is strictly better than today and does not need the rename story.

**Definition of done.** All 49 files remain committable and editable; a NEW function over 15, or an existing one made worse, is refused; the gate is registered. Prove the second clause with a mutation test, not a grep.

**Re-verified 2026-09-23: STILL TRUE — unchanged in mechanism, kept open.** `check-complexity`
is still absent from `hooks_manifest.hooks` and still carried only in the `declared_non_gates`
catalogue:

```
$ grep -n '"id": "check-complexity"' templates/scripts/commit_guardian/commit_guardian.json
(no match)

$ python3 templates/scripts/commit_guardian/check_hook_trigger_reachability.py   (run from repo root)
DECLARED-NON-GATE: check_complexity.py ground=BP-100n-4 correction: FUNCTIONAL, not broken --
  ... It is withheld from registration solely because this repository currently carries 65
  functions over the complexity.max_score threshold (15) ...
```

Git history shows the gate was briefly registered (commit `89e8cb33`, "13 registered as real
gates", 2026-09-15) and then walked back to withheld (`be557d10`, "eleven gates registered and
two withheld for different reasons") — the ratchet-shape gap this entry describes was the
reason it came back out. `unit_tests/commit_guardian/test_hook_registration_inventory.py`'s
`UNREGISTERED_BASELINE` still lists `check_complexity.py` today, with a comment citing "79
over-limit functions across 50 files at max_score 15" — the population has grown since this
entry's 49/915, not shrunk, and no per-file or per-function ratchet (option (a) or (b) from
this entry's own "Ratchet shape" section) has been implemented. `main()` still recomputes
absolute scores with no `HEAD` comparison anywhere in `check_complexity.py`. Mechanism
confirmed present; kept open.

---
