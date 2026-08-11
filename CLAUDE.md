# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Shell Convention — MANDATORY

Every Bash tool call MUST be a single, simple command. Never chain with `&&`, `;`, `||`, pipes to other commands, or multi-line scripts. Never use `cd` — use absolute paths or `git -C` instead.

**Wrong** (triggers permission prompt, breaks auto-allow):
```
cd /some/project && python script.py --flag "value"
```

**Right** (single command, auto-allowed):
```
python /some/project/script.py --flag "value"
```

Rules:
1. Use absolute paths for the script AND its arguments.
2. Use `git -C <path>` instead of `cd <path> && git`.
3. Redirect stderr to `/tmp/` (not a relative path).
4. If a command needs environment variables, use `ENV=val command` syntax — that is a single command, not a chain.

## Commit Delegation — MANDATORY

`git commit` must never be called directly. Dispatch the `commit` agent via
the Agent tool instead.

Calling `git commit` directly bypasses the confirmation gate, the pre-commit
hook failure → autofix path, the sign-off recording, and the background-commit
safety checks that are built into the `commit` agent template. The
`enforce_commit_delegation` PreToolUse hook will block any direct `git commit`
call that does not originate from within the `commit` agent.

**Wrong:**
```bash
git commit -m "some message"
```

**Right:**
```
# Use the Agent tool to dispatch the commit agent:
# Agent tool → commit agent → dispatches COMMIT_AGENT_MODE=1 git commit internally
```

### Commit messages must match the diff — MANDATORY

Every factual claim in a commit message ("Added X", "Fixed Y", "Now logs a WARNING
in Z") must be verifiable in `git diff --staged`. Do NOT describe an intended change
that is not actually in the staged hunks. A message that claims work the diff does not
contain is the same phantom-done failure mode this repo exists to prevent, one level up:
it makes a reviewer (and future you) believe a change landed when it did not.

**Why this matters:** During EPIC-PhantomDoneFilesTouched (2026-07-07) a remediation
commit message stated a WARNING log had been added to a helper, but the diff contained
no such change — the log was only added in a later round. The claim survived until a
code-review agent grepped the actual file. Before committing, re-read your message against
the staged diff and delete any claim you cannot point to a hunk for.
(Source: EPIC-PhantomDoneFilesTouched retrospective KI-4, 2026-07-07.)

## Repository Structure

This repo IS the leafcutter-ai package. Origin: `git@github.com-urlmonitor:urlmonitor/leafcutter-ai.git`

When installed into a consumer project, this repo is cloned into a subdirectory (e.g. `my-project/leafcutter-ai/`). The consumer then runs `python leafcutter-ai/scripts/build.py --target-dir .` to deploy agents, skills, and hooks into their project root.

For local development of the package itself, the workspace looks like:

```
leafcutter/              <- workspace directory (not tracked by this repo)
  leafcutter-ai/         <- THIS repo (git root)
  .claude/               <- build outputs deployed by build.py
  scripts/               <- build outputs deployed by build.py
```

To rebuild the development environment: `./build-self.sh` (or equivalently, `python leafcutter-ai/scripts/build.py --target-dir .` from the parent directory). See [ADR-001](docs/architecture/adrs/ADR-001-self-hosting-boundary.md) for the self-hosting boundary convention.

SSH auth uses host alias `github.com-urlmonitor` (key: `~/.ssh/id_urlmonitor`).

<!-- glossary-section: leafcutter -->
## Glossary

Project jargon and terminology is tracked at [docs/glossary.md](docs/glossary.md).

Consult it for project-specific terms when reading code or docs.

- **To populate from scratch**: run `/glossary-bootstrap` (once after initial install
  or after a major codebase merge).
- **Ongoing additions**: the `check-glossary-coverage` pre-commit hook detects novel
  terms in staged files and dispatches the `glossary-triage` agent automatically.
- **Do NOT hand-edit to add entries** — always use the triage flow so the blacklist
  stays consistent. Manual edits are only for correcting existing entries.

## Knowledge & Memory Capture — MANDATORY

When the user asks you to "remember this", "capture this", "write this down",
"save this for later", or otherwise store a learning or memory, do NOT write
directly to a memory file, the glossary, a doc, or a config value. First invoke
the `route-knowledge` skill, which classifies the request and returns a
structured `{ target_surface, path, rationale }` routing decision. Persist the
knowledge to the surface it names.

This prevents defaulting every learning to a memory file: `route-knowledge`
distinguishes memory (session-spanning working context) from the glossary
(project terminology), documentation surfaces (how-tos, references, ADRs,
explanations), and config values. It is also the required pre-flight gate before
dispatching `documentation-expert`.

## New Work Goes Through ACs — MANDATORY

**Never hand-write a ticket as the primary artifact for new work.** Author
**acceptance criteria first**, then generate the ticket from them. This is the
canonical path per ADR-012 (`/create-ticket` is retired):

1. `/plan-feature` — ac-triage → PO v3 → BA v3 → IT PO v3 author the ACs into the
   store (`docs/acceptance-criteria/{component}/`), with user gates between stages.
2. `/build-ac` — generates a fully-wired ticket **from** an approved AC.

**Why:** ACs are the machine-readable, **test-coverable** unit of work. The AC YAML
in the store is the source of truth that tests, `test-writer`, `ac-validator`, and CI
tooling read; a ticket's body ACs are for human readability only (see
`ticket-authoring` → "AC Referencing Convention"). Skipping straight to a ticket
leaves nothing for tests to assert against, so the work cannot be verified as truly
done — the exact phantom-done failure mode this repo exists to prevent.

**The only** direct writes to `tickets/**/*.md` that bypass this are pure **lifecycle
moves** — flipping `status:` and relocating a file between status folders
(`00_inbox` → `01_todo` → `99_done`). Everything that defines new behavior starts
with `/plan-feature`.

<!-- roadmap-phase:start — AUTO-GENERATED from docs/roadmap.json; edits between these markers are overwritten on next render -->

| Roadmap | [docs/roadmap.json](docs/roadmap.json) | Current phase, exit criteria, and tickets advancing the outcome. Use `python portable-dev-workflow/scripts/roadmap_query.py --current-outcome` to list actionable tickets. |

Current phase: `phase_1`
Current outcome: Stable MVP that installs into any project and helps the user build good software — portable, self-onboarding, and reliable enough to use across multiple repos.

<!-- roadmap-phase:end -->

## Architecture Reference

| Document | Path | What it covers |
|----------|------|----------------|
| Agent Knowledge Plane | [docs/architecture/agent_knowledge_plane.md](docs/architecture/agent_knowledge_plane.md) | All 11 channels through which agents receive context at invocation time (pre-execution knowledge injection). |
| Agent Knowledge System | [docs/architecture/agent_knowledge_system.md](docs/architecture/agent_knowledge_system.md) | How agents classify, route, and persist learnings after task completion (post-execution knowledge capture). |
| Agent Delivery Workflows | [docs/architecture/agent_delivery_workflows.md](docs/architecture/agent_delivery_workflows.md) | Supervisor dispatch topology, ticket batching, and blocker adjudication flows. |
| Knowledge Query | [templates/skills/knowledge-query/SKILL.md](templates/skills/knowledge-query/SKILL.md) | Cross-surface knowledge graph query skill. Invokes `scripts/knowledge_query.py` to search nodes across all paths.json surfaces (agents, tickets, docs, skills, ADRs, hooks) with keyword filter, surface filter, JSON export, and edge list output. |
| Knowledge Graph Visualization | [scripts/visualise_knowledge_graph.py](scripts/visualise_knowledge_graph.py) | Generates a self-contained D3.js force-directed HTML graph from all knowledge surfaces. Run `python scripts/visualise_knowledge_graph.py --no-open` to write to `/tmp/leafcutter_knowledge_graph.html`; omit `--no-open` to open in the default browser. |

## Error Handling Policy

All Python code in this repository must follow these four rules. They are
enforced mechanically at commit time by Ruff (rules E722, BLE001, TRY); the
rules below explain the *why* so violations are understandable before you hit
the linter.

**Rule 1 — External I/O must be wrapped.**
All calls to `requests.*`, `open()`, `cursor.execute()`, subprocess calls,
and any other operation that crosses a process or system boundary must be
wrapped in `try/except <SpecificExceptionType>`. "External I/O" means any
call that can raise an OS, network, or database error.

```python
# Good
try:
    response = requests.get(url, timeout=10)
except requests.RequestException as exc:
    logger.warning("Request failed: %s", exc)
    raise

# Bad — no try/except around external call
response = requests.get(url)
```

**Rule 2 — Never bare except (Ruff E722).**
`except:` with no exception type is forbidden. Always name at least one
specific exception type. Ruff rule E722 blocks the commit on bare excepts.

```python
# Good
except ValueError as exc:

# Bad — bare except
except:
```

**Rule 3 — Never silently swallow (Ruff BLE001, TRY).**
Every `except` block must either (a) log the error at WARNING or higher via
the project logger, or (b) re-raise the exception (as-is or wrapped in a
typed exception). An empty block or one that only sets a flag without logging
is a violation. Ruff rules BLE001 and the TRY family catch common forms.

```python
# Good — log and re-raise
except OSError as exc:
    logger.warning("File operation failed: %s", exc)
    raise

# Good — wrap in typed exception
except OSError as exc:
    raise ConfigLoadError("Cannot read config") from exc

# Bad — silently swallowed
except OSError:
    pass
```

**Rule 4 — No try/except on pure internal functions.**
Functions that do not perform I/O, do not call external services, and do not
mutate shared state must NOT be wrapped in try/except by default. Adding
try/except to pure functions obscures bugs. If a pure function raises
unexpectedly, let it propagate — the caller at the I/O boundary is
responsible.

```python
# Good — pure function, no try/except
def calculate_offset(start: int, end: int) -> int:
    return end - start

# Bad — unnecessary try/except on pure function
def calculate_offset(start: int, end: int) -> int:
    try:
        return end - start
    except Exception:
        return 0
```

For deeper explanation of the Ruff rules, see:
- [E722](https://docs.astral.sh/ruff/rules/bare-except/) — bare-except
- [BLE001](https://docs.astral.sh/ruff/rules/blind-exception/) — blind exception catch
- [TRY](https://docs.astral.sh/ruff/rules/#tryceratops-try) — tryceratops family

## Implementation Conventions

### Function Signature Extension — Call-Site Audit Required

When a ticket extends the signature of an existing function (adds required or optional keyword arguments), the implementing agent must:

1. **Grep for ALL existing call sites** in the codebase before declaring done.
2. **Verify each call site** passes the new arguments (or explicitly documents why an old-argument call is an intentional backward-compat path).
3. **Include call-site updates in the same commit** as the signature change.

A function whose signature is extended but whose callers still use the old signature silently exercises the legacy code path. This is not catchable by tests that test the function directly — the tests pass against the function in isolation while every real call path uses the old signature.

(Source: EPIC-ComputedQualityGates FP-1, 2026-07-07.)

### In-Place Workflow Specs — Protected-Branch AC Required

Any workflow spec whose behaviour is "operates in the current worktree" (or otherwise
commits/pushes in place without creating an isolated branch) MUST include an explicit
acceptance criterion covering the protected-branch (`main`/`master`) case — either a
confirmation gate or a hard refusal. A spec that omits it ships a workflow that will
happily commit straight to `main`.

**Why this matters:** `/quick-fix` shipped without a main-branch guard; the missing
`BP-600f` confirmation gate had to be added in a post-merge follow-up after the gap was
found in production.
(Source: EPIC-QuickFixWorkflow retrospective KI-3, 2026-07-10.)

### Gate / Workflow ACs — Verify Behaviorally, Not by Grep

An acceptance criterion about a workflow, runner, hook, or gate must be covered by
a test that **executes the behavior** (or, for a workflow the unit layer cannot run,
asserts the results are actually **consumed** in control flow) — never by a test that
only greps the source for a string's presence or ordering. A grep-only test passes on
dead code, so it cannot distinguish "the gate is wired and runs" from "the gate string
is defined and ignored." Pair every such AC with an independent adversarial review
(code-review + a logic-check that runs the code) before marking it done.

**Why this matters:** The fast-lane feature — built specifically to defeat phantom-done —
itself shipped a phantom-done runner: `fast-lane-build.js` passed its grep-only structural
tests while **never executing** its red/green gates, and `fast_lane.py` had no CLI so the
runner's `select_batch` call was a silent no-op. Both were invisible to the structural
tests and were caught only by an independent code-review agent + a logic-check agent that
executed the code; the fix required behavioral (CLI) and semantic-consumption (guarded
control-flow) tests.
(Source: fast-lane build + review, 2026-07-22.)

### New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest

When a commit-guardian hook or a CI gate imports a module, that module MUST be added to
the build deploy list (`build_ac_store` `deploy_map` in `scripts/build_phases.py`, or the
equivalent phase for its directory). The hook runs from the **deployed** layout, not the
source tree, so a dependency that is not deployed raises `ModuleNotFoundError` at hook
runtime. Once the gate is a **required** status check, that crash blocks **every** merge.
Verify by running the deployed hook (or `build.py` then the hook) — not just the unit tests,
which import from the source tree and mask the gap.

**Why this matters:** `done_proof.py` (backing the `check_done_proof` hook and the required
CI done-proof gate) was created in `scripts/ac_store/` but omitted from `build_ac_store`'s
hardcoded `deploy_map`, so the deployed hook crashed with `ModuleNotFoundError: done_proof`
— which would have blocked all merges once the gate became required. Caught live by the
hook firing on its own commit.
(Source: fast-lane build + review, 2026-07-22.)

### Skip-Branch Side-Effects — Conditionalize, Don't Add (+ tests must see all quote styles)

When adding a per-step side-effect call (e.g. `outcome()`, an append, a status push) inside
an already-satisfied **skip branch** of an `if/else`, you MUST also conditionalize the
pre-existing **unconditional** call that sits after the `if/else` — move it into the
`else`/execute branch, or guard it — so the step is recorded **exactly once per path**.
Adding a skip-branch call while leaving the unconditional one produces a **duplicate** entry
on the skip path (and, symmetrically, moving without leaving one on every path produces a
gap). One recorded outcome per step per non-halt path; zero only on a full-workflow halt.

Static/structural tests that assert "the call is present" MUST match **all** JS quote styles
for the call's arguments — single-quote, double-quote, AND backtick template literals. A
regex that matches only `outcome\s*\(\s*['\"]` is **blind** to a template-literal call and
will pass on the buggy double-recording code. Pair any such structural test with a review
that reasons about runtime paths — static presence ≠ correct runtime cardinality.

**Why this matters:** `BO-1000b-1-i` added skip-branch `outcome(\`Step X…\`, 'skipped: …')`
calls (template literals) but left the unconditional `outcome('Step X…', …)` calls (string
literals) after each `if/else`; every skipped step double-recorded in `stepOutcomes[]`. The
count-guard test's regex only matched quoted-string first args, so it was blind to the
template-literal calls and stayed green. Caught only by an independent code-review + a
logic-check that enumerated runtime paths.
(Source: EPIC-InFlightVisibility retrospective, 2026-07-23.)

### TDD Order — test-writer Must Precede python-coder

The supervisor must dispatch `test-writer` BEFORE any coder phase. If `test-writer` runs and
finds the target suite already **green** (tests satisfied before the implementation phase),
that is a TDD-order violation, not a pass — document it in the ticket and do NOT mark the
ticket TDD-compliant. A red baseline captured before the coder runs is the evidence that the
tests actually constrain the implementation.
(Source: EPIC-InFlightVisibility retrospective, 2026-07-23.)

### Agent templates — `requires_verification: true` is mandatory when Edit or Write is in tools

Any agent template (`templates/agents/*.md`) that lists `Edit` or `Write` in its `tools:`
frontmatter field MUST also declare `requires_verification: true`. Omitting it trips
`registry_validator.py` rule A, which fails `build.py`'s `install_shims` step — and because
that build runs before pytest in CI, the missing flag blocks the required `Test suite
(pytest)` gate *before any test executes*, so it surfaces as a build failure rather than a
template-authoring error. The rule is enforced mechanically (`registry_validator` +
`unit_tests/commit_guardian/test_agent_verification_consistency.py`); it is documented here
so the failure is recognised fast.

Verify after authoring any new agent template:
```bash
grep -n "requires_verification\|Edit\|Write" templates/agents/<new-agent>.md
```
(Source: EPIC-DocumentationCoverageGuarantee FP-2, 2026-08-10.)

### guardrail_gates.yaml — exclude new top-level sections from the vocab-parity test

`unit_tests/commit_guardian/test_check_ac_schema.py` asserts that the non-policy top-level
keys of `config/guardrail_gates.yaml` exactly equal the `change_target` enum. When a branch
adds a new **top-level policy section** that is NOT a `change_target` vocab entry (e.g.
`documentation_gates`, `surgical_removal_guard`), add its name to the
`_NON_CHANGE_TARGET_SECTIONS` exclusion set in that test (alongside `flow_change_gates`) in
the same commit. Skipping this produces a failure that is invisible on the branch and only
surfaces once `origin/main`'s stricter parity test merges in.
(Source: EPIC-DocumentationCoverageGuarantee FP-3, 2026-08-10.)

## Pre-Drive Checklist

Run through these checks before invoking `/build-feature` or starting any epic drive.
Skipping them risks silent failures that are hard to diagnose after the fact.

### EMU account: open epic PR before drive (if applicable)

**What to check:** If you are operating under an Enterprise Managed User (EMU)
GitHub account, `gh pr create` is blocked at the CLI level. Before dispatching
any tickets:

```bash
# Switch to the non-EMU account
gh auth switch --user urlmonitor

# Push the epic branch to origin first
git push -u origin EPIC-<name>

# Then open the PR manually at:
# https://github.com/<org>/<repo>/compare/main...EPIC-<name>
```

Once the PR exists, the `pull-request` phase on each ticket should detect it via
`gh pr list --head EPIC-<name>` and push to the existing branch without re-opening.

**REST API fallback (when `gh pr create` is EMU-blocked):** the GraphQL
`createPullRequest` mutation that `gh pr create` uses can be blocked for EMU accounts,
but the REST endpoint is not. When `gh pr create` fails with the EMU error, create the
PR via the REST API instead:

```bash
gh api -X POST repos/<org>/<repo>/pulls \
  -f title="feat(...): <title>" \
  -f head="EPIC-<name>" \
  -f base="main" \
  -f body="<body>"
```

(Confirmed working in EPIC-AcPatternEnforcementIsMechanically PR #100/#102, 2026-06-18 —
`gh pr create` itself also succeeded under the `urlmonitor` account in the same session,
so try the CLI first and fall back to `gh api` only on the EMU error.)

**If you skip this:** The pull-request phase on the first ticket that tries `gh pr
create` under the EMU account will fail with "Unauthorized: As an Enterprise Managed
User, you cannot access this content (createPullRequest)".

### Feedback sink reachable

**What to check:** Verify that `debugging/logs/agent_telemetry.jsonl` (or the configured
remote endpoint, if any) is writable before the drive begins.

```bash
# Quick writability probe — should exit 0 and append one line
echo '{"probe":"pre-drive-check"}' >> debugging/logs/agent_telemetry.jsonl
```

If the command exits non-zero, the sink is unreachable — fix before invoking `/build-feature`.

**If the check fails:** Do not start the drive. The most common causes are:
- The `debugging/logs/` directory does not exist yet (`mkdir -p debugging/logs/`).
- A remote endpoint (future) is down — wait for it to recover or disable remote logging.
- A permissions issue on WSL2 NTFS mounts — remount or use a native Linux path.

**Why this matters:** During a past epic drive, the sink was unreachable for the entire
run. 23 `submit-failed` events occurred without detection — the drive completed but zero
telemetry was captured, making the retrospective impossible.
(Root cause ticket: TICKET-20260527-FeedbackSinkPreDriveCheck)

**Also verify `feedback_categories.yaml` is accessible.** The `submit_feedback.py` script requires this file in the worktree's `.leafcutter/` directory. When absent, all agent feedback calls fail silently with `(submit-failed)`, making the retrospective's quantitative category breakdown unavailable.

Check:
```
ls <worktree-root>/.leafcutter/feedback_categories.yaml
```
If the command fails (`No such file or directory`), the file is missing.

Fix: symlink or copy from the main tree's `.leafcutter/` alongside the `.pre-commit-config.yaml` fix in the section below.
(Source: EPIC-ComputedQualityGates FP-5, 2026-07-07.)

### Worktree pre-commit config (MANDATORY for worktree-based drives)

Worktrees do not inherit `.pre-commit-config.yaml` from the main working tree.
It is a `.leafcutter` symlink created by `install_shims` in the project root only —
a fresh worktree created from `origin/main` has neither the symlink nor a populated
`.leafcutter/`. If the worktree root lacks it, ALL package hooks are silently skipped
for the entire drive (`git commit` runs with `PRE_COMMIT_ALLOW_NO_CONFIG=1`).

**Check:**
```bash
ls <worktree-root>/.pre-commit-config.yaml 2>/dev/null || ls <worktree-root>/.leafcutter 2>/dev/null
```

**Fix (if absent):**
```bash
# Option A — symlink (preferred, requires native Linux FS):
ln -s <main-tree-root>/.leafcutter <worktree-root>/.leafcutter

# Option B — copy (for NTFS/WSL2 where symlinks are restricted):
cp <main-tree-root>/.pre-commit-config.yaml <worktree-root>/.pre-commit-config.yaml
```

**Why this matters:** During EPIC-AcPipelineDeployGaps (2026-06-17), all nine package
hooks were silently skipped for the entire drive. A post-drive diagnostic found 14
would-have-blocked findings (7 `check-feedback-id` + 7 `check-description-field`) that
required a dedicated fix commit after merge. If you cannot establish the config, run the
package hooks manually against the branch diff before merge.
(Permanent fix tracked in TICKET-20260617-Worktree_Precommit_Bootstrap.md)

**Latent hazard — `.security-allowlist` resolves via the symlink target, not the worktree
root.** The `check-secrets` hook computes its project root from `__file__` of the *resolved*
`.leafcutter` symlink target (under the workspace parent, e.g.
`/home/henzeh/projects/leafcutter/.leafcutter/`), so it reads the allowlist from the
**workspace-root** `.security-allowlist`, not the worktree's own copy. When you add a
suppression for a worktree-local false positive, add it to the workspace-root
`.security-allowlist` (or duplicate it to both) — a suppression placed only in the
worktree's `.security-allowlist` is silently ignored when the hook runs via the symlink path.
(Observed in EPIC-AcPatternEnforcementIsMechanically, 2026-06-18.)

### Security Allowlist — Use Glob Patterns for Test Files

When `check-secrets` flags false-positive `ENTROPY_HIGH` patterns in test files (e.g., keyword-argument strings such as `guardrail_config_path=_GUARDRAIL_CONFIG` that look like secret patterns), do **NOT** add per-line suppressions. Per-line entries (`ENTROPY_HIGH:<path>:<lineno>`) break as the test file grows — new lines shift existing line numbers, invalidating suppressions silently.

Instead, use a single glob entry:

```
ENTROPY_HIGH:<path>:*
```

This is supported by `scan_secrets.py _is_suppressed` (checks `lineno == "*"`). Add the glob to **BOTH** the worktree-root and workspace-root `.security-allowlist` per the dual-update rule (the `check-secrets` hook resolves the allowlist from the workspace-root symlink target, not the worktree's own copy — a suppression placed only in the worktree's `.security-allowlist` is silently ignored).

(Source: EPIC-ComputedQualityGates ticket 10 AC-5, 2026-07-07.)

### Land the scaffold commit on origin/main before creating the epic worktree

After running `/create-epic`, confirm the scaffold commit (Master_Plan.md + sub-ticket
stubs) is reachable from `origin/main` before calling `worktree-agent` to create the epic
worktree.

```bash
# The scaffold files must be reachable from origin/main (empty output = nothing missing):
git -C <repo> log --oneline origin/main..main
```

**`main` is PR-only (ruff branch-protection gate).** A direct `git push origin main` is
rejected with `GH013: ... Required status check "Lint (ruff)" is expected`. The scaffold
must go through its own PR:

```bash
# 1. Push the scaffold commit to a short-lived branch:
git -C <repo> push origin HEAD:scaffold/EPIC-<name>

# 2. Open a PR targeting main and merge it once the ruff check is green
#    (scaffold is tickets-only, so ruff passes trivially):
gh pr create --repo <org>/<repo> --base main --head scaffold/EPIC-<name> \
  --title "chore: scaffold EPIC-<name>" --body "..."
gh pr merge <N> --squash --delete-branch

# 3. Verify the scaffold is on origin/main before creating the epic worktree:
git -C <repo> fetch origin
git -C <repo> ls-tree -r origin/main --name-only tickets/00_inbox/epics/EPIC-<name>/
```

**If you skip this:** the epic worktree (created from `origin/main`) diverges at a stale
point — the scaffold files are unreachable inside it and ticket agents cannot read them
until the scaffold commit is cherry-picked onto the epic branch. Worse, when the scaffold
later reaches `origin/main` independently, the epic PR hits an add/add merge conflict on
those files at finalize (resolve in favor of the branch — the `status: done` versions win).
(Source: EPIC-AcPipelineDeployGaps retrospective, 2026-06-17, Findings #1 + #5;
scaffold-via-PR confirmed in EPIC-AcPatternEnforcementIsMechanically, 2026-06-18.)

### Commit agent in batch-drive mode

When running a sequential single-ticket batch drive (not using epic-supervisor),
the commit agent will refuse relayed approval from any intermediary. The approved
workaround for a human-authorized batch drive is to dispatch the commit agent
with `COMMIT_AGENT_MODE=1`. This bypasses the interactive gate only — the pre-commit
hook path, sign-off recording, and commit message validation remain active.
Do NOT use `COMMIT_AGENT_MODE=1` outside of a human-supervised batch drive.

(Source: EPIC-Oneagenthandlesboththelookandthecodefor retrospective, 2026-06-22,
Friction point #3.)

### Full test suite + ruff at epic-finalize (before merge)

**What to check:** Per-ticket sign-offs run only that ticket's own tests (often via
`unittest discover` on a subdir), so cross-cutting breakage and lint violations slip
through — especially when the worktree pre-commit hooks are not established. Before
merging any epic PR, run the FULL suite and ruff from the worktree root:

```bash
python -m pytest <worktree-root>/unit_tests/ -q
ruff check <worktree-root>/scripts <worktree-root>/tests <worktree-root>/unit_tests
```

Fix everything they surface on the branch before merge. Treat the pre-existing
non-required pytest failures (the registry self-description build-guard) as the known
baseline — but any NEW failure or any ruff violation is a merge blocker (ruff is a
required CI gate).

**Why this matters:** During EPIC-WorktreeQualityGateGuard (2026-07-06), two defects
passed per-ticket sign-off but were caught only by the full run: (1) idempotency tests
that read every deployed file as UTF-8 crashed on `__pycache__/*.pyc` under `pytest`
though they passed under `unittest discover`; (2) `ruff F401/F841` unused-import/variable
violations in new test files that the (unestablished) worktree ruff hook never ran. Both
forced extra fix commits at finalize.
(Source: EPIC-WorktreeQualityGateGuard retrospective KI-3, 2026-07-06.)

### Post-origin/main-merge diff audit — catch silently-dropped logic

After merging `origin/main` into a long-diverged feature/epic branch (especially when both
sides heavily edited the same file), git's 3-way auto-merge can produce a **textually clean
but semantically broken** result — silently dropping hunks one side added. Tests can stay
green because the dropped logic had no failing test. Before approving the merge:

```bash
git diff origin/main -- <heavily-diverged-file>   # should be ADDITIVE only (your feature's changes)
```

Every deletion line in that diff must be one you can explain. Any of main's logic that is
altered or removed (not just reformatted) is a HIGH-severity regression — restore it (take
main's version of that region and re-apply your change on top), then re-run the suite.

**Why this matters:** merging `origin/main` into EPIC-InFlightVisibility auto-merged
`finalize-feature.js` with no conflict but silently dropped main's hardened deploy-parity
guards (H-1: `if (!testPassed && postMergeFailures.length > 0)`; H-2: the `still_failing`
contradiction filter) — which could let a malformed test run merge to main. All 353 tests
stayed green; caught only by a fresh `git diff origin/main` review that showed non-additive
deletions.
(Source: EPIC-InFlightVisibility retrospective, 2026-07-23.)

### Real-artifact behavioral spot-check before declaring done

**What to check:** Before an epic is called done (and ideally before the `pr-reviewer`
phase signs off), exercise the changed component against the ACTUAL on-disk artifact it
processes — not a hand-authored fixture — in a fresh process, and assert the observable
behavior. For a parser/validator/matcher, feed it the real ticket / config / YAML exactly
as the tool that writes it produces (e.g. `yaml.safe_dump`, PyYAML column-0 block lists),
never an indented literal you typed.

**Why this matters:** During EPIC-PhantomDoneFilesTouched (2026-07-07), all 7 tickets
passed green phase sign-offs while the core hook was a **complete no-op on every real
ticket**: real `files_touched` lists serialize with dashes at column 0, but the parser
regex required indented dashes. The synthetic unit fixtures reproduced the indented bias,
so the tests passed on a feature that did nothing. Even the first behavioral spot-check
during remediation reused indented fixtures and missed it — only running the parser
against a real on-disk ticket file caught the defect. Green sign-offs prove the code runs;
they do not prove it works on the real data format.
(Source: EPIC-PhantomDoneFilesTouched retrospective KI-1, 2026-07-07.
See also user-memory feedback_spotcheck_real_data_format.)

### Doc-spec-only epic — confirm an implementation ticket exists

Before pushing any source-file commits for an epic, check whether **every** ticket in
the epic is documentation-spec-only (llm-expert-only, empty `test_requirements`,
test-writer auto-skipped). If so, confirm at least one **implementation** ticket exists —
with `files_touched` pointing at real source, an assigned coder agent, and a non-empty
test plan — before any code lands. An all-spec epic silently routes the actual
implementation outside the ticket system.

**Why this matters:** EPIC-QuickFixWorkflow's 16 tickets were all doc-spec-only, so the
real 516-line `SKILL.md`, 440-line `quick-fix.js`, and command template arrived in three
ad-hoc commits with no AC traceability, no test-writer, and no ac-validator — producing
two post-merge defects (`BP-600f` missing main-branch guard; `ACS-700` missing
`origin_agent` in AC scaffolds).
(Source: EPIC-QuickFixWorkflow retrospective KI-1, 2026-07-10.)

### AC-store reconciliation when pivoting to a direct-commit drive

If you abandon a per-ticket epic drive in favour of direct branch commits, reconcile the AC
YAML store fields for every affected AC **before opening the PR** — not post-merge:

- `work_status: done` — only with a passing `# covers:`-tagged test; leave genuinely
  unfinished ACs untouched.
- `implemented_by` / `covered_by` — the real commit and the test that exercises the AC.

**Why this matters:** BO-2200 shipped its code via direct commits while the per-ticket drive
was abandoned, so `work_status` was left `todo` on 24 already-done ACs and 0 were linked to
their tests. Recovery required a post-merge `ac-audit` (four parallel verification agents +
a full green-test pass) to separate the 24 real dones from 5 genuine gaps. In-line
reconciliation before the PR avoids that entirely.
(Source: EPIC-DocumentationCoverageGuarantee FP-1, 2026-08-10.)

### AC-store hygiene — bulk pre-flight before a finalization drive

Before a finalization or sequential commit-batch drive that will fire AC-store hooks,
validate the whole epic's AC YAML set in bulk so violations surface at once rather than as a
serial per-commit hook cascade — child-limit caps, missing parent `covered_by` back-links,
and schema-invalid fields (e.g. a list-valued `test_rationale` that must be a string):

```bash
python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/<component>/
```
(Source: EPIC-DocumentationCoverageGuarantee FP-4, 2026-08-10.)
