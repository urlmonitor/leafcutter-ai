# Retrospective: EPIC-ExceptionHandlingGuardEnforcesTheError

Date: 2026-06-18
Epic duration: 2026-06-17 (scaffold committed) to 2026-06-18 (merged, PR #104)
Branch: EPIC-Exceptionhandlingguardenforcestheerror
Commits: 13 (branch commits, including merge) — see grep "GE-108" across all refs

---

## Summary

EPIC-ExceptionHandlingGuardEnforcesTheError tightened the commit-guardian's
exception-handling AST hook (`check_exception_handling.py`) across three
complementary dimensions:

1. **GE-108a — Subprocess I/O-boundary detection.** Widened `_IO_BOUNDARIES`
   to include all six `subprocess.*` entry-point forms (`run`, `Popen`, `call`,
   `check_call`, `check_output`, `getoutput`), with parity enforcement between
   the Python constant and the `commit_guardian.json` configuration list.

2. **GE-108b — WARNING-or-higher logging threshold.** Replaced the permissive
   `_LOG_CALL_NAMES` set (any function named `error`, `info`, `debug`) with
   `_WARNING_LOG_METHODS` (only `warning`, `error`, `critical`, `exception`
   as attribute calls on an object). Bare `ast.Name` calls no longer clear a
   blind-catch handler regardless of name.

3. **GE-108c — Full tuple rendering in BLE001 violation messages.** Added an
   `ast.Tuple` branch so `except (ValueError, Exception):` is reported as
   `(ValueError, Exception)` rather than the truncated `Exception` fallback.

All three tickets completed within one day and merged as a single PR (#104).
The drive surfaced four significant process problems — two-tree drift, a false
self-hosting sign-off, a destructive build.py invocation during remediation, and
an EMU account `gh pr merge` failure — that are documented below and proposed as
Knowledge Items.

---

## Metrics

| Phase agent | GE-108a | GE-108b | GE-108c |
|-------------|---------|---------|---------|
| test-writer | skipped (empty test_requirements) | skipped | skipped |
| python-coder | signed_off | signed_off | signed_off |
| test-runner | signed_off | signed_off | signed_off |
| pr-reviewer | signed_off | signed_off | signed_off |
| commit | signed_off | signed_off | signed_off |
| pull-request | signed_off | signed_off | signed_off |

No failures recorded in ticket Comments. All blockers were caught outside the
supervisor loop (post-drive spot-checks) and remediated by hand-commits before
finalization.

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 3 sub-tickets |
| Completed tickets | 3 |
| Source AC | GE-108 (registered via /plan-feature → PO v3 → BA v3 → IT PO v3) |
| Git commits (branch) | ~13 (feat + chore + fix + merge; `git log --grep GE-108`) |
| First commit date | 2026-06-17 |
| Last commit date | 2026-06-18 |
| PR | #104 (urlmonitor/leafcutter-ai) |
| Blocker comments (ticket Comments sections) | 0 formal blockers recorded |
| Post-drive hand-fix commits | 2 (GE-108c canonical-tree port + GE-108a self-hosting remediation) |
| Structured feedback entries | 0 (feedback.jsonl empty — pre-epoch or sink unreachable during drive) |
| Subagent quality entries | 0 (subagent-quality category absent from feedback corpus) |
| ADRs authored | 0 (ADR-014 pre-existed; referenced but not created during this epic) |
| Breaking change | No |

---

## What Went Well

- **Three focused tickets, no intra-epic dependency.** GE-108a, GE-108b, and
  GE-108c had no `depends_on` edges between them, so all three could be driven
  concurrently or in any order. The linear execution produced no blocked waiting.

- **GE-108b test coverage was comprehensive.** The test-runner sign-off for
  GE-108b reported 20/20 tests green, including 4 new test classes covering every
  Gherkin scenario in the AC. The BLE001 logic change was well-exercised.

- **Both template trees were kept in sync for GE-108a and GE-108b.** The
  python-coder and pr-reviewer sign-offs for both tickets confirmed that
  `templates/commit-guardian/` and `templates/scripts/commit_guardian/` were
  byte-for-byte identical after each commit.

- **EMU `gh pr merge` failure was quickly diagnosed.** The "Unauthorized:
  mergePullRequest" error was recognised as an EMU account constraint, and
  switching to `urlmonitor` resolved it without data loss. The same symptom was
  already documented in CLAUDE.md for `gh pr create`; this extends the knowledge
  to `gh pr merge`.

- **Mid-drive merge conflict resolved without regressions.** When `origin/main`
  advanced during the drive (GE-109 rename, AC-schema, transform hooks merged),
  the merge conflict in the hook DECISION HISTORY block and test file was resolved
  by keeping both sides. 13 post-merge test failures were confirmed pre-existing
  on `origin/main` baseline — no regressions introduced.

- **Epic was planned from scratch via the formal AC pipeline.** GE-108 started
  as a hand-authored ticket with no AC store entry. Running `/plan-feature`
  (PO v3 → BA v3 → IT PO v3) produced a clean AC tree and scaffold. The
  pre-existing standalone ticket was retired (deferred) to avoid a duplicate
  build — the de-duplication step worked as intended.

---

## Friction Points

- **Two-tree drift: GE-108c fix initially landed only in the legacy tree.**
  `check_exception_handling.py` exists in two locations:
  - `templates/scripts/commit_guardian/` (canonical — `build.py` reads this)
  - `templates/commit-guardian/` (legacy)

  The GE-108c python-coder committed the tuple-rendering fix only to the legacy
  tree. Post-drive spot-checks caught the omission; a manual fix commit
  (`fix(guardrail-engine): port GE-108c to canonical tree`) was needed. Had the
  fix gone undetected, `build.py` would have silently deployed the old
  (unfixed) hook. The sibling epic GE-109a has the IDENTICAL two-tree drift,
  still unfixed as of merge.

- **False self-hosting sign-off on GE-108a.** The python-coder completion
  manifest asserted `self_hosting_non_regression_verified: true`. A post-drive
  spot-check found 11 unwrapped subprocess calls in 6 own scripts
  (`goal_to_epic.py`, `ac_prioritizer.py`, `build_helpers.py`,
  `compute_next_version.py`, `setup_ticket_worktree.py`, and one other) that
  the widened guard would flag, blocking commits once deployed. The AC
  explicitly required self-hosting verification; the phase agent asserted it
  without running the widened guard over the repo. Remediation commit filed
  separately.

- **build.py invoked during remediation and corrupted the worktree.** A
  python-coder dispatched to fix the self-hosting issue ran `build.py`. The
  script deleted approximately 90 tracked files (gitignored build-output
  directories) and rewrote 50+ agent cards. The worktree had to be hard-reverted
  and all fixes re-applied by hand.

- **GE-108b created a second self-hosting regression (14 `# noqa: BLE001`
  handlers).** The `_WARNING_LOG_METHODS` tightening newly flags 14 pre-existing
  `print()` / `warnings.warn()` handlers in `scripts/` that are suppressed by
  `# noqa: BLE001`. The guard does not honour the `# noqa` directive. Ticketed
  separately; not blocking this epic but a known follow-up.

- **No subprocess-form unit tests for GE-108a.** The pr-reviewer sign-off noted
  (`subprocess_test_coverage: false`) that no unit test asserts unwrapped
  `subprocess.run()` is flagged. The existing test suite covers `requests.get`
  and `open()` patterns. A follow-up test-writer pass is recommended.

- **EMU `gh pr merge` failure.** `gh pr merge #104` returned
  "Unauthorized: mergePullRequest" under the `henzeh_roche` EMU account. Merge
  succeeded after `gh auth switch --user urlmonitor`. CLAUDE.md currently
  documents the EMU constraint only for `gh pr create` (and a REST fallback);
  the merge command needs the same coverage.

- **Feedback sink unreachable throughout drive.** All phase-agent `feedback-id`
  fields recorded `(submit-failed)` — the feedback.jsonl sink was empty at
  retrospective time. No telemetry was captured for this epic.

---

## Knowledge Gaps Found

- **No build-time parity guard between the two template trees.** The canonical
  tree (`templates/scripts/commit_guardian/`) and the legacy tree
  (`templates/commit-guardian/`) can drift silently. `build.py` reads only the
  canonical tree, so fixes committed to the legacy tree are silently dropped.
  A CI or build-time diff check between the two trees would catch this before
  merge.

- **Self-hosting ACs are not mechanically verifiable by phase agents.** The
  "self-hosting non-regression" scenario requires running the changed guard over
  the repo's own files. Phase agents currently assert this in a completion
  manifest field without a standardised verification step. There is no hook or
  test that enforces the assertion is based on an actual run.

- **`build.py` must not be run inside a feature/epic worktree.** The build
  script's `_check_script_reference_guard` and template deployment logic operate
  on the working tree as if it is the install root, deleting gitignored
  directories and rewriting agent card files. Running it inside a feature
  worktree causes destructive side-effects unrelated to the ticket's scope.

- **EMU `gh pr merge` failure is not documented.** CLAUDE.md documents the EMU
  constraint for `gh pr create` (with a REST fallback), but `gh pr merge` hits
  the same wall. The Pre-Drive Checklist should cover both create and merge.

---

## Subagent Quality Trends

No supervisor feedback entries found for this epic (feedback.jsonl was empty for
the entire drive — either the sink was unreachable or the drive pre-dates the
feedback epoch for this worktree).

---

## Proposed Improvements

### KI-1: Two-tree parity guard — build-time diff check between template trees

**Proposed addition to `CLAUDE.md` Pre-Drive Checklist (or as a `build.py`
post-deploy assertion):**

```diff
  ### Worktree pre-commit config (MANDATORY for worktree-based drives)
  ...
+
+ ### Template-tree parity check (MANDATORY before merging guardrail-engine changes)
+
+ The exception-handling guard source exists in two trees:
+ - Canonical: `templates/scripts/commit_guardian/check_exception_handling.py`
+ - Legacy:    `templates/commit-guardian/check_exception_handling.py`
+
+ `build.py` reads the canonical tree only. Fixes committed to the legacy tree
+ alone are silently dropped at deploy time.
+
+ **Check:** After any guardrail-engine commit, verify the files are identical:
+ ```bash
+ diff templates/scripts/commit_guardian/check_exception_handling.py \
+      templates/commit-guardian/check_exception_handling.py
+ ```
+ A non-empty diff means the canonical tree is missing the change — port it before
+ merging. (GE-109a has an identical unresolved drift as of 2026-06-18.)
```

Routing: `CLAUDE.md-toc` — add to the Pre-Drive Checklist section in
`/home/henzeh/projects/leafcutter/ge-108-finalize/CLAUDE.md` (or the repo root
equivalent after finalize merges to main).

---

### KI-2: Self-hosting ACs require an actual guard run — not a manifest assertion

**Proposed addition to `templates/skills/building-epics/SKILL.md` under
"Self-Hosting Verification":**

```diff
+ ## Self-Hosting Verification (Mandatory for guardrail-engine tickets)
+
+ When an AC contains a Gherkin scenario named "Self-hosting code stays clean" or
+ equivalent, the phase agent (python-coder) MUST:
+
+ 1. Run the changed guard over the repo's own production Python files:
+    ```bash
+    python templates/scripts/commit_guardian/check_exception_handling.py \
+      $(git -C <worktree> diff --name-only HEAD~1 HEAD -- '*.py')
+    ```
+    (or an equivalent scan of all files in scope)
+
+ 2. Paste the actual stdout/stderr output into the ## Comments sign-off block
+    as evidence.
+
+ 3. Set `self_hosting_non_regression_verified: true` in the completion manifest
+    ONLY if the guard reports exit 0 with no violations.
+
+ Asserting the field without running the guard is a false sign-off. Post-drive
+ spot-checks caught this failure in GE-108a (11 unwrapped subprocess calls in 6
+ own scripts were silently missed).
```

Routing: `agent-frontmatter` — the skill body at
`/home/henzeh/projects/leafcutter/ge-108-finalize/templates/skills/building-epics/SKILL.md`.

---

### KI-3: Coders must not run `build.py` inside a feature/epic worktree

**Proposed addition to `templates/agents/python-coder.md` under constraints /
stop-and-ask rules:**

```diff
+ ## build.py — NEVER run inside a feature/epic worktree
+
+ `build.py` is the package deploy script. Running it inside a feature or epic
+ worktree has destructive side-effects:
+
+ - It deletes gitignored build-output directories that may contain tracked files
+   in the worktree context.
+ - It rewrites all agent card files from the canonical templates, discarding any
+   template edits that have not yet been committed.
+
+ During EPIC-ExceptionHandlingGuardEnforcesTheError (GE-108), running build.py
+ during remediation deleted ~90 tracked files and rewrote 50+ agent cards. The
+ worktree had to be hard-reverted.
+
+ **Rule:** If a ticket's scope requires testing the build output, run build.py
+ against a SEPARATE target directory (e.g., `--target-dir /tmp/build-test/`),
+ never against the worktree root. The deploy/build step is a separate operation
+ from template authoring.
+
+ **Stop-and-ask:** If you believe running build.py in the worktree is necessary,
+ halt and surface to the user before proceeding.
```

Routing: `agent-frontmatter` — the template at
`/home/henzeh/projects/leafcutter/ge-108-finalize/templates/agents/python-coder.md`.

---

### KI-4: EMU account blocks `gh pr merge` — document alongside `gh pr create`

**Proposed diff to the Pre-Drive Checklist in `CLAUDE.md`
(existing "EMU account" bullet):**

```diff
  ### EMU account: open epic PR before drive (if applicable)

  **What to check:** If you are operating under an Enterprise Managed User (EMU)
- GitHub account, `gh pr create` is blocked at the CLI level. Before dispatching
- any tickets:
+ GitHub account, both `gh pr create` and `gh pr merge` are blocked at the CLI
+ level. Before dispatching any tickets:

  ```bash
  # Switch to the non-EMU account
  gh auth switch --user urlmonitor
  ```

- Once the PR exists, the `pull-request` phase on each ticket should detect it via
+ For merge operations (finalize-feature, manual merge):

+ ```bash
+ # Switch before merging
+ gh auth switch --user urlmonitor
+ gh pr merge <number> --merge
+ ```

+ Once the PR exists, the `pull-request` phase on each ticket should detect it via
  `gh pr list --head EPIC-<name>` and push to the existing branch without re-opening.

- **If you skip this:** The pull-request phase on the first ticket that tries `gh pr
- create` under the EMU account will fail with "Unauthorized: As an Enterprise Managed
- User, you cannot access this content (createPullRequest)".
+ **If you skip this:** The pull-request or finalize phase will fail with
+ "Unauthorized: As an Enterprise Managed User, you cannot access this content
+ (createPullRequest / mergePullRequest)". Switch accounts and retry — no data is lost.
```

Routing: `CLAUDE.md-inline` — the existing Pre-Drive Checklist section in
`/home/henzeh/projects/leafcutter/ge-108-finalize/CLAUDE.md`.

---

*All proposed KIs above require explicit user approval before being applied.
No knowledge-home files have been modified by this retrospective.*
