---
title: "KI-BP-007 — No gate validates a skill reference written in template prose, so six skills are loaded by name and none of them exist"
description: "KI-BP-007 — No gate validates a skill reference written in template prose, so six skills are loaded by name and none of them exist"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-007 — No gate validates a skill reference written in template prose, so six skills are loaded by name and none of them exist

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — PARTIALLY FIXED (re-verified 2026-09-23). Closed: `route-learning`
  and `capture-learning` are retired per ADR-034 and removed from the fail-open path in
  `signoff/SKILL.md` §7 and from PO v3 / BA v3 / IT PO v3
  (`templates/agents/{product-owner,business-analyst,it-po}.md`), which now read "Do NOT
  load `route-learning` or `capture-learning`" — the widest-blast-radius call sites this
  entry named. The `agent-telemetry` skill has since been authored
  (`templates/skills/agent-telemetry/` exists), resolving its 8 references in
  `building-epics/SKILL.md`. Remains open: `scripts/check_skill_refs.py` is still not
  wired into CI or `build.py` (no hit in `.github/workflows/*.yml` or
  `.pre-commit-config.yaml`); two dangling imperative `route-learning` references survive
  at `templates/agents/retrospective-agent.md:242` and `templates/skills/README.md:36`;
  and the three trading-domain leftovers in `templates/agents/research-agent.md`
  (`import-scanner`, `find-context-candle`, `trade-analysis`) are untouched. Running
  `python3 scripts/check_skill_refs.py` today: `FAIL: 5 imperative reference(s) to 4
  skill target(s) that do not exist` (down from the original 21 references / 6 skills).
  New closure condition: that command exits 0 AND is wired in as a required CI/build
  check. Affects `/plan-feature`: incidentally — the entry never names `/plan-feature`,
  but three of the four now-fixed call sites (PO v3, BA v3, IT PO v3) plus the
  still-live `signoff` skill are exactly the agents `/plan-feature`'s AC-authoring
  pipeline dispatches, so this partial fix lands squarely in its path even though the
  entry's own scope (also `build-feature`, `quick-fix`, `retrospective-agent`) is wider.
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/build_phases.py:1970-1990` — the `skills_invoked` resolution loop, the
  only skill-reference validator in the build

**Symptom.** Reported from a consumer install as "those knowledge-capture skills aren't
available in this consumer project." The report is accurate but its framing is not: nothing
is wrong with the packaging. `build_skills` copies `templates/skills/` wholesale, and
`route-knowledge` / `knowledge-query` deploy correctly. The skills the customer wanted were
never written. Six distinct skills are referenced **by path** in shipped templates and have
no directory in `templates/skills/`:

| Referenced skill | Referenced from | Reference is |
|---|---|---|
| `route-learning` | `signoff/SKILL.md`, PO v3, BA v3, IT PO v3, `retrospective-agent`, `skills/README.md` | `Load .claude/skills/route-learning/SKILL.md` |
| `capture-learning` | `signoff/SKILL.md`, PO v3, BA v3, IT PO v3 | `Load .claude/skills/capture-learning/SKILL.md` |
| `agent-telemetry` | `building-epics/SKILL.md` ×8 | `python .claude/skills/agent-telemetry/scripts/emit_event.py …` |
| `import-scanner` | `research-agent.md` | routing table — "invoke via `Bash`" |
| `find-context-candle` | `research-agent.md` | routing table — "invoke via `Bash`" |
| `trade-analysis` | `research-agent.md` | routing table — "invoke via `Bash`" |

None has ever been committed: `git log --all -- templates/skills/<name>` is empty for all
six, and `find … -name emit_event.py` returns nothing. The last three are not even from this
domain — `find-context-candle` and `trade-analysis` are trading-system skills, inherited when
`research-agent` was copied in from another project and never reconciled against this
package's skill set.

**Why this is the gate, not the artifacts.** Six independent authors, across at least three
epics, each wrote a reference to a skill that was not there, and the build printed a success
banner every time. `build_phases.py:1970-1990` *does* fail the build on an unresolvable skill
id — but it resolves only the `skills_invoked` **registry field** in `agent_registry.json`.
Every one of these six is declared in **Markdown prose inside a template body**, which no
validator reads. So the check covers the declaration form that is mechanically generated and
rarely wrong, and ignores the form a human hand-types — the one that actually rots.

The failure is uniform because the callers are uniform: each reference site treats "skill not
found" as a pass. `signoff` §7 is the widest blast radius, since every phase agent runs it on
every sign-off:

```text
This step is **mandatory** — skipping it is a protocol violation. If `route-learning` or
`capture-learning` are unavailable, log a warning and proceed (do not block sign-off).
```

Declared mandatory, then handed an unconditional escape hatch — so the escape hatch is the
only reachable path. PO v3, BA v3 and IT PO v3 each carry their own copy of the shape ("if
not found, log … and stop"). The eight `agent-telemetry` calls in `building-epics/SKILL.md`
fail per-command inside a supervisor that does not check their exit status. Net effect: the
post-execution half of `docs/architecture/agent_knowledge_system.md` has never run, and the
epic runbook has never emitted a telemetry event — while every agent reports a clean sign-off.

This is very likely the mechanism behind the pre-drive-checklist story in `CLAUDE.md`
("23 `submit-failed` events occurred without detection — the drive completed but zero
telemetry was captured, making the retrospective impossible"). That was diagnosed as an
unreachable sink; an `emit_event.py` that does not exist produces the same symptom.

**Evidence.** `scripts/check_skill_refs.py` resolves every prose skill path against the real
directory set. On the tree that recorded this issue:

```text
$ python3 scripts/check_skill_refs.py
FAIL: 21 imperative reference(s) to 6 skill(s) that do not exist in templates/skills/.
  'agent-telemetry'      (8 references)  templates/skills/building-epics/SKILL.md
  'capture-learning'     (4 references)  signoff/SKILL.md, PO v3, BA v3, IT PO v3
  'find-context-candle'  (1 reference)   templates/agents/research-agent.md
  'import-scanner'       (1 reference)   templates/agents/research-agent.md
  'route-learning'       (6 references)  signoff/SKILL.md, README.md, PO/BA/IT-PO, retrospective
  'trade-analysis'       (1 reference)   templates/agents/research-agent.md
```

A naive scan also flags a seventh name, `create-ac` — the control case worth keeping in mind.
It was correctly retired into `plan-feature` (#184, `3aeb9298`), and the surviving mention at
`plan-feature/SKILL.md:560` sits inside a `DECISION HISTORY` comment recording that migration.
A gate that fails on it would be failing on accurate history. Two discriminators separate the
classes, and `check_skill_refs.py` applies both: HTML comment blocks are stripped before
scanning, and a reference only fails if its line is **imperative** (`Load …`, `python …`,
"invoke via Bash") rather than descriptive.

**Fix direction.** The gate now exists — `scripts/check_skill_refs.py`, added with this entry.
It is not yet wired into CI or the build, so it currently only fails when run by hand. Wire it
in as a required check (or as a `build.py` validation phase alongside the `skills_invoked`
resolution it complements) — the same posture `skills_invoked` already has, applied to the
declaration form that is actually used. That is what converts all six from silent runtime
no-ops into a build error, and stops the seventh being written.

Then resolve the instances: retarget `route-learning` at `route-knowledge` (which exists and
already describes itself as the caller-friendly variant — see its `:474-511` table, written
as though both halves shipped), decide whether `capture-learning` and `agent-telemetry` are
authored or dropped, and delete the three trading-domain rows from `research-agent`. Remove
the fail-open clauses in the same change — a mandatory step that warns and proceeds is
indistinguishable from an absent one, and is what let this survive for the life of the
feature.

**Trap.** The complaint arrives as a consumer-install packaging bug and reads exactly like
KI-BP-006 — a module missing from a deploy list. Auditing `build_skills` and the deploy
manifest finds nothing, because nothing there is wrong. Confirm the artifact exists in
`templates/` before investigating why it did not arrive. And do not stop at the two skills the
customer named: the reporter sees whichever dangling reference their workflow happened to
touch, never the class.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2's inverse. Source and deployed
layout agree perfectly; both are missing the same file, and every consumer of it treats
absence as a pass.

---
