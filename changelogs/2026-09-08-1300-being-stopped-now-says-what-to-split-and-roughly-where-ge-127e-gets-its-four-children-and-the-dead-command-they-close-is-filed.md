---
title: "Being stopped now says what to split and roughly where: GE-127e gets its four children, and the dead command they close is filed"
date: "2026-09-08"
time: "13:00"
type: manual
components: 
  - ac_store
  - commit_guardian
summary: "Specified (not yet built) what a blocked commit is owed when a file is too long: the split advice a refusal gives must actually be about that file, and must actually work when followed — and filed the concrete case where it currently does not."
description: "1 commit, 7 files, spec-only (no code, no tests, no behaviour change). Five new acceptance-criteria records under docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/ (GE-127e-1, -2, -3, -3-i, -4) fill in GE-127e, an L1 that had covered_by: [] since 2026-09-01; GE-127e.yaml gains only that covered_by list. 36 test descriptors total, every one driving a real commit in a real temporary repository, none grepping source. One new known-issue entry in docs/known-issues/commit-guardian.md: KI-CG-20260908-file-size-refusal-advises-a-dead-command (medium, open)."
commits: 
  - 2f9564b5b
breaking: false
---

## Entry

### The gap: a fixed sentence has satisfied "gives remediation advice" since day one

`GE-127e` — *"Being stopped tells you what to split and roughly where"* — has been an L1
under `GE-127` with `covered_by: []` since 2026-09-01, the only childless L1 in its tree.
It is the criterion that keeps the other four members of that tree from being eroded in
practice: the pressure that destroys a file-size standard is the cost of complying at the
moment you are blocked, and today the only advice a refusal carries is a fixed sentence
pointing at a helper. This change gives `GE-127e` its children. Nothing here is built yet —
all five new records are `readiness: reviewed`, `work_status: todo` — and `GE-127e.yaml`'s
own `criteria` field is untouched; it only gains the `covered_by` list pointing at them.

### The discriminator — `GE-127e-2`

The reader-facing point is `GE-127e-2`: *"Two different oversized files are not given the
same advice, and changing what is in a file changes the advice it gets."* "The refusal
includes remediation guidance" is satisfiable by a fixed sentence — which is exactly what
ships today — so acceptance is instead bound to the advice being a **function of the file in
hand**. Three arms:

- two files refused in the same commit must be given different advice;
- the same file rearranged at constant length must be given advice that has **moved**;
- a byte-identical copy of a file at another path must be given **identical** advice.

Its named mutation — derive advice from file kind and length alone, ignoring content —
must redden the first two arms while the copy arm **stays green**; an injection run that
reddens all three is recorded as a failure of that descriptor, not a stronger pass.

### The other three members

- **`GE-127e-1`** — the refusal accounts for what is inside the file it refused, and names
  a division of that file in terms of those same parts. The only record of the four that
  builds something; the other three constrain what it produces.
- **`GE-127e-3`** — the refusal offers only help that actually arrives; a bare verdict beats
  a promise nothing keeps. This is the criterion written to close the known issue below.
- **`GE-127e-3-i`** — guidance that could not be produced is said so plainly, and never
  moves the commit verdict in either direction. It reuses `GE-127a-1-i`'s line grammar (one
  token, `reason=`, a specific named cause) but deliberately **not** its exit 2: a failure
  to measure leaves the verdict unknown, which is what exit 2 means, but a failure to
  describe leaves the verdict perfectly known and only the advice missing — routing it to
  exit 2 would collapse that distinction and suppress the refusal block outright.
- **`GE-127e-4`** — everything needed to choose arrives with the refusal, the division is
  offered as a starting point, and declining it costs nothing.

Across all five records: 36 test descriptors total, every one driving a real commit in a
real temporary repository — none grepping source or asserting a config key. Each record
carries one reachability descriptor through `run_hook.py` and one deployed descriptor in a
cold process. All 11 of the business-analyst's named mutations are carried verbatim into
descriptors, machine-verified by a whitespace-normalised string match between each record's
notes and its `test_spec`. `package_surface: false` on all five, measured rather than
assumed.

### Known issue filed — `KI-CG-20260908-file-size-refusal-advises-a-dead-command`

Severity medium, status open. `check_file_size.py:234` (and :236) tells a blocked author to
use the `/code-refactoring-specialist` slash command. That command exists and is deployed —
but its own step 1 instructs running
`.agent/skills/code-analysis/scripts/analyze_structure.py`, and that script exists nowhere
in the workspace. So the single actionable line the live gate emits dead-ends one hop down:
the pointer chain resolves at every hop but the last, which is why a check that stopped at
"does the slash command exist" would report it healthy. The verdict itself is never wrong —
the file genuinely is over its limit — only the advice attached to it is dead, which is why
this is medium rather than high. `GE-127e-3` is the criterion written against exactly this
shape; its first descriptor is written to be applied to this message, and the durable fix is
`GE-127e-1`/`GE-127e-2` replacing the fixed pointer with guidance derived from the file in
hand.
