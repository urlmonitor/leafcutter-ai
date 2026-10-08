---
title: Criteria for abilities that actually reach the agent
date: "2026-10-08"
time: 0946
type: manual
components: 
  - agent_registry
  - template_compiler
  - skills_system
  - build_pipeline
summary: "Thirty-one approved, high-priority acceptance criteria for a build defect that delivers no skills table to any agent: the compiler computes each agent's table and then discards it, silently, for all 120 compiled prompts."
description: "Authors a new L0 (AR-300, 'A specialist arrives with every ability you granted it') with four L1s, sixteen L2s and eight L3s, plus AR-200b-2 and its L3 under the existing AR-200b. The defect: template_compiler.py only substitutes the per-agent skills table when a placeholder token is present in the template body, and none of the 60 agent templates contain it, so the table is computed and dropped with no warning and exit 0. The per-agent spawn-allowlist injection fails the same way. Separately, 25 of the 31 agents with a recorded skill grant lack the Skill tool. The criteria move the grant into each agent template's own frontmatter beside tools, require delivery to be proven against the compiled prompt rather than the registry or source template, and turn a silent drop into a reported failure. Supersedes INF-600a-1 and INF-600a-1-i, which were never implemented and pointed the other way. Also files KI-BP-20261001 on a phase_1 exit criterion that cannot fail on this defect."
breaking: false
---

## Entry

The build works out which skills each agent may use, and then never tells the agent.

`scripts/template_compiler.py` builds a per-agent skills table from the registry, but it only
puts that table into the prompt when the template contains a `{{my_skills_used}}` placeholder:

```python
if "{{my_skills_used}}" in body:
```

None of the 60 agent templates contain that token. The table is computed and thrown away, with
no warning, and the build exits 0. The per-agent spawn-allowlist injection
(`{{my_spawn_allowlist}}`) fails the same way, also in 0 of 60 templates. Dual-platform
compilation writes a second set of 60 prompts, so 120 compiled prompts are affected. Only 2 of
them have any skills section, and that is the same hand-written block in python-coder, an agent
that does not have the tool needed to invoke a skill.

The sign-off block in the same file shows the design that works. It is appended with no
placeholder when a template sets `signoff: true` in its frontmatter, and it reaches 23 of 23
agents.

## What is specified

**`AR-300` — "A specialist arrives with every ability you granted it."** Four L1s:

- `AR-300a` — the compiled prompt names every ability the agent was granted, says when each one
  applies, and contains no abilities section when nothing was granted
- `AR-300b` — a per-agent block the build computed but did not deliver ends the run in failure.
  This covers both dead injections and any added later, and a run that recognised no blocks at
  all reports that rather than passing
- `AR-300c` — the grant is declared once, in the agent template's own frontmatter beside
  `tools:`, and the registry's copy is derived and checked against it
- `AR-300d` — a new grant, a new agent, or a revoked ability takes effect on the next build with
  nothing else to edit. Revocation is the case that matters: an append-only design satisfies
  every other criterion here and still tells an agent it may use an ability that was taken away

**`AR-200b-2`** — an agent whose grant is not empty must also hold the `Skill` tool. Today 25 of
the 31 agents with a recorded grant do not. Its derivation is stated in the record rather than
inherited from `AR-200b-1`, because that record limits itself to mutating tools on the grounds
that a missing read-only tool "fails loudly". This one does not fail loudly. Across about 90,000
recorded agent tool calls there were 33 skill invocations and about 32,600 shell-outs to raw text
search. `AR-200b`'s own criteria were widened via `amended_by` to cover a grant that is declared
rather than written into the instructions, and that wording was then re-approved.

## Evidence rule

Every test contract asserts against the **compiled** prompt, never the registry or the source
template. Checking either of those passes today for all 31 agents that receive nothing. Several
descriptors corrupt only the compiled output and require the check to fail, so an implementation
that reads the registry cannot satisfy them. Every universal rule reports how many agents it
examined, and a count of zero is a failure.

## Superseded

`INF-600a-1` made the registry's `skills_invoked` field the source of truth and kept
`skills_used` as an alias. That is how the grant ended up split across two fields (32 agents in
one, 40 in the other, 12 only in the second), and it points the opposite way from this tree. It
was never implemented. It and its child `INF-600a-1-i` are superseded by `AR-300c-1`,
`AR-300c-3` and `AR-300c-3-i`, and their `criteria` blocks are left intact as the audit trail.

## Also filed

`KI-BP-20261001`: phase_1's exit criterion *"build.py --validate-only returns 0 with no template
injection errors"* can only detect an error, and a missing placeholder never causes one, so the
criterion passes while both injections deliver nothing. `docs/roadmap.json` is untouched. The
build-pipeline register also gains the index row that `KI-BP-20260923-0730` never had.

No code changes. All 31 records are `readiness: approved`, `priority: high`.
