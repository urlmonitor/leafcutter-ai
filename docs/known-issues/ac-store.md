---
title: "Known issues — ac-store"
description: "Open, observed defects in the ac-store component: the acceptance-criteria YAML store, its schema validator, and the scripts that read and write it. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - ac_store
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/reference/ac-schema.md
---

# Known issues — ac-store

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-ACS-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-ACS-001 — `validate_ac_schema.py` exits 0 when it validates nothing

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/validate_ac_schema.py:333`

**Symptom.** The script takes **file paths** and does no globbing of its own. Handed a
directory — the intuitive way to validate a component — it matches zero files, prints
`No YAML files to validate.` and **exits 0**. The caller sees a success-shaped result
from a run that checked nothing. A validator that cannot distinguish "clean" from "I was
given nothing" is worse than no validator, because it is consulted for reassurance.

**Evidence.** Verified 2026-08-18 against `docs/acceptance-criteria/testing-quality/`:
the bare-directory form prints the no-op message and exits 0, while
`find <dir> -name "*.yaml" -exec python scripts/ac_store/validate_ac_schema.py {} +`
over the same tree reports eight real violations (`documentation_triggers` present on L2
records, permitted only on L1). Across the whole store the correct invocation reports
**288** violations, most of them legacy list-form `it_requirements` predating the
object-form rule — real, but not a fire.

This mattered because `CLAUDE.md`'s own "AC-store hygiene — bulk pre-flight" section
prescribed the bare-directory form from 2026-08-10 until 2026-08-18, so the documented
defence against store rot was itself a no-op for eight days. That instruction is now
fixed; the script is not.

**Fix direction.** Exit non-zero, or at minimum warn loudly, when the resolved file count
is zero. Better: accept a directory and walk it, since that is plainly what every caller
means. Note a plain `*/*.yaml` glob is **not** an adequate workaround — AC YAML sits at
more than one depth, so a fixed-depth pattern silently skips directories, which is the
same defect wearing a different hat.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5.

---

### KI-ACS-002 — `--verify` passes `files_touched` on a path count, not on correctness

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `--verify` readiness report

**Symptom.** The readiness report's surface check asserts only that *some* paths were
derived. Its output reads `[PASS] files_touched has N path(s) from doc_links` — N > 0 is
the whole test. An AC whose derived surface omits the file the work changes, and includes
a file the AC's own criteria forbid touching, passes it and the report concludes `READY`.
The provenance label is misleading too: paths that came from the prose fallback are
reported as coming from `doc_links`.

**Evidence.** `python scripts/ac_store/generate_ticket_from_ac.py --ac BO-2400g-2 --verify`
on `main` at `439b9076f` exits 0 and prints:

```
=== Ticket readiness report for BO-2400g-2: READY ===
  [PASS] files_touched has 4 path(s) from doc_links
```

The four paths are `scripts/build.py`, `templates/agents/change-scope-reviewer.md`,
`templates/agents/pr-reviewer.md` and `unit_tests/_workflow_engine_harness.py`. The file
that AC exists to change — `templates/workflows-js/fast-lane-ship.js` — is absent, because
its `doc_link` is tagged `describes`. `change-scope-reviewer.md` is a file that AC's
criteria explicitly forbid touching, and `scripts/build.py` came from the prose scan, not
from a `doc_link` at all.

This is the check people reach for when they want reassurance that a generated ticket is
sane, so a count dressed as a verdict is worse here than elsewhere.

**Fix direction.** Compare the derived surface against something independent — at minimum
warn when an AC has edit-surface `doc_links` for files that did not make the list, or when
a path arrived only via the prose fallback. Report provenance per path honestly. A check
that cannot assess correctness should report `INFO`, not `PASS`. Related: the prose
fallback itself is `BP-1100a-4`, and the authoring-side rule is documented in
`docs/how-to/ac-traceability-store.md`.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8.
