---
name: ac-tree-split
description: |
  Guided procedure for splitting overcrowded AC trees. Loaded by PO v3 (for L0/L1 splits)
  and BA v3 (for L2 redistribution). Prompt-based — no enforcement scripts. Covers
  horizontal splits (same component, new sibling L0) and intermediate splits (L1 split
  into sibling L1s). Vertical splits (new sub-component) deferred to v2.
trigger: |
  Load when the AC validator flags an overcrowded parent (>7 L1s per L0, >5 L2s per L1),
  or when an agent is about to create a child that would exceed the limit.
tools: Read, Write, Bash
portable: true
visibility: internal
---

# AC Tree Split — Guided Procedure

This skill provides step-by-step instructions for splitting an overcrowded AC tree
into well-formed subtrees. It is prompt-based: no enforcement scripts, no automated
rewiring. The calling agent (PO v3 or BA v3) reads these instructions and executes
them manually, pausing at each confirmation gate.

---

## 1 When to Split

Three triggers cause this skill to activate:

1. **Hard trigger (validator flag).**
   The AC validator reports a parent exceeding its child limit:
   - L0 with **>7 L1 children** (covered_by count exceeds 7)
   - L1 with **>5 L2 children** (covered_by count exceeds 5)

2. **Pre-creation gate.**
   You are about to create the Nth child that would push a parent over the limit.
   **Stop before writing the file.** Load this skill, run the split, then create
   the new child under the correct (possibly new) parent.

3. **Semantic trigger (agent-detected).**
   Even below the hard limit, children may cluster into 2+ distinct themes.
   If you detect this, recommend a split to the user with a brief rationale.
   **The user must confirm before proceeding** — semantic splits are advisory,
   not mandatory.

---

## 2 Split Patterns

### Pattern A — Horizontal Split (v1)

**When:** An L0 has too many L1 children and they cluster into distinct themes.

**Procedure:**

1. **Read** the overcrowded L0 and ALL of its L1 children (every file listed
   in the L0's `covered_by`).

2. **Cluster** children by semantic similarity. Look for shared signals:
   - Common themes in their `criteria` text
   - Same `assigned_agent`
   - Overlapping `depends_on` targets
   - Related `delivers_to` / `expects_from` contracts

3. **Propose split.** Draft a table showing which L1s go to which new L0:

   ```
   Original L0: ACS-100 "Requirements that build themselves"
   
   Group A (stays with ACS-100):
     - ACS-100a: "Every requirement carries its full context"
     - ACS-100b: "Requirements know their neighbors"
     - ACS-100c: "One source of truth for what a component means"
   
   Group B (moves to new ACS-101):
     - ACS-100d: "Changes leave a trail"
     - ACS-100e: "Requirements that check themselves"
     - ACS-100f: "Find any requirement in seconds"
   ```

4. **GATE: Cluster approval.**
   Present the cluster proposal to the calling agent or user.
   Ask: "Does this grouping make sense? Should any L1s move between groups?"
   **Do not proceed until approved.**

5. **Create new L0 file** in the same feature folder (e.g., `ACS-101.yaml`).
   Use the next available ID in the component's sequence.
   Set fields:
   - `level: L0`
   - `status: active`
   - `req_status: active`
   - `work_status: todo`
   - `covered_by: []` (will be populated in step 8)
   - `depends_on: []`
   - `origin_agent:` same as original L0

6. **Update moved L1s.** For each L1 moving to the new parent:
   - Add the new L0 ID to its `depends_on` list
   - Remove the old L0 ID from its `depends_on` list
   - **L1 IDs do NOT change** — this is critical. ACS-100d stays ACS-100d.

   > **Pattern A note on ID stability and the limit hook:** The
   > `check-ac-tree-limits` hook counts L1 children under an L0 by ID-string
   > derivation (it strips the last segment via `_derive_parent_id`). L1 IDs
   > keep their original prefix (e.g. `ACS-100d`), so the hook has no
   > structural knowledge of which L0 "owns" them — it derives the parent
   > purely from the ID string. This means L1 IDs that did not include the L0
   > ID as a prefix segment (or that share an ambiguous prefix with two L0s)
   > could be miscounted. In the standard scheme where L1 IDs are
   > `<L0-id><alpha-suffix>` (e.g. `ACS-100d` under `ACS-100`), moving
   > `ACS-100d` to `ACS-101` keeps the derived parent as `ACS-100` — so
   > Pattern A L1 moves may not reduce the hook's count for the original L0
   > either, depending on the ID naming convention in use. Verify with a
   > manual `pre-commit run check-ac-tree-limits` after the split. If the
   > hook still flags the original L0, L1 IDs may also require renaming —
   > apply the same store-wide grep procedure described in Pattern C step 6.

7. **Update original L0.** Remove moved L1 IDs from its `covered_by` list.

8. **Update new L0.** Set `covered_by` to the list of moved L1 IDs.

9. **GATE: Blast radius preview.**
   Count and list all modified files. Present to the agent/user:
   ```
   Blast radius:
     - 1 new file created (ACS-101.yaml)
     - 3 L1s updated (depends_on changed)
     - 1 L0 updated (covered_by trimmed)
     Total: 5 files touched
   ```
   Agent checks the list and makes a recommendation (proceed / revise).
   **User can override the agent's recommendation.**

10. **Revise original L0 criteria.** The original L0 now covers fewer L1s.
    Its `criteria` text should be narrowed to reflect the reduced scope.
    **Flag this revision for PO review** — L0 criteria are PO domain.

11. **Validate.** Run the AC validator to confirm:
    - Both parents are below the limit
    - No parent has fewer than 3 children (sparse advisory — warn but don't block)
    - No `depends_on` cycles introduced
    - No dangling `delivers_to` / `expects_from` references

---

### Pattern C — Intermediate Split (v1)

**When:** An L1 has too many L2 children and they cluster into sub-behaviors.

> **Override alternative.** Before splitting, consider whether the overcrowding
> is deliberate and temporary. A parent AC may carry `child_limit_override: <int>`
> to explicitly raise its own cap without restructuring:
> ```yaml
> child_limit_override: 8   # auditable exception; remove when resolved
> ```
> `check_ac_limits.py` reads this field and skips the limit check for that
> parent. Use the override for a short-lived, intentional exception; use
> Pattern C (with the rename procedure below) for a genuine structural
> rebalance.

**Procedure:**

1. **Read** the overcrowded L1 and ALL of its L2 children.

2. **Cluster** L2s by behavioral theme. Look for:
   - Groups of L2s that test the same sub-feature
   - L2s with shared `assigned_agent` or shared `depends_on`

3. **Propose new L1 siblings.** Draft titles for the new L1s that will
   replace the overcrowded one. Each title should be a customer-value
   statement (PO language, not engineering).

4. **GATE: PO approves new L1 titles.**
   New L1 titles are PO domain. Present the proposed titles and wait
   for PO approval. PO may rewrite titles — accept their version.

5. **Create new L1 files** under the same L0 parent.
   Set fields:
   - `level: L1`
   - `depends_on:` include the parent L0
   - `covered_by: []` (populated after L2 redistribution)

6. **Rename and redistribute L2s.** This is the critical step.

   > **Why renaming is mandatory:** `check_ac_limits.py` (the
   > `check-ac-tree-limits` pre-commit hook) counts a parent's children by
   > ID-string derivation — it strips the last ID segment to infer the parent
   > (`_derive_parent_id`). It deliberately does NOT use `covered_by` or
   > `depends_on` references to count children (per GE-106, to prevent
   > cross-links from gaming limits). A moved L2 that retains its old ID prefix
   > still registers as a child of the original L1 in the hook's view, so the
   > commit is still blocked even after rewiring `depends_on`. **Moved L2s MUST
   > be renamed** so their ID prefix matches the new parent L1.
   >
   > Real-world precedent: splitting TKT-500d required renaming
   > TKT-500d-6..10 to TKT-500f-1..5 to clear the hook.

   For each L2 being moved to a new parent L1:

   a. **Rename the file** to reflect the new parent prefix. Example: if
      `ACS-100d-6.yaml` moves under new sibling L1 `ACS-100f`, rename it
      `ACS-100f-1.yaml` (assign sequential IDs starting at 1 for the new
      parent). The old filename must no longer exist.

   b. **Update the file's own ID field** to match the new filename.

   c. **Update `depends_on`** inside the renamed file: reference the new L1 ID,
      remove the old L1 ID.

   d. **Grep the entire AC store for every old L2 ID** before committing.
      Any reference to the old ID — in `depends_on`, `covered_by`,
      `delivers_to`, `expects_from`, `superseded_by`, or `amended_by` in
      ANY file in the store — must be updated to the new ID. Run a search
      across all YAML files in the store for each old ID string:

      ```bash
      grep -r "ACS-100d-6" /path/to/ac-store/
      ```

      Repeat for every renamed ID. Update every match found.

   e. **After renaming all files**, run a second grep pass to confirm no
      stale references remain in the store.

7. **Mark original L1 as superseded.** Set `superseded_by: [new-L1-a, new-L1-b]`
   on the original overcrowded L1. Do NOT delete it — it serves as an
   audit trail.

8. **Update parent L0's covered_by.** Remove the old L1 ID, add all new L1 IDs.

9. **Update new L1s' covered_by.** Set `covered_by` on each new L1 to the list
   of renamed L2 IDs that now belong to it.

10. **GATE: Blast radius preview.**
    Count and list all modified files. The blast radius of a Pattern C split is
    larger than it appears: in addition to the L1 and L0 files, every renamed L2
    and every file anywhere in the store that referenced an old L2 ID is modified.
    Present the full list.
    Agent checks and makes a suggestion. **User can override.**

11. **Validate.** Run the AC validator to confirm:
    - No sparse parents (fewer than 3 children — warn if so)
    - No dangling references
    - No `depends_on` cycles
    - The hook `check-ac-tree-limits` no longer flags the original L1
      (run manually: `pre-commit run check-ac-tree-limits`)

---

### Pattern B — Vertical Split (DEFERRED to v2)

**When:** A subset of children represents a distinct standalone capability that
deserves its own component.

**Why deferred:** Vertical splits require a `parents` field in `components.json`
to track component hierarchy. That field does not exist yet. Without it, vertical
splits would require ID changes (e.g., ACS-100d becomes ACS-200a), which cascade
across the entire store — every `depends_on`, `delivers_to`, `expects_from`, and
`covered_by` reference must be updated.

**Cost:** High. ID changes are the most dangerous operation in the AC store.

**Will be added when:** `components.json` supports parent-child component
relationships, enabling ID-stable vertical splits.

---

## 3 Rewiring Rules

These rules govern how references are updated during a split.

| Field | Pattern A (Horizontal) | Pattern C (Intermediate) | Pattern B (Vertical, deferred) |
|-------|----------------------|------------------------|-------------------------------|
| `depends_on` | Update moved L1s: old L0 -> new L0. L2s under moved L1s are **unaffected** (L1 IDs don't change). | Update moved L2s: old L1 -> new L1. **L2 IDs CHANGE** (renamed to new parent prefix — see step 6). Update `depends_on` inside each renamed file. | All references change (IDs change). |
| `delivers_to` / `expects_from` | **No change.** Contracts reference AC IDs, not parent IDs. L1 IDs are stable. | **Must rewire.** L2 IDs change (renamed to new parent prefix), so all `delivers_to` / `expects_from` references to old L2 IDs anywhere in the store must be updated to new IDs. Grep the entire store for each old ID before committing. | Must rewire all contracts (IDs change). |
| `covered_by` | Remove from old parent, add to new parent. | Remove old L1 from L0, add new L1s to L0. Set `covered_by` on each new L1 to its renamed L2 IDs. | Remove from old component, add to new component. |
| `superseded_by` / `amended_by` | **Not set.** Original L0 is trimmed, not superseded. | Set `superseded_by` on original L1 pointing to new L1 siblings. Any `superseded_by` / `amended_by` references to old L2 IDs in other files must also be updated to new IDs. | Set on original component root. |

---

## 4 Confirmation Gates

Every split includes mandatory confirmation gates. Do not skip them.

| Gate | What is presented | Who confirms |
|------|-------------------|-------------|
| **Cluster proposal** | "Here are the proposed groups: [table of L1s per group]" | Calling agent (PO or BA) |
| **New parent titles** | "These are the proposed L0/L1 titles: [list]" | PO (always — L0/L1 titles are PO domain) |
| **Blast radius preview** | "N files modified, M references updated: [file list]" | Agent checks and makes suggestion; user can override |
| **Post-split validation** | "Validator confirms limits respected, no cycles, no dangling refs" | Automatic (report only, no approval needed) |

---

## 5 Audit Trail

Every split must leave a traceable record.

1. **`amended_by` field.** Set on every modified AC file:
   ```yaml
   amended_by:
     - reason: "split: ACS-100 -> ACS-100 + ACS-101, 2026-06-05"
   ```

2. **Git commit message.** Use this format:
   ```
   refactor(ac-store): split ACS-100 [horizontal, 8->4+4]
   ```
   Pattern: `refactor({component}): split {ID} [{pattern}, {old-count}->{new-counts}]`

3. **Structured summary.** Produce a summary suitable for a ticket comment
   or retrospective entry:
   ```
   Split summary:
     Pattern: Horizontal (Pattern A)
     Original: ACS-100 (8 L1s)
     Result: ACS-100 (4 L1s) + ACS-101 (4 L1s)
     Files created: 1
     Files modified: 5
     References rewired: 4 depends_on, 2 covered_by
     Validation: PASS (no cycles, no sparse parents, no dangling refs)
   ```

---

## 6 Validity Constraints

A split is valid if and only if ALL of the following hold:

1. **Below limit.** The overcrowded parent is now below its child limit
   (<=7 L1s for L0, <=5 L2s for L1).

2. **No sparse parents.** No parent created by the split has fewer than
   3 children. This is an **advisory** — warn but do not block. A sparse
   parent may be acceptable if more children are planned.

3. **No cycles.** The split does not introduce any `depends_on` cycles.
   Verify by walking the dependency graph from each modified AC.

4. **No unpaired contracts.** Every `delivers_to` has a matching `expects_from`
   and vice versa. Splits that break contract pairs are invalid.

---

## 7 Who Loads This Skill

| Agent | When | Patterns used |
|-------|------|---------------|
| **PO v3** | L0 splits, L1 title decisions | Pattern A (full), Pattern C (gate 4 only) |
| **BA v3** | L2 redistribution under a split L1 | Pattern C (steps 1-2, 6) |

The skill is **strategy-agnostic** — it presents clustering options and split
mechanics. Ownership decisions (which group gets which title, whether to split
at all) are deferred to the calling agent.

---

## 8 Design Decisions Log

These decisions were made during the design of this skill and should be
respected by all agents loading it.

| Decision | Rationale |
|----------|-----------|
| **Semantic splitting: agent detects and recommends, user confirms** | Agents can spot clusters, but theme boundaries are subjective. User confirmation prevents unwanted restructuring. |
| **Pre-creation gate: yes** | Preventing overcrowding is cheaper than fixing it. The gate fires before a file is written, not after. |
| **Shared folder after horizontal split: yes (v1)** | Splitting into separate folders adds complexity (path changes cascade). In v1, new L0s stay in the same feature folder. Folder splits may be added in v2. |
| **New L1 titles in Pattern C: skill proposes, PO approves** | L1 titles are customer-facing language. The skill can draft based on L2 clusters, but PO owns the final wording. |
| **Trimmed L0 criteria revised: yes, flagged for PO** | After losing children, the L0's criteria text may overstate scope. Revision is mandatory but PO-owned. |
| **Merge (reverse-split): deferred to v2** | Merging two L0s back into one is the inverse operation. It requires the same rewiring logic in reverse plus conflict detection. Not needed for initial deployment. |
| **Blast radius gate: agent checks and makes suggestion, user can override** | The agent has context to evaluate whether the blast radius is acceptable, but the user has final authority. This balances automation with safety. |
| **Vertical split: deferred to v2** | Requires a `parents` field in `components.json` (NOT `index.yaml`, which is deprecated). ID changes in vertical splits cascade across the entire store — too risky without component hierarchy support. |
| **Pattern C L2 rename: mandatory** | `check_ac_limits.py` counts children by ID-string derivation (`_derive_parent_id`), not by `covered_by`/`depends_on` (GE-106). A moved L2 that keeps its old ID prefix still registers under the original L1 in the hook's view, so the commit stays blocked. Renaming is the only way to clear the hook. Confirmed when splitting TKT-500d required renaming TKT-500d-6..10 to TKT-500f-1..5. |
| **child_limit_override escape hatch** | When an L1 genuinely needs more children than the default cap (e.g. closely related edge-cases that do not cluster cleanly), `child_limit_override: <int>` on the parent AC signals an intentional and auditable exception. The hook reads this field and skips the limit check for that parent. Use the override for temporary exceptions; use Pattern C (with rename) for structural rebalances. |
