---
title: "Known Issues: Commit Guardian"
description: "Open defects in commit-guardian hooks found while driving GE-122: a scope hook that cannot tell a ticket-as-subject from a ticket-as-driver, a parity hook silently skipping one of its checks, an unretired always-exit-0 fail-open contract, and a repair module with no supported entry point."
type: reference
status: active
created: 2026-08-19
last_updated: 2026-08-19
components:
  - commit_guardian
  - precommit_hooks
related_docs:
  - docs/pre-commit-hooks.md
  - docs/architecture/components/commit-guardian.md
  - docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md
---

# Known Issues: Commit Guardian

Open defects observed directly on 2026-08-19 while driving
`EPIC-GE122UniquenessPassAndRepair`.

## KI-CG-1 — `check-predone-scope` cannot distinguish a ticket's subject from its driver

**Severity: medium.** Blocks any lifecycle-repair commit.

The hook reads every modified ticket `.md` in the change set as a *governing*
ticket authorising the commit, then reports source changes as undeclared against
that ticket's `files_touched`. It has no notion of a ticket being the *subject*
of a change.

This misfires on any work that repairs tickets. GE-122e-2 deleted five duplicate
work items; the hook read those five long-finished June tickets as the commit's
authorisers and blocked.

**Second, compounding defect: it reconciles branch-wide, not commit-wide.** An
attempt to satisfy it by splitting the source changes into a separate commit
still failed, and the error named files that were not in the commit at all
(`_commit_disposition.py`, `_uniqueness_scanners.py`, `_work_items_scanner.py` —
all from earlier commits on the branch). No commit boundary can satisfy it.

**Detection.** The tell is a blocker naming files absent from `git diff --staged`.

**Workaround.** `SKIP=check-predone-scope`, with the justification written into
the commit message. Used once on `6715e4c3`.

**Suggested fix.** Two independent changes: (1) distinguish subject from driver,
probably by treating a ticket as governing only when the commit is authored under
it; (2) reconcile against the staged diff rather than the branch diff.

## KI-CG-2 — `check_ticket_signoff_parity.py` silently skips check #6

**Severity: medium.** A gate check has been inert.

The hook resolves the agent registry at
`<worktree_root>/leafcutter/config/agent_registry.json`. That path is wrong for
this layout — nothing exists there — so it emits a warning to stderr and skips
check #6 entirely:

```
[check-ticket-signoff-parity] WARNING: agent registry not found at
  <worktree>/leafcutter/config/agent_registry.json; skipping check #6
```

The hook then **exits 0**. The other checks run, so the hook looks healthy; one
of its checks has simply never fired in this layout.

**Detection.** Run the hook and read stderr, not just the exit code. Silence is
not the same as a pass.

**Suggested fix.** Resolve the registry the way other layout-aware scripts do
(derive the root from `git rev-parse`, and support both the source-repo and
deployed layouts). Consider whether an unresolvable registry should fail closed
rather than skip.

## KI-CG-3 — `check_ticket_state_integrity.py` retains an always-exit-0 contract

**Severity: medium.**

The script documents a `Returns: Always 0` fail-open contract. GE-122a-2 widened
work-item integrity checking but did **not** retire it. The contract is pinned by
existing tests, so a coder may not unilaterally weaken it — retiring it needs a
`test-writer` pass first to change the pinned expectations.

While this stands, the hook cannot block anything.

## KI-CG-4 — `repair_work_item_duplicates.py` has no CLI

**Severity: low.**

The module is importable only. The live repair run against the real `tickets/`
tree therefore went through a throwaway operator harness in `/tmp` rather than a
supported entry point. Nothing in the AC's `test_spec` required a CLI, and adding
untested surface for convenience was declined — but a repair that can only be
invoked from a test is awkward to re-run and hard to audit.

## KI-CG-5 — Staged paths with non-ASCII characters are silently unattributed

**Severity: low** in this repository, **medium** in a consumer project with
non-ASCII filenames.

`_get_staged_paths` in `_commit_disposition.py` uses plain
`git diff --cached --name-only`, with no `-z` and no `--no-quote-path`. Under
git's default `core.quotePath=true`, a staged path containing non-ASCII
characters comes back **quote-escaped** (e.g. `"tickets/caf\303\251.md"`). That
string does not resolve to a real path, so the attribution check silently fails
to match it.

The consequence is directional and bad: a collision the current commit **did**
cause is reported as *unattributed*, which by design does **not** block. The
commit proceeds.

Found during the first review of `GE-122a-1-i`. It is inherited from
`check_ac_schema.py::_get_staged_ac_paths`, which that AC's own `doc_links` name
as its precedent — so it is a pre-existing convention rather than something the
GE-122 work introduced.

**Why it is low here:** this repository's numbered artifacts are ASCII by
convention (`GE-122a-1.yaml`, `ADR-029-*.md`, `TICKET-*.md`). Nothing currently
in the collection can trigger it.

**Suggested fix.** Use `git diff --cached --name-only -z` and split on NUL, or
pass `--no-quote-path`. Fix both call sites together — leaving the precedent
unfixed means the next author copies it again.

## KI-CG-6 — FIXED — the uniqueness pass reported success over a collection it never found

**Fixed 2026-08-25.** The most serious defect found in the GE-122 work, because
it is this epic's own thesis failing in this epic's own implementation.

```
run_uniqueness_pass(Path('/does/not/exist'))
  overall passed = True
  all four namespaces: passed=True, inspected_count=0
```

Every namespace scanner fail-opened to `passed=True` when its root directory or
config file was missing or unreadable, and `run_uniqueness_pass`'s
`passed = all(...)` propagated that into a green overall verdict.

GE-122a-1's own coverage note requires per-namespace inspected counts precisely
*"so a passing result is distinguishable from a pass produced by inspecting
nothing."* The gate built to make a pass-over-nothing detectable **was** a
pass-over-nothing. Point it at a wrong path — a consumer install whose AC store
lives elsewhere, a hook invoked from an unexpected cwd, a renamed directory —
and it is silently, greenly inert.

**The contract now.** A namespace may report `passed=True` only when its root or
config was actually resolved, whether that yielded zero artifacts or many. The
three-way distinction uses the existing fields rather than a new one, so the six
downstream consumers need no change:

| verdict | meaning |
|---|---|
| `passed=True` | resolved and clean |
| `passed=False`, `findings == []` | could not resolve — misconfiguration |
| `passed=False`, `findings != []` | genuine collision |

**Scope boundary that must be preserved:** a *declared lifecycle folder* absent
from disk while the config itself is present and readable remains legitimately
fail-open. An empty-but-present namespace root still passes. Only an
unresolvable root or config fails closed.

**What this exposed downstream.** Fixing it flipped
`test_ge_122a_1.py::test_repaired_collection_passes_with_per_namespace_counts`
from green to red — its fixture never created a `tickets/` root or
`ticket_lifecycle.json` at all. That test had been asserting *"a repaired
collection passes"* over a collection that was never there, passing only because
the fail-open masked the gap. The fixture was completed, not the assertion
weakened.

That is the sharpest instance of this register's recurring shape: **a test
passing for the wrong reason, where the bug and the test's blind spot are the
same bug.**

## KI-CG-7 — FIXED — the fail-closed contract never reached the exit code

**Fixed 2026-08-25.** Found by the fourth adversarial review round, in the fix
KI-CG-6 describes. KI-CG-6 made an unresolvable namespace report
`passed=False`. It did not make anything *act* on that.

`compute_commit_disposition` derived its verdict solely from findings:

```python
blocking=any(f.attributed for f in commit_findings)
```

An unresolvable namespace reports `passed=False` with an **empty** findings list
— deliberately, since there is nothing to name; the root itself is the finding.
It therefore contributes no `CommitFinding` and could never set
`blocking=True`. `main()` consults `verdict.passed` only when git itself is
unavailable, so on every ordinary commit the gate printed its complaint and
exited **0**:

```
$ check_identifier_uniqueness.py          # docs/acceptance-criteria/ absent
[check_identifier_uniqueness] acceptance-criteria: FAILED (0 inspected)
exit code = 0
```

So for one full round, the headline fix of this epic was inert at the only layer
that decides anything. The unit tests were green throughout: the 770-line
`test_ge_122e_3_root_resolution.py` asserted on `run_uniqueness_pass` and never
on the exit code, while `test_ge_122a_1_i.py` exercised the disposition layer but
only ever with non-empty findings. **Neither file could construct the failing
shape, so the gap between them was invisible to both.**

`blocking` is now additionally true when any namespace is unresolvable, and an
additive `unresolvable_namespaces` field lets the operator message name which
one. The boundary is pinned: an unresolvable root blocks *regardless of what is
staged* (it is a misconfiguration of the gate, not a property of the diff),
whereas a genuine collision with no staged claimant stays non-blocking exactly
as GE-122a-1-i specified.

**The lesson worth keeping.** Every layer of this epic has now failed the same
way once: a signal is computed correctly and then not consumed. Producing the
right verdict is not the same as acting on it, and a test that stops at the
verdict cannot tell the two apart.

## KI-CG-8 — `scan_decisions` and `scan_diagrams` fail silently

**Severity: low**, but it makes every misconfiguration harder to diagnose than
it should be.

When a namespace root is missing, `_work_items_scanner.py` logs:

```
[check_identifier_uniqueness] WARNING: cannot read <path>/tickets/ticket_lifecycle.json
```

`scan_decisions` and `scan_diagrams` in `_uniqueness_scanners.py` return
`passed=False` for an absent root with **no log line at all**.

This has already cost real diagnostic time. Three failing tests were first read
as "the lifecycle config is missing" because that was the only namespace that
said anything; the fixtures were in fact missing **three** roots, and the two
silent ones were only found by printing the verdict directly. Since the
fail-closed contract now blocks the commit, an operator hitting this sees a
non-zero exit with one namespace named and two staying quiet.

**Suggested fix.** Give the silent scanners the same WARNING the work-items
scanner already emits. The `unresolvable_namespaces` field added for KI-CG-7
already carries the information; this is only about surfacing it at the point of
failure.

## KI-CG-9 — THE UNIQUENESS PASS IS REGISTERED NOWHERE AND HAS NEVER RUN

**Severity: critical. Open. This is the finding that reframes the whole epic.**

Found in review round six, by the first reviewer to test the gate *as deployed*
rather than by invoking it from the source tree.

```
grep "check_identifier_uniqueness" templates/scripts/commit_guardian/commit_guardian.json  -> 0
grep "check_identifier_uniqueness" .pre-commit-config.yaml                                 -> 0
grep -rl across every .json / .yaml / .yml / .js / .toml in the repo
    -> docs/acceptance-criteria/.../GE-122a-1.yaml   (the AC that specifies it)
    -> tickets/.../.pending/adr_handoff.json         (a pending handoff)
       nothing else
```

No pre-commit hook invokes it. No CI workflow invokes it. The one registered
hook with a similar name, `check-decision-number-uniqueness`, runs a **different
script** (`check_adr_collision.py`).

**Six review rounds and five fix commits hardened a `main()` that no runner
calls.** The commit immediately before this one is titled *"the fail-closed
contract was never wired to the exit code"* — and nothing reads that exit code.

The epic's own `Master_Plan.md` named this outcome in advance:

> The trap this epic is most likely to fall into: **a guard that is built,
> tested green, and registered nowhere.**

and its Success Criteria require *"one whole-collection uniqueness pass,
**registered in `commit_guardian.json`** and reachable through its production
entry point — not a second inert detector."* **That criterion is not met.** The
epic was commissioned because three whole-collection detectors were already
registered nowhere. It has produced a fourth.

**How six rounds missed it.** Every round verified behaviour by importing the
module or running the script directly. Not one asked what invokes it in
production. Each round's verification was accurate and none of them addressed
the question. The register's own recurring lesson — *a signal computed correctly
and then not consumed* — applied to the entire component, and the reviews
inherited the blind spot from the thing they were reviewing.

**Do not register it in the same change that ships it.** See **KI-BO-4** — doing
so today makes the package uninstallable. Required order: scaffold the missing
namespace roots, then register, then re-run the deployed-consumer test.

## KI-CG-10 — the unattributed backlog count is discarded in deployment

**Severity: medium. Open.**

GE-122a-1-i requires a visible count of reported-but-unattributed collisions,
on the stated grounds that *"a visible count is what makes the backlog shrink."*
Run directly, the gate emits it:

```
[check_identifier_uniqueness] 1 reported-but-unattributed contested number(s)
  with no claimant in the current change set (not blocking)
```

Under `pre-commit`, a **passing** hook's stdout is discarded, and the generated
config sets `verbose: true` on no hook. So on the non-blocking path — the only
path this message exists for — the operator never sees it.

Same shape as **KI-CG-7**, one layer further out: computed correctly, then not
consumed. Fix by setting `verbose: true` on this hook's registration when
**KI-CG-9** is addressed.

## KI-CG-11 — `main()` derives the root from `Path.cwd()`

**Severity: medium. Open.**

`check_identifier_uniqueness.py`'s `main()` uses `Path.cwd()`. The package's
canonical `find_project_root()` (git-toplevel first) sits unused in the same
directory as `_resolve_root.py`, which 27 sibling files already import.

Under `pre-commit` the cwd happens to be the repo root, so it works **by luck**.
From any nested directory it does not:

```
$ env --chdir=<consumer>/docs python3 .../check_identifier_uniqueness.py
BLOCKING: ... acceptance-criteria, decisions, diagrams, work-items      exit 1
```

All four namespaces unresolvable, so with the KI-CG-7 fail-closed fix in place
it hard-blocks. Any agent or manual invocation from a subdirectory is affected.
Adopt the shared resolver.

## KI-CG-12 — `check_adr_collision.py` blocks any repo without `origin/main`

**Severity: high. Open, and live on `main` today — not introduced by this epic.**

This hook IS registered and required. It reads the decision-number sequence from
`origin/main` and fails closed when that ref does not exist:

```
[check_adr_collision] BLOCKED -- could not read the decision-number sequence:
  could not read the decision sequence on 'origin/main' (git ls-tree exited 128):
  fatal: Not a valid object name origin/main
[check_adr_collision] Uniqueness was not established, so this commit cannot proceed.
```

A `git init` repository has no `origin/main`. Every ADR-touching commit in any
repo that is not a clone with a `main` branch is blocked. Found while building a
fresh consumer install to test **KI-CG-9**; worth its own ticket independent of
this epic.

## KI-CG-13 — the diagrams root is hardcoded while its sibling roots are configurable

**Severity: medium. Open.**

`config/paths.json` declares the other architecture roots:

```json
"architecture":            "docs/architecture/",
"architecture_adrs":       "docs/architecture/adrs/",
"architecture_components": "docs/architecture/components/",
```

There is **no `architecture_diagrams` key**. `check_identifier_uniqueness.py`
hardcodes `docs/architecture/diagrams/` instead. So of the four namespaces the
gate polices, one has a root that a consumer cannot relocate, while its two
immediate siblings can.

This matters more once the gate is registered (**KI-CG-9**): a consumer that
keeps diagrams anywhere else gets a permanently unresolvable namespace, which
under the **KI-CG-7** fail-closed contract blocks every commit with no
configuration escape.

**Suggested fix.** Add `architecture_diagrams` to `paths.json` and read the root
from it, matching how `architecture_adrs` is already consumed. Fold this into the
scaffolding work (**KI-BO-4**) — the same change decides where the directory
lives and how the gate finds it, and splitting them invites the two answers to
diverge.

**Context for whoever picks this up.** `docs/architecture/diagrams/` currently
holds 24 files: 13 match the `c{level}-{seq}` pattern the gate's numbering
namespace polices, and 11 do not. Those 11 are a **binding, permanent exemption**
recorded in `GE-122e.yaml` / `GE-122b.yaml` by a PO gate decision of 2026-08-17 —
do not renumber them. See `docs/reference/architecture-docs-layout.md`.

## Fixed, recorded for context

Two defects in this area were found and fixed during the same drive; they are
listed here only so the history is legible, and are **not** open:

- **`check_adr_collision.py` was never registered.** ADR-029 claimed it had been
  "shipped and wired into `.pre-commit-config.yaml` since the package's early
  history". It appeared in none of the 49 registered hooks. Now registered as
  `check-decision-number-uniqueness`; ADR-029 amended.
- **The uniqueness pass's id fast path diverged from `yaml.safe_load`.** Plain
  scalars like `no`, `007` and `0x1F` resolved to their raw source text rather
  than YAML's coerced value, so two records YAML considers identical looked like
  two different ids and a real collision was silently missed. Fixed by asking
  PyYAML's own resolver whether a plain scalar would be coerced.
- **The same fast path answered wrongly on two more shapes** (found in round 4).
  A multi-document stream (`id: GE-1\n---\nid: GE-2`) returned `GE-2` where
  `safe_load` raises and the contract says *no claim*; a folded plain scalar
  (`id: foo\n  bar`) returned `foo` where `safe_load` yields `foo bar`. Because
  `_read_yaml_id` falls back to the full parse only on `None`, a *wrong* answer
  was never corrected. Fixed by making the fast path **decline** on any shape it
  cannot decide — declining is always safe, answering wrongly is not. The
  performance win is intact: 3091 of 3092 real files still take the fast path,
  0.20s.
- **The fast path answered wrongly on YAML's `...` document-end token** (found
  in round 6). Round 5 added `_is_document_separator_line` so the fast path would
  decline on a multi-document stream, and taught it only `---`. `...` is the
  grammatical sibling in the same YAML production, so `"id: GE-1\n...\nid: GE-500"`
  — a file `safe_load` refuses to parse at all — returned `GE-500` and
  manufactured a phantom collision against a legitimate record, one the operator
  could not resolve because nothing was wrong with the file they would inspect.
  The round-5 fix's own docstring claimed it declined "on ANY shape it cannot
  decide"; the equivalence table had a `---` case and zero mention of `...`, so
  the "0 mismatches over 3092 files" verification was true only inside a blind
  spot it shared with the fix. Fixed via a shared `_is_document_boundary_token`
  covering both tokens. Note the boundary: a **lone trailing** `...` is legal
  YAML terminating one document and must keep resolving — determined empirically
  rather than assumed.
- **Two lifecycle folders naming the same directory produced a phantom
  self-collision** (found in round 4). A trailing slash, a `./` prefix or a `..`
  round-trip each passed the containment check independently, so one real ticket
  file was walked twice and reported as colliding with itself, with
  `inspected_count` doubled. Fixed by de-duplicating on resolved path identity,
  preserving declaration order. Note the tests had the *opposite* case covered
  (two folders sharing a basename but genuinely distinct) and not this one.
