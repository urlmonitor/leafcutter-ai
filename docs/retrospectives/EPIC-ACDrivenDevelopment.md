# Retrospective: EPIC-ACDrivenDevelopment

Date: 2026-06-05
Epic duration: 2026-06-05 (created) to 2026-06-05 (merged, PR #61)
Commits: 25 implementation + 1 merge-with-main + 1 merge commit = 27 total (branch: EPIC-ACDrivenDevelopment)

---

## Summary

EPIC-ACDrivenDevelopment inverted the backlog: where tickets were previously the
authoritative source of what needs to be built, the AC store is now the backlog.
Nine sub-tickets delivered the full pipeline in one sprint:

1. **AC readiness gate** (ticket 00) — schema fields `readiness`, `priority`, `documentation_triggers` added to AC YAML; PO/BA/IT PO pipeline enforces draft → reviewed → approved progression.
2. **AC scanner + ticket generator** (ticket 01) — `scan_acs.py` and `generate_ticket_from_ac.py` scripts; scan approved leaf ACs, emit wired ticket files.
3. **AC-aware ticket prioritizer** (ticket 02) — `ac_prioritizer.py` ranks ACs alongside tickets in a unified priority queue.
4. **AC done-linker** (ticket 03) — `mark_ac_done.py` and `link_ac_to_ticket.py` scripts; marks `work_status: done` when implementing ticket merges.
5. **/build-ac entry point** (ticket 04) — `build-ac` agent: AC → ticket → build → link-back end-to-end command registered in agent_registry.json.
6. **Cross-reference audit** (ticket 05) — `cross_reference_audit.py` finds existing tickets that satisfy ACs and backfills `implemented_by` fields.
7. **pick-next-ticket AC integration** (ticket 06) — `pick_next.py` updated; AC priorities feed into the existing ticket selection algorithm.
8. **Documentation** (ticket 07) — flow diagrams, AC state machine diagram, component diagram (AC store → scanner → ticket generator → build pipeline), and how-to guide.
9. **/create-ac workflow** (ticket 08) — `ac-triage` (Haiku) → PO/BA/IT PO routing → user confirmation gates → AC store output. Registered as skill `create-ac` and agent `ac-triage`.

---

## Metrics

| Component | Status |
|-----------|--------|
| AC readiness gate (readiness/priority schema) | Done |
| scan_acs.py + generate_ticket_from_ac.py | Done |
| ac_prioritizer.py (unified priority queue) | Done |
| mark_ac_done.py + link_ac_to_ticket.py | Done |
| build-ac agent registered in agent_registry.json | Done |
| cross_reference_audit.py (implemented_by backfill) | Done |
| pick_next.py AC priority integration | Done |
| Flow diagrams, state machine, component diagram, how-to guide | Done |
| ac-triage agent + create-ac skill registered | Done |

All 9 tickets completed. No failures. No blocked tickets.

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 9 sub-tickets |
| Completed tickets | 9 |
| Git commits | 27 (25 feature + 1 merge-main + 1 merge commit) |
| PR | #61 (urlmonitor/leafcutter-ai) |
| Merge commit | f5f298b |
| Breaking change | No |
| ADRs authored | 0 |
| Agents added | build-ac, ac-triage |
| Skills added | create-ac, ac-tree-split (merged from main) |
| Commits behind main at merge time | 47 |
| Conflict files | 3 (agent_registry.json, skill_registry.json, ACS-100a.yaml) |

---

## What Went Well

- **Clean dependency graph executed in order.** All 9 tickets followed the planned dependency chain (00 first, 01/08 after 00, 02/03/05 after 01, 04 after 02+03, 06 after 02, 07 after 00+04). No ticket was blocked waiting for another.

- **Test regression caught and fixed before merge.** SHA 399017a fixed missing `priority`/`readiness` fields in test fixtures that would have caused post-merge test failures. The finalization pre-merge test run caught this and it was resolved on the branch.

- **Haiku-pinned triage is an effective pattern.** Using Haiku (not Sonnet) for the ac-triage stage with a hard read-only constraint and a < 3s target is a reusable pattern for any routing stage that needs speed over depth.

- **Additive design: no existing workflows broken.** The human-authored ticket flow coexists with the new AC-originated flow. Both `/create-ticket` (v1/v2) and `/create-ac` are live simultaneously. No migration required.

---

## Friction Points

- **47-commit drift at merge time.** The branch was 47 commits behind origin/main when the PR was ready to merge, causing conflicts in agent_registry.json, skill_registry.json, and ACS-100a.yaml. The conflicts were additive (both sides added new entries to existing arrays) but required manual resolution because json.dump reformats the file. A pre-merge `git merge origin/main` convention mid-epic would reduce this drift.

- **JSON conflict resolution is fragile without tooling.** The sandbox shell restrictions (no heredocs, no multi-line python -c) made it difficult to write a resolution script. The workaround (building scripts line-by-line with printf >> ) was tedious and error-prone. A `resolve-conflict` skill that delegates to a python script file would be more robust.

- **Test fixture drift on new schema fields.** Ticket 00 added `priority` and `readiness` as required fields but the test fixtures for tickets 01-08 were not updated in the same commit. This caused a last-minute fix commit (399017a) after all other tickets were already done. New required AC schema fields should trigger a fixture-update pass before closing ticket 00.

---

## Proposed Improvements

### KI-1: Mid-epic sync convention for long-running feature branches

After every 3rd ticket merge on a long-running epic branch, run `git merge origin/main --no-commit --no-ff` to detect conflicts early. This should be added as a checkpoint in the `build-epic` workflow guidance, triggered when `git rev-list --count origin/main..HEAD` exceeds 20.

Routing: `templates/skills/build-epic/SKILL.md` — add as a periodic sync checkpoint.

### KI-2: New required AC schema fields must trigger a fixture-update pass before the defining ticket closes

When a ticket adds a new required field to an AC YAML schema, the ACs for all other sub-tickets in the same epic must be updated in the same commit (or in a follow-up commit before the ticket is marked done). This prevents the "last-minute fixture fix" pattern seen in this epic.

Routing: `templates/skills/ticket-authoring/SKILL.md` — add as a sign-off checklist item when `requires_schema_change: true` is in ticket frontmatter.

---

*All proposed KIs above require explicit user approval before being applied. No files have been modified by this retrospective.*
