---
title: "Reference: AC Assignments and Persistence"
description: "Lookup reference for how AC assignment is read (agent cards carry no AC Assignments section; assigned_agent is grouped at read time) and for the AC persistence guarantee after a quick-fix ticket closes."
type: reference
status: active
created: 2026-10-12
last_updated: 2026-10-12
components:
  - build_pipeline
related_docs:
  - docs/reference/ac-schema.md
---

# AC Assignments and Persistence

> **Parent document:** [ac-schema.md](ac-schema.md)

Two lookups split out of the AC schema reference to keep it within its length limit.

---

## Agent cards carry no AC Assignments section (removed 2026-10-09)

`generate_agent_cards.py` no longer emits a `## AC Assignments` section in
`docs/agents/cards/<agent>.card.md` and no longer scans the AC store.
`render_ac_assignments`, `_scan_ac_assignments`, `_scan_all_ac_assignments`
and the `ac_assignments=` parameter of `generate_card` were deleted.

Reason: the AC store is the source of truth, and `assigned_agent` can be
grouped at read time by any consumer. Caching that query into generated
markdown made every `build.py` run rewrite the cards (a permanently dirty
working tree), and the regenerated cards could not be committed because of
the doc-length growth ratchet.

Source today: the AC YAML store, grouped by `assigned_agent` at read time. The
field is still live: the ticket generator reads `assigned_agent` to build the
ticket's `agents:` map and render a single `Assigned agent:` line. AC
INF-600b-2, which specified the section, is retired as superseded.

---

## AC persistence guarantee after ticket lifecycle close (AC BP-600b-3)

When the quick-fix workflow completes end-to-end — fix committed and the
workflow's internal ticket closed — the AC YAML file created during the AC
creation phase MUST remain untouched in the store.

**Invariant:**

```
Given the quick-fix workflow has completed end-to-end (fix committed
  and ticket closed),
When the user lists AC files under docs/acceptance-criteria/,
Then the AC YAML file created by the quick-fix workflow still exists,
And its status field is "active",
And it is not deleted or moved by the ticket lifecycle close step.
```

**Implementation constraint for the ticket lifecycle close step:**

The step that marks the quick-fix workflow's internal ticket as `done` (e.g.
flipping `status: in_progress → done` via `set_ticket_status.py`) MUST NOT
touch or reference any AC YAML file. Specifically:

- The close step operates only on the ticket markdown file (`*.md`) and the
  git index for that file.
- It MUST NOT delete, rename, move, or overwrite any file under
  `docs/acceptance-criteria/`.
- It MUST NOT set the AC's `status` field to `deprecated` or `superseded_by`
  as a side-effect of the ticket closing.

The AC lifecycle (active → deprecated → superseded_by) is governed exclusively
by human or agent intent expressed in separate commits. A ticket closing is not
a trigger for AC lifecycle transitions.

**Why this guarantee is necessary:**

The quick-fix workflow creates an AC YAML file as a permanent traceability
artefact. The AC documents what bug was fixed and what criterion the fix must
satisfy going forward. If the ticket lifecycle close step were to delete or
deactivate the AC, the traceability record would be destroyed, the pre-commit
`check_ac_coverage.py` hook would lose its anchor, and any test tagged
`# covers: <id>` would reference a ghost criterion. The persistence guarantee
ensures the AC outlives the workflow that created it.

---

## See Also

- [ac-schema.md](ac-schema.md) - the parent AC schema reference.
