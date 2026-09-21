---
title: "KI-ACD-012 — The generated `Master_Plan.md` is missing six fields the repo's own ticket guard requires"
description: "KI-ACD-012 — The generated `Master_Plan.md` is missing six fields the repo's own ticket guard requires"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-012 — The generated `Master_Plan.md` is missing six fields the repo's own ticket guard requires

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 4
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-31
- **2026-08-31 recurrence:** `EPIC-SuppressionNarrowsNeverDisables`. Seven fields missing this
  time — `title`, `type`, `depends_on`, `requires_diagram`, `requires_adr`, `change_target`,
  `risk_surface`. Caught by `ticket_frontmatter_guard` on the first edit to the file, so it
  fails loudly, which is the good half. The bad half is that it is still unfixed six days and
  four occurrences later, and every generated epic pays the repair by hand.
- **Where:** `scripts/ac_store/epic_master_plan.py:191-199` — the frontmatter block in
  `_render_master_plan()`; against `templates/hooks/ticket_frontmatter_guard.py`
- **Reported by:** customer bug report 2026-08-25

**Symptom.** The generator emits an artifact that the repository's own pre-commit gate
rejects. Every epic it produces therefore arrives with a Master_Plan that cannot be
committed without either hand-editing the file or skipping the hook.

**Root cause — producer and consumer disagree about the required field set.**
`_render_master_plan()` writes frontmatter with five keys: `epic_name`, `created`,
`status`, `components`, `source_ac`. `ticket_frontmatter_guard.py` demands rather more.
Its `REQUIRED_FIELDS` constant (`:26`) is
`("title", "status", "components", "created", "depends_on")`; on top of that it calls
`_check_required_tristate()` for `requires_diagram` and `requires_adr` (`:556-557`), and
`_check_change_target()` / `_check_risk_surface()` (`:560-561`) — the last two promoted
from optional to REQUIRED by BO-610-4.

Intersecting the two lists leaves **six** required fields the generator never writes:
`title`, `depends_on`, `requires_diagram`, `requires_adr`, `change_target`,
`risk_surface`. Note also that `epic_name` and `source_ac`, the two keys the generator
does emit beyond the overlap, carry no weight with the guard at all — so the artifact is
not merely thin, it is describing itself in a vocabulary the gate does not read.

**AC-coverage note — a genuine spec gap.** No AC claims this. `ACD-1200a-8` is
`work_status: todo` and enumerates Master_Plan **content** only; it never mentions
frontmatter fields, so even completing it as written would not close this. There is no
criterion anywhere stating that generated artifacts must satisfy the gates that guard
hand-written ones.

**Second occurrence, 2026-08-25.** Reproduced verbatim by
`goal_to_epic.py --ac GE-120`: the generated `EPIC-TrustThatAGreenCheckActuallyChecked/Master_Plan.md`
was rejected for exactly the six fields named above. Fixed by hand in that epic — `title`,
`type: epic`, `depends_on: []`, `requires_diagram`, `requires_adr`, `change_target`,
`risk_surface` added, and `status` corrected from `in_progress` to `todo`, since no ticket
in the epic has been started. The generator is unchanged, so the next epic reproduces it.

**Third occurrence, 2026-08-25** — and it reconciles this entry with `KI-ACD-019`'s
correction, which are both right about different gates. Reproduced by
`goal_to_epic.py --ac GE-122d` (`EPIC-TheNumberingGuaranteeHoldsAtEveryStage`); all six
fields supplied by hand again. Three runs, three identical hand-repairs — this is not
intermittent.

**There are two gates and they disagree by four fields.** Verified against both:

| Gate | When it fires | Required set | Generator misses |
|---|---|---|---|
| `check_doc_frontmatter.py`, config `templates/scripts/commit_guardian/commit_guardian.json` → `ticket_frontmatter.required_fields` | pre-commit, on `tickets/**/*.md` | `title`, `status`, `components`, `created`, `depends_on` | **2** — `title`, `depends_on` |
| `templates/hooks/ticket_frontmatter_guard.py` | Claude Code `PreToolUse` on `Edit`/`Write` | the same 5, plus `requires_diagram`, `requires_adr` (`:556-557`), `change_target`, `risk_surface` (`:560-561`) | **6** |

`KI-ACD-019` is right that the generator writes through Python file I/O and so never trips
the `PreToolUse` guard on generation, making the commit-blocking count 2. What it misses is
the sequel: **the moment anyone opens the file with `Edit` or `Write` to supply those two,
the `PreToolUse` guard fires and demands four more.** That is why every run so far has been
repaired to the full six — not because six were commit-blocking, but because the act of
repairing is itself an `Edit`. The number is 2 or 6 depending on how you fix it, and there
is no route that requires only 2.

So the fix direction below is unchanged, but the regression test must run **both** gates:
satisfying only the pre-commit set leaves a Master_Plan no agent can subsequently edit.
The four-field divergence between the two gates is worth closing on its own merits — a
hand-written ticket and a generated one are held to different standards today.

**Fix direction.** Render the full required frontmatter set. Then add a test that runs
`ticket_frontmatter_guard` against a freshly generated Master_Plan, so the generator and
the gate cannot drift apart again — the two are maintained independently and each is
individually correct, which is exactly the condition under which a divergence goes
unnoticed. The test must run the real guard rather than assert a field list, or it
becomes a second copy of the requirement that can itself fall behind.

---
