# IT-PO learnings — the COMPILED-PROMPT evidence surface, and why `.claude/agents/` is the wrong path to name

Captured 2026-09-30 during AR-300 / AR-200b-2 technical enrichment.
Component: agent-registry (AR). 26 L2/L3 leaves enriched.

S9 note: `harvest_learnings.py --print-sink` REFUSED in this worktree — no
`config/knowledge_sink.json` build-time declaration (the build has not run
here). Persisted as a memory file per the existing `feedback_itpo_*.md`
convention, same as the BP-900f run.

## The measured defect class: a per-agent injection gated on a token nobody writes

`scripts/template_compiler.py` guards the skills-table substitution on
`if "{{my_skills_used}}" in body:`. Verified: **0 of 60** agent templates contain
that token, so the computed table is discarded for every agent, silently, exit 0.
Same shape kills `{{my_spawn_allowlist}}` (also 0 of 60). There are **8**
placeholder-guarded injection types in that function, all sharing the failure mode.
`scripts/build_placeholder_detection.py` checks for LEFTOVER tokens and does not
check either dead injection — so the obvious enforcement point is a no-op for this
defect class.

**The working precedent is in the same file** (~line 420):
`body = body.rstrip("\n") + build_signoff_block()` — an append with NO placeholder,
gated on a `signoff: true` flag in the template's own frontmatter. Verified: **23**
templates carry `signoff: true`, and it delivers 23 of 23. Generalise this; never
reinstate a body token.

## THE BIG ONE: `.claude/agents/` is a symlink, not a location

A brief (or a BA note, or your own instinct) will tell you the compiled prompts
"live at `.claude/agents/*.md`". Enriching against that path verbatim ships a check
that is vacuous in three separate real situations. Measured in this repo:

```
leafcutter-ai/.claude/agents -> ../.leafcutter/agents
leafcutter-ai/.leafcutter    -> /home/henzeh/projects/leafcutter/.leafcutter   (OUTSIDE the repo)
.gitignore:16                   .claude/agents
```

- **Fresh worktree: the directory does not exist at all.** Verified — the
  skills-injection worktree has no `.claude/agents`. The compiled tree is a
  gitignored build output. Any test asserting on it must build first (ADR-016).
- **Consumer install: the shim degrades to a file COPY on Windows** (ADR-004), so
  the "same" directory can be a divergent second copy.
- **A broken symlink reads as an empty directory**, which is the repo's recurring
  false-green (see the commit_guardian broken-symlink incident).

**Standing it_requirement**: resolve the compiled-prompt population through the
build's declared output root — `output_root` in `skills_config` (default
`.leafcutter`, in `config/skills_config.default.json`) — and FAIL, never skip, when
it does not resolve or resolves short.

## Second-biggest: there are TWO compiled-prompt roots, not one (ADR-002)

Dual-platform compilation emits **60 prompts into `<output_root>/agents/` AND 60
into `<output_root>/gemini/agents/`** (byte-identical today, verified by size). A
delivery guarantee scoped to the claude root leaves the other half unguarded —
which is precisely the sample-not-population defect the AC tree exists to prevent.
Derive the platform roots from the build's declared targets; never enumerate.
(`.agents/agents/pull-request/` is NOT a third root — it is the
`project_context_path` home from skills_config, and it is stale June-4 residue.)

## The evidence rule, stated generally

For any "X was computed and then discarded" defect: **a check against the input
side passes on the broken tree.** Here, all 31 granted agents satisfy a comparison
made against `config/agent_registry.json` or `templates/agents/*.md` while
receiving nothing. So:

- Evidence = the BUILT artifact, always. ADR-050 already decided this for the
  reachability guard ("the capability set comes from the built argparse parser and
  never from source text") — cite it rather than re-arguing it.
- Every such AC needs a **mutation descriptor** in `test_spec`: break only the
  compiled artifact, leave the inputs correct, assert the check fails. A green
  assertion over a correct tree does not prove the assertion looks at the right
  artifact.
- Use `angle: deployed` / `angle: real_artifact` (docs/testing/test-angles.md).
  `test_spec` accepts `angle`, and it is the right vocabulary for exactly this.

## Vacuity is a first-class criterion in this store now — enrich for it

Three of the BA's AR-300 records make "a rule that resolves to nothing passes
forever" (KI-ACS-001) the criterion itself. The it_requirement shape that works:

- Derive BOTH populations at run time; report BOTH counts.
- Fail on zero AND on short (examined < the number the build compiled).
- Name WHICH side came back empty — the reader otherwise guesses.
- Reuse **ADR-037's verdict-object contract** (a mandatory per-namespace inspected
  count) so sibling guards share one shape instead of growing four report paths.
- Never let a quoted measurement become a constant. 31 / 60 / 32 / 40 / 12 were all
  measured on 2026-09-30; a hard-coded figure excludes the next agent.

## The file-size ratchet is a real scoping constraint, so check it during enrichment

Measured: `template_compiler.py` 496, `injection_builders.py` 876,
`build_placeholder_detection.py` 678 — all above the 400-content-line limit, and the
ratchet refuses a change that leaves an oversized file LONGER. So "add the check to
the compiler" is not an available design. Put it in the it_requirements: new logic
lands in a NEW module; edits to those files must be net-neutral or shorter. For
AR-300d-1 the expected diff direction is negative (deleting the marker-gated branch).

## Two registries again, third variant: `tools` is in the TEMPLATE, not the registry

Verified: `tools` appears in **0 of 61** `config/agent_registry.json` entries — it
lives only in template frontmatter, as a bare comma-separated string
(`tools: Bash, Read, Edit, Write, Agent`). The ability grant lives only in the
registry (split across `skills_used` 32 / `skills_invoked` 40, 12 in the newer
only). **That split is why the 25-agent capability mismatch is invisible**: the two
sides of the comparison are in different files. Consequence for enrichment: an AC
that compares grant-against-tools is NOT implementable from the definitions alone
until the grant moves into frontmatter — wire it as `expects_from` on the placement
AC and say so, rather than letting a coder discover it. (Generalises the GE-117
"which registry is this resolving against?" rule to a third pair.)

Also: because `tools:` is unstructured, pin an EXACT-match requirement on the
invoking-tool check — a substring match on `Agent` inside a longer token is a silent
false pass.

## Superseding a child whose parent was superseded: prefer supersede over re-parent

INF-600a-1-i (L3, reviewed, todo) survived its parent's supersession. Re-parenting
was rejected on two grounds worth reusing:

1. **Its criteria name the demoted source.** The Given says "an agent registry entry
   where `skills_invoked` ...". If the new design makes that field derived, a
   re-parented record still validates the copy nobody may believe — the same
   contradiction, relocated to the leaf. Criteria are the BA's text and not the IT
   PO's to rewrite, so a record whose SUBJECT was demoted must be retired whole.
2. **Cross-component re-parenting is structurally unavailable.** Parent coverage is
   derived from the id and requires the parent in the SAME feature folder. An
   INF-prefixed L3 cannot become a child of an AR-prefixed L2 without moving the
   file and changing the id — a supersession wearing a re-parent's clothes.

Recipe: `status: superseded_by` + `superseded_by: [<successor>]` + a structured
`amended_by` entry + a `notes` audit trail + reciprocal doc_links on BOTH records.
Leave `readiness` alone (user's gate) and `work_status: todo` (never implemented —
marking it done would be a false claim). Leave the superseded parent's `covered_by`
as the historical link.

## Assignment spine for this cluster (no splits were needed)

All 25 behavioural leaves = `python-coder`; the one reference-doc leaf
(AR-300c-4, satisfying AR-300c's `documentation_triggers: [reference-doc]`) =
`documentation-expert` + `test_required: false`. No `llm-expert` split even though
two ACs touch `templates/agents/*.md`, because both touches are structural rather
than prose: a frontmatter-key backfill (AR-300c-2) and the deletion of one
hand-written section (AR-300a-4). `.md` is a matched surface for python-coder under
the S2.8 table, so neither is a technology contradiction. Test homes:
`unit_tests/prompt_assembly/` for compiler/prompt work, `unit_tests/agents/` for
registry-vs-template comparisons.

## Backfills into 60 tracked templates: the insert-only rule

AR-300c-2 writes a frontmatter key into ~44 of 60 tracked templates. Standing
it_requirements: second run byte-stable (run-twice-and-diff); infer-then-VALIDATE
before write; **insert only the target key, never rewrite the file or reformat
unrelated keys** (a 60-file reformat is an unreviewable diff); uninferable values go
to a review report, never a guessed value; and an entity with no source value gets
NO key rather than an empty one — an empty declaration produces the bare-heading
state a sibling AC explicitly forbids.
