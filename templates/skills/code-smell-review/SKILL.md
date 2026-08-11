---
name: code-smell-review
description: |
  Run a full Fowler code-smell review by fanning out to two specialised reviewers in
  parallel — find-structural-smells (Sonnet, the six local/mechanical smells) and
  find-design-smells (Opus, the six cross-cutting/judgment smells) — then merging their
  findings into one prioritised report. Cost-tiered and focused: each reviewer holds only
  its six smells. Runs in the top-level loop (not inside a sub-agent) so the parallel
  dispatch respects the depth-1 sub-agent limit.
  Use when: the user asks for a code-smell / refactoring review, "review this for smells",
  or invokes /code-smell-review.
allowed-tools:
  - Bash
  - Read
  - Write
  - Agent
---

# code-smell-review — parallel fan-out orchestration

This skill runs **in the top-level loop** (the main assistant, or a `/code-smell-review`
command). It must NOT be loaded inside a spawned sub-agent: a sub-agent cannot spawn further
sub-agents (Claude Code's depth-1 hard limit, ADR-006 "flatten the supervisor chain"). The
fan-out therefore lives here, at depth 0, and the two reviewers run at depth 1.

## Why two reviewers

The Modern-12 smells split by difficulty (see the two bucket skills):

- **Structural** (local / mechanical, near-lint) → `find-structural-smells` on **Sonnet**.
- **Design** (cross-cutting / judgment, needs whole-target reasoning) → `find-design-smells`
  on **Opus**.

Splitting keeps each reviewer focused on six smells (better recall than one agent juggling
twelve) and spends Opus only where judgment is needed.

## Steps

### 1. Resolve the target
Identify the code to review (attached/linked files → pasted code → else ask). Resolve it to a
concrete set of paths or a diff range so both reviewers see the same target. Do NOT do the
review yourself.

### 2. Fan out in parallel
Dispatch **both** reviewers in a **single message with two `Agent` tool calls** so they run
concurrently:

- `find-structural-smells` — pass the exact target. It returns its structural findings.
- `find-design-smells` — pass the same target. It returns its design findings.

Each reviewer loads the `review-for-code-smells` core + its own bucket skill and returns its
findings sections (not a file).

### 3. Merge
Combine the two returned finding sets into ONE report using the `review-for-code-smells`
output format:
- One shared **Inferred Context** table (reconcile the two stacks/intents; they should agree).
- One **Summary** table spanning all twelve smells and both reviewers' counts.
- **HIGH / MEDIUM / LOW** sections merging both sets; re-number IDs continuously (`H-1`,
  `H-2`, …) across the merged set, ordered by severity.
- **De-dup overlaps.** A finding both reviewers raised (e.g. a Repeated Switch that is also
  Shotgun Surgery) becomes one finding — keep the stronger framing, list all sites.
- One combined **Scorecard**.

### 4. Write and confirm
Write the merged report to `code-smells-{target-id}.md` at the workspace root. Confirm in
chat with a single sentence: the file path and the total finding count by severity.

## Degradation
- If one reviewer returns nothing usable (error / skip), write the report from the other's
  findings and state plainly in chat that only one bucket ran.
- For a tiny target (a single short function), it is fine to skip the fan-out and run one
  reviewer — but say so; do not silently narrow coverage.

## Constraints
- **Never review inside this skill.** Its job is dispatch + merge, not analysis.
- **One report, not two.** The two reviewers return findings; this skill writes the single
  merged file.
- **Respect depth-1.** Only the top-level loop runs this skill.
