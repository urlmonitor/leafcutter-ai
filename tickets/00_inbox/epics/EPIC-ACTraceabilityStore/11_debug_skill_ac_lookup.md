---
title: "Debug flow AC lookup — debug skill queries ACs for full context"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 02_ac_store_directory_scaffold.md
  - 05_ba_agent_ac_query.md
priority: medium
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/skills/debug/SKILL.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 11: Debug flow AC lookup — debug skill queries ACs for full context

## Actor / Goal

In order to give the debug skill's investigative agents a grounded picture
of expected behaviour before they begin diagnosis, we need to add an AC
store query step to `templates/skills/debug/SKILL.md` (before the three
investigative agents are spawned), so that investigators receive the
declared expected behaviour for the components under examination as part
of their initial prompt rather than having to infer it from code alone.

## Context

The debug skill (`/debug`) orchestrates three parallel investigative agents
(database, backend, frontend/docs) to diagnose a reported issue. Currently
each investigator is given only the raw issue description — it has no
access to the system's declared expected behaviour (i.e., the ACs that
govern the components it is investigating).

With the AC store in place (ticket 02) and the BA query pattern established
(ticket 05), the debug skill can follow the same read pattern: for each
component implied by the issue description, load the active ACs from
`docs/acceptance-criteria/{component}/` and embed them in the investigator
prompts under a `## Declared Expected Behaviour` header.

This matters because:

1. **Root-cause precision.** An investigator that knows "AC AUTH-003
   says the session token must be rotated on every login" can immediately
   flag a violation when it finds code that reuses the old token — without
   needing to infer that requirement from naming conventions or comments.
2. **Stale-AC detection.** If the investigator finds that the code
   contradicts an active AC it was given, it can surface "possible AC
   staleness" as a distinct hypothesis rather than classifying it purely
   as a regression.
3. **Reduced hallucination.** Grounding investigators with machine-readable
   ACs narrows the hypothesis space and reduces the chance of fabricated
   causal chains.

### Query pattern (mirrors ticket 05 BA pattern)

Before spawning the three investigative agents, the debug skill performs
a lightweight AC query:

1. **Component inference** — from the issue description, the skill
   attempts to identify 1–3 relevant component slugs. If the description
   mentions a file path (e.g., `templates/agents/business-analyst.md`),
   use the enclosing module as the component slug. If ambiguous, include
   all plausible candidates.
2. **AC load** — for each inferred component slug, read all `.yaml` files
   under `docs/acceptance-criteria/{component}/` where `status: active`.
   Extract `id`, `title`, and `criteria` for each.
3. **Fallback** — if `docs/acceptance-criteria/` does not exist in the
   target project, skip the query step entirely and proceed to the
   investigative agents as before. Log: "AC store not found — investigators
   will work without declared expected behaviour."
4. **Inject into investigator prompts** — add a `## Declared Expected
   Behaviour` section to each investigator prompt containing the loaded
   ACs in the format below. If no ACs were found for the inferred
   components, omit the section entirely.

### AC injection format (per investigator prompt)

```
## Declared Expected Behaviour

The following active Acceptance Criteria govern the components most likely
involved in this issue. Use them as ground truth when evaluating whether
observed behaviour is a regression or an intended design:

AC-{ID}: {title}
  {criteria (indented, verbatim from YAML)}

AC-{ID}: {title}
  {criteria}
```

### Dependency rationale

- **02_ac_store_directory_scaffold.md**: the `docs/acceptance-criteria/`
  directory must exist in the target project for the query to have any
  files to read. The fallback handles pre-ticket-02 installs gracefully,
  but the productive path requires ticket 02 to have shipped.
- **05_ba_agent_ac_query.md**: this ticket borrows the same component-
  inference and file-read pattern established for the BA agent. Ticket 05
  must be merged first so that the debug skill can reference the settled
  pattern rather than reinventing it.

### Relationship to ticket 08

Ticket 08 (triage agent AC lookup) looks up ACs *after* a test has
failed, using the `# covers:` tag to identify the specific AC. This
ticket looks up ACs *before* investigation begins, using component
inference rather than a tag. The two lookups are complementary and
independent — they do not share code paths.

## Acceptance Criteria

```gherkin
Given templates/skills/debug/SKILL.md is updated with the AC query step
 And docs/acceptance-criteria/finalize/ exists with two active AC YAML files
 And the issue description mentions the finalize component
When the debug skill is invoked
Then the skill reads both AC files before spawning investigative agents
 And each investigator prompt contains a "## Declared Expected Behaviour" section
 And the section lists each active AC's id, title, and criteria verbatim

Given templates/skills/debug/SKILL.md is updated with the AC query step
 And docs/acceptance-criteria/ does not exist in the target project
When the debug skill is invoked
Then the AC query step is skipped
 And the skill logs "AC store not found — investigators will work without declared expected behaviour"
 And the three investigative agents are spawned with their existing prompts unchanged

Given templates/skills/debug/SKILL.md is updated with the AC query step
 And docs/acceptance-criteria/ exists but contains no active ACs for the inferred components
When the debug skill is invoked
Then the "## Declared Expected Behaviour" section is omitted from the investigator prompts
 And the skill proceeds to spawn the investigative agents without error

Given the debug skill infers components from a file path in the issue description
When the path is "templates/agents/business-analyst.md"
Then the inferred component slug is "business-analyst" (or the enclosing module)
 And the skill reads docs/acceptance-criteria/business-analyst/ for active ACs

Given the debug skill runs the AC query step
When the issue description does not mention any recognisable component slug
Then the skill notes "component inference ambiguous" in its log
 And loads ACs for all components that exist under docs/acceptance-criteria/
 And caps the total number of injected ACs at 10 to avoid overwhelming the investigator prompt
```

## Sign-offs

- [x] documentation-expert — 2026-06-04 14:00
- [x] pr-reviewer — 2026-06-04 14:05
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-04 14:00 — documentation-expert (status: ok)
feedback-id: fb_2026-06-04_ba9a024d
completion_manifest:
  step0_ac_store_query_added: true
  ac_context_injected_all_three_agents: true
  overview_numbering_updated: true
  step_cross_references_updated: true
Added Step 0 (AC Store Query) to templates/skills/debug/SKILL.md immediately before the existing Step 1; updated the Overview to list AC Lookup as step 1 of the workflow; injected `{AC_CONTEXT}` into all three investigator prompt templates after the `**Issue:**` line; updated Step 1 header to document the AC_CONTEXT parameter; updated Step 2 header to reference Step 1 explicitly. All implementation tasks complete.

### 2026-06-04 14:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_9d99d4e2
completion_manifest:
  all_acs_verified: true
  fallback_log_message_present: true
  ac_context_injected_all_three_prompts: true
  file_path_slug_inference_documented: true
  ambiguous_inference_cap_at_10: true
All 5 ACs are satisfied. Step 0 correctly handles the absent-store fallback (logs exact message from AC 2), empty-AC omission (AC 3), file-path slug inference using the business-analyst example (AC 4), and ambiguous-inference with a 10-AC cap (AC 5). All three investigator prompts have {AC_CONTEXT} injected after the Issue line (AC 1). No rework required.

## Implementation Tasks

- [x] In `templates/skills/debug/SKILL.md`, add a new **Step 0 — AC Store
  Query** immediately before the existing Step 1:

  **Step 0 — AC Store Query**

  Before spawning the investigative agents:

  1. Check if `docs/acceptance-criteria/` exists in the target project.
     If it does not exist, log the fallback message and skip to Step 1.
  2. Infer 1–3 component slugs from the issue description:
     - If the description contains a file path, extract the enclosing
       directory or module name and normalise to lowercase-hyphenated slug.
     - If the description mentions a component by name (e.g., "finalize",
       "business-analyst"), use that slug directly.
     - If ambiguous: use all slugs that have a directory under
       `docs/acceptance-criteria/`.
  3. For each inferred slug: read all `.yaml` files under
     `docs/acceptance-criteria/{slug}/` where `status: active`. Extract
     `id`, `title`, and `criteria`.
  4. If no ACs are found across all inferred components, skip injection.
  5. If ACs are found: build the `## Declared Expected Behaviour` block
     using the injection format above. Cap at 10 ACs total (take the first
     10 by filename sort if more exist).
  6. Store the block in a variable `AC_CONTEXT`. It is injected into each
     investigator prompt in Step 1.

- [x] In Step 1 of `templates/skills/debug/SKILL.md`, update each of the
  three investigator prompt templates to include `{AC_CONTEXT}` immediately
  after the `**Issue:** {$ARGUMENTS}` line. When `AC_CONTEXT` is empty or
  the AC store was absent, `{AC_CONTEXT}` expands to an empty string (no
  visible section added).

- [x] Ensure the existing Step numbering in the skill shifts: current Step 1
  becomes Step 2, Step 2 → Step 3, and so on. Update all cross-references
  within the skill file (e.g., "Proceed to Step 2" → "Proceed to Step 3").

## Risk & Safety

- Touches money? No.
- Touches data? No. Read-only AC file access; no AC files are written or
  modified by this ticket.
- Reversibility? Template edit only. Reverting `templates/skills/debug/SKILL.md`
  to its prior version fully restores the original three-agent debug
  workflow. Existing AC files in any target project are not affected.
- If the AC store is absent or component inference fails, the debug skill
  degrades gracefully to its existing behaviour with no visible change for
  the user. The enhancement is purely additive and opt-in by presence of
  the AC store.
- The 10-AC cap prevents excessively long investigator prompts that could
  push relevant content out of the context window.
