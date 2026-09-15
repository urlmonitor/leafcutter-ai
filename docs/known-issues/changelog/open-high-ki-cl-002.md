---
title: "KI-CL-002 — No build drive can produce a changelog entry: `changelog-agent` is in neither the phase order nor any generated agents map, so every code-touching drive lands a PR that cannot merge"
description: "KI-CL-002 — No build drive can produce a changelog entry: `changelog-agent` is in neither the phase order nor any generated agents map, so every code-touching drive lands a PR that cannot merge"
type: reference
category: reference
status: active
created: '2026-08-26'
last_updated: '2026-08-26'
components:
  - changelog
related_docs:
  - docs/known-issues/changelog.md
  - docs/known-issues/README.md
---

# KI-CL-002 — No build drive can produce a changelog entry: `changelog-agent` is in neither the phase order nor any generated agents map, so every code-touching drive lands a PR that cannot merge

> One known issue, split out of `docs/known-issues/changelog.md` on
> 2026-09-14. Index: [changelog.md](../changelog.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26
- **Where:** `templates/workflows-js/build-feature.js:305-330` (`phaseOrder`);
  `scripts/ac_store/generate_ticket_from_ac.py` (`_build_agents_map` — no `changelog`
  reference anywhere in the file); `scripts/release/check_changelog_presence.py`
  (`EXEMPT_PREFIXES`)

**Symptom.** A `/build-feature` drive completes, reports `status: ok`, opens a PR — and the PR
is unmergeable, with the required `Changelog entry present` check red and every other required
check green. The drive reports success because from its own point of view it succeeded: no phase
failed, because no phase was responsible.

**Why it cannot self-correct.** Two independent gaps, either of which alone would be enough:

- **`phaseOrder` has no `changelog-agent` entry.** The array runs `status-checker` → … →
  `commit` → `pull-request`, and `changelog-agent` appears nowhere in the file.
- **The generator never puts it in the agents map.** `generate_ticket_from_ac.py` contains no
  occurrence of the string `changelog` at all, so no generated ticket ever marks the phase
  `needed`.

The second gap hides the first. `build-feature.js:355-368` already has a diagnostic for an agent
that is in an agents map but missing from `phaseOrder` — it warns and sorts the agent last. That
guard never fires here, because the agent never reaches a map to be sorted. The failure is
therefore completely silent on the drive side and only surfaces on GitHub.

**Scope — this is not an edge case.** `EXEMPT_PREFIXES` in `check_changelog_presence.py` covers
`changelogs/`, `tickets/`, `docs/acceptance-criteria/` and `docs/known-issues/`. It does **not**
cover `scripts/`, `unit_tests/`, `templates/` or `docs/testing/`. So the gate fires on essentially
every drive that changes code — which is what a build drive is for. A ticket-only or AC-only drive
passes, which is why the gap can look intermittent.

**Evidence.** Three consecutive drives in the `BP-1100g` chain, each with all other required
checks green and this one red, each needing a hand-written entry before it could merge:

| PR | ticket | non-exempt paths that tripped it |
|---|---|---|
| #548 | `BP-1100g-1` | `templates/`, `unit_tests/` |
| #574 | `BP-1100g-3` | `scripts/`, `templates/`, `unit_tests/` |
| #584 | `BP-1100g-3-i` | `unit_tests/` |

**Why high rather than medium.** It is not that a step is missing — a missing step that halts is
cheap. It is that the drive reports `status: ok` and `recorded_status: done` on work that cannot
land, so the payload disagrees with the repository. That is the phantom-done shape this component
family exists to prevent, and it costs a manual round-trip on every single code drive.

**Fix direction.** Add `changelog-agent` to `phaseOrder` **before** `commit`, not after — the
entry has to be in the commit the PR contains, and anything after `commit` either misses the
commit or forces a second one. Priority ~11.95, immediately after `documentation-verifier`. Then
make the generator add it to the agents map, gated on the same condition CI uses rather than a
second hand-maintained rule: the ticket's `files_touched` containing at least one path outside
`EXEMPT_PREFIXES`. Deriving the condition from the CI checker's own constant is the point — a
re-stated copy of the exempt list is the two-vocabularies drift this repo keeps rediscovering
(see KI-CL-001's three-layer split, and the `EPIC-ComputedQualityGates` layer-3 failure).

Worth fixing the diagnostic too while there: `build-feature.js`'s "absent from phaseOrder" warning
only covers agents that made it into a map. An agent that is in `config/agent_registry.json` and
in **no** map is invisible to it, which is exactly this bug. A startup assertion that every
registry agent is either in `phaseOrder` or explicitly listed as non-phase would have caught this
on the first run.

**Cross-component note.** Filed here because the missing artefact is a changelog entry and this
register owns that corpus, following KI-CL-001's precedent. But the code to change is
`build-orchestration`'s (`build-feature.js`, and its twin `build-ticket.js` — the `phaseOrder`
array is explicitly marked `TWIN: mirrors build-ticket.js phaseOrder. Keep in sync.`, so fixing
one and not the other reintroduces the gap on the other route) and `ac-driven-dev`'s
(`generate_ticket_from_ac.py`).

**Pattern:** a required gate with no producer anywhere in the pipeline that is supposed to satisfy
it, where the guard that would have reported the omission cannot see an agent that appears in no
map at all.
