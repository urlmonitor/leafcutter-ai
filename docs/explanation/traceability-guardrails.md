---
title: "Traceability guardrails: AC ↔ Code ↔ Tests ↔ Docs ↔ Flows"
description: "Which mechanical guardrails currently enforce the links between acceptance criteria, code, tests, documentation and product-truth flows; which layer each one runs in; where the holes are; and which AC families are planned to close them."
type: explanation
status: active
created: 2026-08-24
last_updated: 2026-08-24
components:
  - commit_guardian
  - precommit_hooks
  - ac_store
  - testing_quality
  - documentation_system
  - ux_prototyping
---

# Traceability guardrails

The harness assumes five artefacts stay linked: an **acceptance criterion**, the
**code** that implements it, the **test** that proves it, the **documentation**
that describes it, and the **product-truth flow** that places it in context.

A flow is not only a user journey. `flow.schema.json` types every flow with a
`kind` of `user`, `data`, or `architecture` — a user journey, a data pipeline, or
an architecture process — and today the store leans toward the non-user kinds:
7 `data`, 6 `user`, 1 `architecture`. The AC-linking machinery is identical for all
three: a step carries `implements: [AC ids]` whatever the flow describes, so
`leafcutter/generate-product-truth` (a data pipeline) is wired to its ACs exactly
the way `fern-and-fig/customer-buys-a-plant` (a user journey) is.

This doc answers one question: *if nobody runs a workflow and no agent is
dispatched, what still forces those links to exist and stay correct?*

The short answer: **the AC ↔ Tests and AC ↔ Flows links are mechanically
enforced. The AC ↔ Code and AC ↔ Docs links are not — they are authored by
agents and verified only by agents.**

---

## Where each link actually lives

| Link | Field of record | Direction of truth |
|---|---|---|
| AC → Code | `implemented_by` (AC YAML) | authored by the coder / ticket generator |
| AC → Test | `covered_by` (AC YAML) + `# covers: <AC-ID>` tag in the test | test tag is the machine-readable side |
| AC → Test contract | `test_spec` / `test_required` (AC YAML) | AC owns what must be tested, not the ticket |
| AC → Docs | `doc_links` (AC YAML), `documentation_triggers` (L1 only) | authored by PO/IT-PO |
| Flow → AC | `step.implements` (`*.flow.json`) | **the only authored direction**; AC `product_truth` is generated |
| Ticket → AC | `source_ac` (ticket frontmatter) | optional field |
| AC → AC | `depends_on` (child) + `covered_by` (parent) | both directions required |
| Code → Docs | `DOC_LINKS:` in module docstring | advisory only |

---

## The four enforcement layers

Only layers 2 and 3 satisfy the "no workflow, no agent" bar.

1. **Claude Code session hooks** (`.claude/hooks/`, wired in `.claude/settings.json`) —
   `documentation_guard.py`, `ticket_frontmatter_guard.py`, `inline_work_guard.py`,
   `check_commit_ticket_staged.py`, `enforce_commit_delegation.py`,
   `check_ticket_state_integrity.py`. These fire on Edit/Write/Bash inside a
   Claude session and **do not exist for a human with an editor**.
2. **Pre-commit** — 50 active hooks generated from
   `commit_guardian.json → hooks_manifest` into `.pre-commit-config.yaml`
   (6 `transform` tier, 44 `judgment` tier; 5 further hooks are registered but
   config-gated off). Bypassed by `--no-verify` or a worktree without the config.
3. **CI** (`.github/workflows/`) — 6 required status checks, plus non-required
   fixture-drift, agent-evals, schema-diff and an informational mypy job. This is
   the only layer that cannot be bypassed locally.
4. **Agent phases** — `test-writer`, `ac-validator`, `ac-fulfillment-gate`,
   `documentation-verifier`, `user-surface-smoker`. Real gates, but they only run
   when `ticket-supervisor` drives the ticket.

---

## What is live today

### AC store internal integrity — strong, both layers

Six hooks run at pre-commit **and** in the required CI job `AC store valid`
(PR-only, diff-scoped, using the same `pre-commit run <id>` invocations so the
two rule sets cannot drift):

| Hook | Enforces |
|---|---|
| `check-ac-schema` | JSON Schema (`config/ac_store_schema.json`) is authoritative; pattern-binding completeness; `implements_pattern` field preservation; **`test_spec`/`test_required` contract on approved leaf code ACs** |
| `check-ac-parent-covered-by` | a staged child's parent lists it in `covered_by` |
| `check-ac-circular-deps` | no cycles in `depends_on` |
| `check-ac-tree-limits` | depth / child-count caps |
| `check-ac-governance` | write-lock on requirement-defining fields |
| `check-ac-pattern-refs` | `implements_pattern` resolves |

The `validate_test_contract` check inside `check-ac-schema` is the single most
load-bearing AC ↔ Tests guardrail: an approved, not-yet-built **leaf code AC must
carry a non-empty `test_spec`** or be reclassified as non-code. It closes the
silent-skip hole where `test-writer` self-skipped TDD.

### AC ↔ Tests — enforced, and it has a CI backstop

- **`check-done-proof` (pre-commit)** — static, fast: for every AC newly flipped
  to `work_status: done`, a `# covers: <ac-id>` tag must exist somewhere in the
  test tree. Presence only, no test run.
- **`Proof-of-done coverage check` (CI, required)** — authoritative: runs
  `verify_done_eligible` over the ACs changed in the PR, actually executing the
  linked tests (Python via pytest, `.ts`/`.tsx` via vitest — the JS toolchain is
  installed in the job because the oracle fails *closed* when a runner is
  missing). `test_required: false` ACs are exempt. This catches `--no-verify`
  commits and hook-less worktrees.
- **`pytest_ac_enforcement` plugin** (loaded from `pytest.ini` for every pytest
  run) — a failing test whose `# covers:` AC is *not* done is downgraded to XFAIL
  so in-progress work does not block the suite. Masking is loud (per-test line +
  session summary) and CI runs with `AC_ENFORCE_STRICT=1`, so on the gate nothing
  is masked.
- **`check-contract-shrinking`** — blocks deleting/skipping/xfailing a test in the
  same commit as a production change.
- **`check-presence-only-assertions`** — a ratchet on staged hunks: rejects new
  tests over workflow/guardian source whose entire assertion is a grep for a
  symbol's text.

### AC ↔ Flows — the best-guarded link in the repo

`check-product-truth-validate` and `check-product-truth-generate --check` run at
pre-commit whenever `docs/product-truth/**` **or any AC YAML** is staged.
`generate_product_truth.py` is the single writer of every derived field, and the
validator recomputes all of it, so drift is impossible to commit:

- every `step.implements` AC id resolves (warning) and every `impl_status`,
  `impl_summary`, AC `product_truth` back-reference and `index.json` view equals a
  fresh recomputation (error);
- every step `screen` resolves to a registered mockup, `expands_to` resolves with
  no cycles;
- an **anti-phantom-done truth gate**: an AC referenced by a *built* flow whose
  status is `done`/`in_progress` must carry non-empty `implemented_by` (leaf) or
  `covered_by` (composite). Flows marked `realization: mock`/`spec` are exempt and
  the exemption is announced.

### Ticket ↔ AC — one hook

`check-ticket-ac-status-parity` blocks a staged ticket at `status: done` whose
`source_ac` has not reached `work_status: done`. Fails *open* when the AC file
cannot be found. `check-predone-scope` reconciles the actual diff against
`files_touched ∪ out_of_scope` — shipped **advisory** (`enabled: true`,
`strict: false`).

### Code ↔ Docs — mostly advisory

`check-structural-change` is the one real blocker: a structural signal (new
model/service/package, >50 added lines in a watched dir, SQL signature change)
without a staged `docs/components.json` fails the commit — escapable with
`[NO-ARCH-UPDATE]` in the message. `check-adr-cross-reference` is warn-only by
default; `check-adr-coverage` always exits 0. Frontmatter, description, index,
length, mermaid parent-links and glossary coverage are enforced on `docs/**`, so
docs that *do* exist are well-formed. Whether the right doc exists at all is not
checked.

### Required CI checks

`Lint (ruff)` · `Component vocab style (components.json)` ·
`Test suite (pytest)` (fresh build + `AC_ENFORCE_STRICT=1`, no
`continue-on-error`) · `Proof-of-done coverage check` ·
`AC store valid` · `Changelog entry present`.

---

## The holes

These are the gaps against your "pre-commit and CI lead the way" requirement.

**1. `implemented_by` is never verified.** Nothing — no hook, no CI job — checks
that the paths in an AC's `implemented_by` still exist, or that the symbol anchor
still resolves. A refactor silently breaks every AC → Code link it touches. The
AC ↔ Code edge is currently *documentation about code*, not a checked link.

**2. Nothing forces new code to declare an AC or a component.** You can add a file
with no `MODULE:`/component declaration and no AC reference and commit it. The
only reverse pressure is `Component vocab style`, which validates ids that are
already present.

**3. The test → AC tag is not required.** `check_test_ac_tags.py` exists and works
but is **not in `hooks_manifest`**, and its own default mode is `warn`. A new test
needs no `# covers:` tag. The tag is only demanded *retroactively*, by
`check-done-proof`, at the moment an AC flips to done. Its mirror,
`check_ac_coverage.py` (every active AC is pointed at by ≥1 test), is likewise
dormant and advisory-only by design.

**4. A ticket need not reference an AC.** `source_ac` is not in
`commit_guardian.json → ticket_frontmatter.required_fields` (which requires only
`title`, `status`, `components`, `created`, `depends_on`).
`check_v2_ac_store_alignment.py`, which validates inline AC references in ticket
bodies, is dormant.

**5. The documentation guarantee is agent-only.** BO-2200 shipped a real
mechanism — `documentation_gates` in `config/guardrail_gates.yaml` drives
`generate_ticket_from_ac.py` to inject `documentation-expert` + a
`requires_documentation_verification` contract, and the `documentation-verifier`
phase agent asserts each named doc has a real diff. **Both ends run inside the
build pipeline.** Commit an L1 AC with `documentation_triggers` by hand and no
hook or CI job will ever ask for the doc. `check_doc_coverage.py` and
`check_doc_links.py` (code ↔ doc back-links) are dormant *and* advisory-only.

**6. Most guardrails have no merge-vector backstop.** 50 pre-commit hooks; 6 CI
jobs. Anything not in that list of six is fully bypassed by `--no-verify`, by a
worktree that lacks the hook config, or by a merge commit. Notably with **no CI
equivalent**: the whole product-truth/flow validation, ticket ↔ AC status parity,
structural-change → components.json, contract-shrinking, presence-only
assertions. `ci.yml` itself documents the deliberate omission of a whole-store AC
gate on push to main (ACS-200h) because the store carries ~57 pre-existing
orphans.

**7. Silence does not mean pass.** Nearly every guardian hook is documented
fail-open: an unexpected exception exits 0 with a stderr note. Several read their
file set from the git index and validate *nothing* when the index is clean —
which is exactly why the `AC store valid` CI job has to `git reset --soft` to the
base ref before invoking them. A green hook run is not proof a check ran.

**8. AC `work_status` is not a reliable read of what is live.** BO-2200a/b/c/d all
sit at `todo` while every one of their children is `done`; `guardrail_gates.yaml`
is shipped and consumed while the BO-620 ACs describing it are `todo`. Verify
against the repo, not the store.

---

## What is planned

All of the following are authored, `readiness: approved`, and almost entirely
`work_status: todo`. Together they are close to a complete answer to the holes
above.

| Family | Closes | State |
|---|---|---|
| **GE-111** *Traceability stays honest* | Hole 1. Commit-time AC ↔ code drift detection with a file-path floor and a `#symbol` anchor tier, scoped to links whose source the commit staged; block by default, warn-only as explicit opt-in; two reconciliation routes (update the link / confirm the code still satisfies it) + how-to + sequence diagram | 0 of ~20 done |
| **GE-117** *Code declares what it serves* | Hole 2. Module docstring names a registered component; public symbol docstring cites a resolvable AC; each new decision-history entry carries an AC ref; guided autofix and a per-item, reasoned opt-out | 0 done |
| **GE-104** *Enforced page docs* | Hole 5 (frontend slice). Two-layer: a commit hook blocking a new page without its reference doc, plus a planning-time trigger flipping `documentation-expert` to needed | 0 done |
| **GE-120** *Green means checked* | Hole 7. A check that cannot inspect reports *degraded*, never a clean pass; every check declares its cannot-run disposition; one shared root/prereq resolver; an out-of-process parity harness proving every manifest hook reaches the same verdict from a worktree; correct authored-diff attribution on merges and reverts | 0 done |
| **TQ-100** *Suite only blocks for failures that matter* | Hole 3. Formalises the `pytest_ac_enforcement` behaviour already live: untagged tests enforced by default, tagged-and-not-done informational, done-AC tests un-downgradable, an expiring allowlist, and a three-stage enforcement rollout | plugin live, ACs todo |
| **BO-600** *Change-driven guardrails* | Routes the guardrail set from `change_target` × `risk_surface`, with inheritance for new agent types and targets | enums + `guardrail_gates.yaml` live; BO-610-4 (both fields mandatory in ticket frontmatter) and the BO-620 mappings todo |
| **GE-122** *Numbers mean one thing* | Id uniqueness across all four namespaces, enforced at three stages, with remediation routes | 1 done |
| **GE-113 / GE-116 / GE-123** | Artefact placement (misplaced tests), agent-config self-consistency, secrets-allowlist suppression narrowing | mostly todo |
| **ACD-600b**, **ACD-800**, **ACS-900** | Post-merge hook marking `source_ac` tickets done (`hooks/check_ac_done_on_merge.py` exists but is dormant); auto-discovery backfilling `implemented_by`; orphaned-code check when an AC is retired | todo |
| **TKT-500f-8 / -9** | Generated tickets carry `ac_traceability` and a `files_touched` unioned with `doc_links` | todo |
| **ACS-200h** | The missing whole-store AC gate on push to main | blocked on reconciling the orphan backlog |

---

## If you want the harness to lead without agents

The cheapest high-value moves, in order:

1. **Wire the dormant hooks.** `check_test_ac_tags`, `check_ac_coverage`,
   `check_v2_ac_store_alignment` and `check_ticket_test_requirements` are written
   and tested; they are simply absent from `hooks_manifest`. Ship them in `warn`
   first, then ratchet.
2. **Add `source_ac` to `ticket_frontmatter.required_fields`.** One config line
   turns Ticket → AC from optional into mandatory.
3. **Build GE-111's file-path floor.** Even without the symbol tier, "an
   `implemented_by` path that no longer exists is drift" is a small hook and it is
   the single biggest missing link.
4. **Give the un-backstopped hooks a CI job.** Product-truth validation and
   ticket ↔ AC parity are cheap to run and currently escape every merge.
5. **Move the documentation trigger out of the ticket generator.** A hook that
   reads `documentation_triggers` off the parent L1 and asserts a matching
   `docs/**` file was staged would make the doc guarantee survive a hand-driven
   commit.

## See also

- [docs/pre-commit-hooks.md](../pre-commit-hooks.md) — per-hook reference
- [docs/explanation/tdd-workflow.md](tdd-workflow.md) — the test-first layer
- [docs/reference/ac-schema.md](../reference/ac-schema.md) — AC field contract
- [docs/product-truth/README.md](../product-truth/README.md) — flow store
