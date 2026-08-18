---
title: "KI-002: Five defects in the done-proof gates that misreport AC coverage"
description: "Known issue: five defects in the proof-of-done gates — the composite path ignores a child's test_required exemption, legacy covered_by entries make children vanish, multi-id covers tags are mis-parsed, the schema hook and the oracle disagree about what a leaf is, and the pre-commit gate is stricter than the CI backstop it approximates."
type: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - build_orchestration
  - commit_guardian
related_docs:
  - docs/known-issues/README.md
  - scripts/ac_store/done_proof.py
---

# KI-002: Five defects in the done-proof gates that misreport AC coverage

**Area:** `build_orchestration` (`scripts/ac_store/done_proof.py`) with
`commit_guardian` (`check_done_proof.py`, `_ac_schema_validators.py`)
**Status:** open, not fixed on `main`
**First recorded:** 2026-08-18, during the build-orchestration proof-of-done remediation

All five were found by running the real gates over the store rather than by
reading them, and each is reproduced below. None was fixed in passing: changing a
gate's verdict is a behaviour change to a contract, which per CLAUDE.md
("New Work Goes Through ACs") needs an acceptance criterion authored first.

Context for why these stayed hidden: the CI job runs
`check_done_proof.py --mode ci-changed`, which only evaluates ACs in the diff.
The whole-store mode (`--mode ci`, `check_all_done_acs`) has never run in CI, so
none of these produced a visible failure.

---

## D-1 — The composite path ignores a child's `test_required: false`

`check_all_done_acs()` honours `test_required: false` for the AC it is about to
evaluate, but `_verify_composite_eligible()` never reads that field when
checking children. `_build_ac_status_map()` does not even carry it, so the
function structurally cannot honour the exemption.

**Consequence:** a composite whose only uncovered children are legitimately
test-exempt (a Mermaid diagram, a how-to, an agent-prompt convention) can
**never** become eligible.

**Reproduce:**

```
verify_done_eligible('BO-2300a', ac_root=docs/acceptance-criteria, test_root=.)
-> eligible: False
   reason  : composite BO-2300a has uncovered children: BO-2300a-3
```

`BO-2300a-3` is a state-diagram AC carrying `test_required: false`, and its
deliverable (`docs/architecture/diagrams/c3-001-interactive-pause-resume-run-lifecycle.md`)
exists on disk. Three ACs are currently in this state: `BO-2300`, `BO-2300a`,
`BO-2300d`. They were deliberately left `work_status: done`, because flipping
them would record a different lie — the work is genuinely delivered.

---

## D-2 — Legacy `covered_by` entries make a child vanish

`_resolve_all_child_ids()` recurses with `if child_covered_by:` — truthiness —
rather than checking whether any entry actually resolves to a store record. The
legacy-path guard (`_has_resolvable_child`, the BO-2500a-6 M-2 remediation) is
applied by the top-level caller but **not** at each recursion step.

**Consequence:** a child whose own `covered_by` holds only a legacy test-file
path is treated as a composite with no leaves and contributes nothing, so the
parent reports "no coverable children" instead of naming the real untested
child.

**Reproduce:**

```
BO-510-3.covered_by   = ['BO-510-3-i', 'unit_tests/test_agent_produces_validation.py']
BO-510-3-i.covered_by = ['unit_tests/test_agent_produces_validation.py']

verify_done_eligible('BO-510-3', ...) -> "composite BO-510-3 has no coverable children"
```

The correct verdict names `BO-510-3-i`.

---

## D-3 — Multi-id `covers:` tags are mis-parsed

`COVERS_TAG_RE = re.compile(r"(?:#|//)\s*covers:\s*(\S+)")`
(`scripts/ac_store/test_enforcement.py`) captures a single `\S+` token. On a
line naming two ACs it swallows the comma into the first id and drops the
second entirely.

**Consequence:** the first AC is registered under an id that matches nothing
(so it reads as untested *and* as a dangling tag), and the second is not
registered at all.

**Reproduce:** running `_scan_single_test_file()` over
`unit_tests/test_ticket_frontmatter_guard.py` (before the fix on
`fix/ac-schema-conformance-33`) registered `'BO-610-1,'` and `'BO-610-2,'` —
with trailing commas — for these lines:

```python
# covers: BO-610-1, BO-610-3-i
# covers: BO-610-2, BO-610-4-i
```

`BO-610-1` and `BO-610-2` were both `work_status: done` with **passing** tests,
yet the oracle reported "no linked test found" for each.

**Partial mitigation already landed:** those two tag lines were split one-id-per
line, which makes both ACs eligible. The regex itself is unchanged, so the trap
is still live for the next author. Two more occurrences remain in
`unit_tests/test_generate_ticket_from_ac.py` (`BO-530`, `BO-560`); they are
`work_status: todo`, so they cause no wrong verdict today.

Fixing the regex to split on commas would be a one-line change, but it alters
what the gate accepts and so needs an AC first.

---

## D-4 — Two gates disagree about what a leaf is

| Gate | Definition |
|------|-----------|
| `_is_leaf_ac()` in `_ac_schema_validators.py` | `level` is `L2` or `L3` |
| `verify_done_eligible()` in `done_proof.py` | `covered_by` resolves to no real AC record |

An `L2` AC that has real children is a **leaf** to the schema hook and a
**composite** to the oracle. The schema hook therefore demands its own
`test_spec` while the oracle derives its proof from its children.

**Observed on:** `BO-1500a-1`, `BO-1500b-1`, `BO-1500c-1`. Each was corrected
from `work_status: done` to `in_progress`, which brought them into the schema
rule's scope (it fires on `readiness: approved` AND `work_status != done` AND
code AC AND leaf AC) and produced:

```
approved code AC must declare a test contract — add a non-empty test_spec
```

This was resolved by authoring an integration-level contract on each parent,
distinct from its children's unit contracts — a defensible outcome. But the
divergence itself is unresolved, and it means the two gates can demand
contradictory things of the same AC.

---

## D-5 — The pre-commit gate is stricter than the CI backstop it approximates

`check_staged_done_proofs()` — the pre-commit path in `check_done_proof.py` —
never reads `test_required`. Its two siblings both do:
`check_all_done_acs()` (line ~463) and `check_changed_done_acs()` (line ~531)
each skip an AC with `test_required: false` before evaluating it.

The module docstring documents the exemption for those two functions and is
silent about the pre-commit one, so the omission may have been deliberate. It is
still incoherent in effect: the same docstring describes the pre-commit check as
the fast static approximation and CI as "the authoritative backstop". An
approximation that is **stricter** than its backstop blocks commits that CI
would pass.

**Consequence:** an AC that is legitimately `test_required: false` and
`work_status: done` can never appear in a staged diff again. Editing so much as
a stale path in one of those files is uncommittable without `SKIP=`.

**Observed on** this branch. Three ACs — `BO-202`, `BO-2300a-3`, `BO-2300d-2` —
are all `test_required: false`, all `work_status: done`, and all have their real
deliverables present on disk (`templates/agents/ac-fulfillment-gate.md`,
`docs/architecture/diagrams/c3-001-*.md`, `docs/architecture/diagrams/c3-002-*.md`).
Two of them carry a stale `implemented_by` pointing at
`tickets/00_inbox/TICKET-20260720-BO-2300a-3.md`; that ticket now lives at
`tickets/99_done/`. Correcting that one-line path was abandoned rather than
bypass the gate a second time, so **the stale pointer is still there**.

Fixing D-5 would be a one-line change mirroring the siblings, but it widens a
phantom-done gate, so it needs an AC and a test rather than an in-passing edit.

---

## Owner / next step

Owner: whoever owns `build_orchestration` / the proof-of-done gate.

Suggested order:

1. **D-5** — cheapest, and it is actively making three ACs uneditable. Fixing it
   also lets the stale `implemented_by` paths on `BO-2300a-3` / `BO-2300d-2` be
   corrected, which is currently impossible without a bypass.
2. **D-3** — small, and it currently produces false "untested" verdicts on ACs
   that are genuinely covered.
3. **D-1** — blocks three ACs permanently today.
4. **D-2** — wrong diagnostic rather than a wrong pass/fail, so lower urgency.
5. **D-4** — needs a decision on which definition is canonical, then align both.

Worth pairing with a decision about whether the whole-store sweep
(`--mode ci`) should run in CI at all. It currently cannot pass, and turning it
on before D-1 and D-2 are fixed would block every merge.
