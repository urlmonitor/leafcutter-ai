---
title: 'Reference: Specialist Ability References'
description: 'Lookup for the ability-reference check: what counts as an instruction to use an ability, what does not, the four fault kinds with their fixes, the own-grant comparison, and the provided_by marking for project-supplied abilities.'
type: reference
status: active
created: 2026-10-20
last_updated: 2026-10-20
components:
- agent_registry
- skills_system
- build_pipeline
related_docs:
- docs/reference/agent-template-frontmatter.md
- scripts/skill_ref_recognition.py
- scripts/agent_skill_ref_grants.py
- scripts/check_skill_refs.py
- scripts/agent_ability_verdict.py
- scripts/agent_ability_gate.py
- scripts/project_ability_slots.py
- scripts/agent_declaration_shape.py
- templates/agents/sql-coder.md
---
# Specialist Ability References

Lets an author look up how the build treats a sentence in a specialist definition
or shared guide that tells the reader to use an ability (a skill), and how to fix
each finding. The `skills:` field itself is documented in
[Agent Template Frontmatter Fields](agent-template-frontmatter.md#granting-skills-and-sub-agents);
the four example failure lines are quoted there, in
[Ability-reference check](agent-template-frontmatter.md#ability-reference-check).

## What is checked

| Document | Examined for | Subject named in a finding |
|---|---|---|
| Specialist definition: a registry agent whose template is a file in `templates/agents/` | Existence, case, agent-named-as-ability, and the grant comparison | The specialist id |
| Shared guide: every other `.md` under `templates/` | Existence only (the guide has no `skills:` to compare with) | The guide's repo-relative path |

The same computation runs in the build, the registry validator CLI and the commit
hook. A run that examines zero definitions or zero guides is an error, not a pass.
Frontmatter and HTML comments are blanked before scanning; line numbers still
match the file on disk.

## What counts as an instruction

One recognition rule (`skill_ref_recognition.recognise`) decides. A mention counts
as an instruction to use an ability when it takes one of these forms and its clause
(a clause ends at `;` or a sentence end) holds a live instruction verb that no
negator governs:

| Form | Example |
|---|---|
| A skills path | ``Load `.claude/skills/signoff/SKILL.md` and follow it`` |
| An "`<id>` skill" phrase | ``Load the `signoff` skill`` |
| A written-out tool call | `Skill: signoff` (counts unless negated) |

Instruction verbs: `load`, `read`, `invoke`, `apply`, `use`, `call`, `consult`,
`resolve`, `follow`, `execute`; the weaker `run`, `python`, `bash` count unless
the clause is an installer file operation. An unticked phrase counts only when it
is written like an id (contains a hyphen) or is a known ability or specialist.
"any", "a", "each", "every" or "some" before it makes the phrase generic.

## What is not an instruction

| Not an instruction | Example (recognised as nothing) | Why |
|---|---|---|
| A negation | ``Do not use the `signoff` skill here.`` | A negator governs the verb. Negation is clause-scoped, never line-wide. |
| Another specialist's subject | ``The sql-coder agent loads the `doc-enforcer` skill after each edit.`` | The clause's grammatical subject is a specialist other than the one the document defines. |
| A citation of an ability's file | ``The `signoff` skill is defined in `templates/skills/signoff/SKILL.md`.`` | No live verb, a source phrase ("defined in", "see", "per", "according to"). A citation skips the grant comparison but is still checked for existence. |
| An installer step | `mkdir -p .claude/skills/signoff` | The clause is a file operation (`mkdir`, `cp`, `mv`, `rm`, `ln`, `echo`, `install`). |
| A recorded decision history | `<!-- 2026-10-01: dropped the knowledge-query skill -->` | HTML comments are blanked before scanning. |

## Fault kinds

When a reference is an instruction, one finding is printed per ability per line.
Precedence per reference: names an agent, then does not exist, then letter case,
then a missing bundled file (reported as "does not exist"), then, for an
instruction only, the grant comparison.

| Kind | Printed phrase | Fix it asks for |
|---|---|---|
| Names an agent | `names an agent, not an ability` | If the text is in the specialist's `spawn_allowlist` the line says so: reword to hand work to that specialist through the `Agent` tool. Otherwise add it to `spawn_allowlist` (which needs `Agent` in `tools:`) or name an ability. |
| Does not exist | `ability does not exist` | Create `templates/skills/<id>/SKILL.md`, correct the name, or delete the instruction. A path into a bundle that lacks the named file reports `skill '<id>' exists but has no <path>`. |
| Differs only in case | `ability name differs only in case` | Write the id exactly as `did you mean '<id>'?` gives it. |
| Not granted | `ability exists but is not granted` | Add the ability to the specialist's own `skills:`, or correct the instruction. |

## Comparing an instruction with the grant

The grant compared is the `skills:` declaration in the specialist's own definition.
The `skills_invoked` copy in `config/agent_registry.json` is derived and never read
for this check: editing the registry neither causes nor clears a "not granted"
finding. The finding states what the definition grants (`nothing` when empty). A
malformed `skills:` declaration is reported by name and the comparison is skipped
for that specialist, never run against an empty set.

A non-empty grant also needs `Skill` among the specialist's `tools:`; that is the
existing `skill-tool-grant` rule, described under *Tool pairing* in
[Agent Template Frontmatter Fields](agent-template-frontmatter.md#granting-skills-and-sub-agents).

### Worked example: fix by adding the grant

Finding, for `probe-agent` granting only `signoff`:

```text
probe-agent: ability exists but is not granted: 'knowledge-query' referenced at templates/agents/probe-agent.md:88 (probe-agent grants: signoff)
```

Line 88 reads ``load the `knowledge-query` skill to search the graph``. The specialist
needs the ability, so add it to its own frontmatter:

```yaml
skills:
- skill_id: signoff
  mode: always
- skill_id: knowledge-query
  mode: always
```

The finding is gone on the next run, even before the transform hook has refreshed
the registry copy.

### Worked example: fix by correcting the instruction

With the same finding, the specialist should not use the ability. Reword line 88 so
it is not an instruction, for example ``Do not use the `knowledge-query` skill
here.``; no grant is added and the finding is gone.

## Project-supplied abilities (`provided_by`)

A `skills:` entry may carry `provided_by`. Its only accepted value is `project`;
any other value (for example `vendor`) is refused as malformed, naming the entry and
the value. An absent marking means the package supplies the ability.

```yaml
skills:
- skill_id: postgres
  mode: conditional
  condition: For every new SQL file, apply the postgres skill first.
  provided_by: project
```

`templates/agents/sql-coder.md` marks `postgres` and `sql-test` this way.

| Case | Result |
|---|---|
| Lookup location | `<output_root>/skills/<id>/SKILL.md` under the build's target directory (default output root `.leafcutter`). A copy the build itself deployed as a fallback does not count as supplied. |
| Unmarked grant, packaged skill exists | Resolves in `templates/skills/`. A project copy never rescues a misspelt id. |
| Unmarked grant to an ability the package does not ship | Refused (`resolves to no installed skill`), unless another specialist marks that id: then it follows the project-wide rule and is not refused. |
| Marked grant, project lacks it, package does not ship it | Reported, not refused: `project-ability-absent`. |
| Marked grant to a shipped ability, project supplies it | The deliberate override: the project's copy is delivered, stated once as `project-override`. |
| Marked grant to a shipped ability, project does not supply it | Falls back to the packaged copy, stated once as `project-fallback`. |

Informational lines are printed once with no warning or error marker and never set
the exit code:

```text
agent '<id>': ability '<ability>' is supplied by the project (<project path>) and is used in place of the packaged one (<packaged path>)
agent '<id>': the project does not supply ability '<ability>' (looked in <project path>); the packaged copy is used
agent '<id>' is granted the project-supplied ability '<ability>': looked in the project's skills area <project path> and it was not found there, so it is not installed in this project
```

A marked ability satisfies both the existence check and the grant check for the
definition that marks it. The project's copy is used by every specialist that
grants the ability. The build never deploys over a marked ability's project copy and
`--clean` never removes it; the packaged fallback is written only into an empty
slot, with a `.packaged-fallback` marker holding the SHA-256 of the file written.

**Open hazard.** KI-BP-009 (`docs/known-issues/build-pipeline/open-high-ki-bp-009.md`)
is still open: the build can delete an adopter's own abilities placed in the
project's skills area. Marked ids are protected; an unmarked project ability is
still exposed.

## See Also

- [Agent Template Frontmatter Fields](agent-template-frontmatter.md) - the `skills:` and `spawn_allowlist` declarations.
- `scripts/skill_ref_recognition.py` - the recognition rule; if it gains or loses an exclusion, change the table above in the same pull request.
- `scripts/agent_skill_ref_grants.py` - the finding wording and precedence.
- `scripts/agent_ability_verdict.py` - the `provided_by` findings and their informational kinds.
