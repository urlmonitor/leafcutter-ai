---
title: "KI-BP-008 — A version gate can skip the entire workflow-install phase and still report a successful build, leaving every deployed workflow silently stale"
description: "KI-BP-008 — A version gate can skip the entire workflow-install phase and still report a successful build, leaving every deployed workflow silently stale"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-27'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-008 — A version gate can skip the entire workflow-install phase and still report a successful build, leaving every deployed workflow silently stale

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **RE-VERIFIED 2026-08-25 — LIVE.** On a scratch adopter I truncated
> `.leafcutter/workflows/fast-lane-ship.js` to one line (source: 1047) and rebuilt with
> `CLAUDE_CODE_VERSION=2.0.100`. Result: exit 0,
> `[WARNING] Claude Code >= 2.1.154 required for workflow scripts. Detected: 2.0.100. Skipping.`,
> then `Stale file cleanup: (no stale files found)` — and the file still one line. The gate
> was driven through the env var read at `build_phases.py:684`, which feeds the identical
> comparison as the `claude --version` probe, so the branch under test is the same one. The
> skip is `build_phases.py:708-713` (`print(...); return 0`).
>
> **Do not "fix the version parse" as the remedy.** The fragile last-token parse at `:693`
> currently falls through to the fail-open branch at `:715-719`
> (`[WARNING] Claude Code version unknown. Installing workflow scripts (fail-open).`), which
> fired on every unforced run in this workspace — it is the only reason workflows install
> here at all. Correcting the parse converts a working fail-open into a clean, silent skip
> and makes this defect *more* dangerous. The safe fix is content comparison (BP-1500c),
> which needs BP-1500d's manifest first. Fix the parse after that, or not at all.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 3
- **First seen:** 2026-08-24 · **Last seen:** 2026-09-25
- **Where:** `scripts/build_phases.py` — the workflow-scripts install phase, lines ~683-720;
  and (second occurrence) the breaking-change gate in `scripts/build.py`

**Second occurrence, 2026-08-25 — same outcome, a completely different cause, and the cause is
arguably worse.** Before driving a ticket I checked the deployed driver against source:

```text
.leafcutter/workflows/build-feature.js   919 lines
templates/workflows-js/build-feature.js  2416 lines   (origin/main)
```

1497 lines behind — predating essentially a month of hardening. Had the drive run, it would
have executed that driver.

The version gate was not involved. `build.py` had been **halting on an unacknowledged
breaking-change gate since 2026-08-18** — the `GE-113c-3` security-allowlist entry — and
refusing to proceed without `--force-breaking`:

```text
  BREAKING CHANGES DETECTED — BUILD HALTED
  [2026-08-18] fix(security-scanner): allowlist basename matching over-suppressed ...
  To proceed after reviewing the steps above, re-run with:
    python build.py --force-breaking
```

That gate did its job: it stopped, loudly, and printed migration steps. The defect is that
**nothing connects "the build halted" to "the deployed tree is therefore now stale."** The halt
is a single event, noticed once by whoever ran it; the staleness is a standing condition that
then persists silently for a week while every workflow run uses the old code. A halted build
leaves exactly the same deployed state as a skipped phase, and neither is reported at *use*
time.

This widens the issue: the register's original framing is about one `return 0` in one phase.
The general statement is that **the deployed tree has no freshness signal of any kind** — not
after a skipped phase, not after a refused build, not after no build at all. Any fix scoped only
to the version gate leaves the breaking-gate route live, and vice versa.

Reproduced end to end: `--force-breaking` brought the deployed driver to 2416 lines, byte-equal
to source, and the subsequent drive ran the current code.

**First occurrence (version gate) follows.**

**Symptom.** The phase probes `claude --version` and compares against
`_MINIMUM_VERSION = "2.1.154"`. When a version is detected and is below the minimum, the
phase prints a `[WARNING]` and `return 0` — deploying nothing. `return 0` is the same
"files written" count a genuinely no-op build returns, so the overall build reports
success. Every deployed workflow keeps whatever content it had, indefinitely, while each
subsequent build says everything is fine. "Stale file cleanup" does not catch it: that
step looks for orphaned files, not out-of-date ones.

**Evidence.** Observed live. `.leafcutter/workflows/fast-lane-ship.js` was **620 lines
against 1047 in source** — 427 behind, with `grep -c "pr-reviewer"` returning `0` on the
deployed copy and `6` on the source. The deployed copy predated PR #485 entirely: no
review phase, no changelog phase. A fast-lane run launched against it therefore executed
the pre-#485 lane, resolved a five-AC set instead of one, and built two criteria against
a superseded spec. Re-running `build.py` from the main checkout in the same environment
installed the current file immediately, so the source was never the problem.

**Why the same environment behaved differently between runs.** The probe is
`subprocess.run(["claude", "--version"], timeout=2)` and parses
`result.stdout.strip().split()[-1]` — the **last** token. On output shaped like
`2.1.154 (Claude Code)` that yields `Code)`, which fails `Version()` parsing, sets
`version_known = False`, and takes the documented fail-open path that installs. So the
fragile parse fails *safe*. The dangerous branch is the one that works: a cleanly parsed
version below the minimum silently skips. A 2-second timeout on an external binary also
means the two paths can alternate between runs on the same machine.

**Why it matters beyond this workspace.** A consumer on an older Claude Code gets this
permanently and invisibly: every `build.py` reports success, and their agents keep running
whatever workflow scripts were deployed the day the gate started tripping. There is no
warning at *use* time, only at build time, in a line that reads like an advisory.

**Fix direction.** A skipped mandatory phase is not a successful build. At minimum,
distinguish "installed 0 because there was nothing to install" from "installed 0 because I
refused", and make the second non-zero or loudly summarised at the end of the build rather
than mid-scroll. Better: record the deployed workflow's source revision (the build manifest
already tracks output mappings) and have the build compare content, so a stale deployed
file is reported as drift regardless of why it was skipped — the same defence KI-BP-005
needs for orphans, in its out-of-date form. Also worth fixing the version parse to take the
first token rather than the last, though note that bug is currently what keeps this
workspace working.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in its stale form — the deployed tree holds an older
version of something the source has moved on from.

**Related.** KI-BP-010 is the cleanup-side counterpart for this same `workflows/` directory:
its `--clean` entry has never executed, so nothing reaps what this phase declines to rewrite.

KI-BP-20260826-1331 is the **write-side twin**: the identical stale-workflow symptom (same
file, same missing review and changelog phases) reached on 2026-08-25 by a build whose install
phase ran fail-open and wrote older bytes from a stale worktree, rather than by this entry's
skip branch. Counted separately because a skipped-phase alarm would not fire on it — but the
source-revision stamp proposed in the fix direction above resolves both, and is the reason to
prefer it over merely making the skip loud.

**Occurrence 3 — 2026-09-25, no build at all: a `git pull` in the dev repo leaves its deployed
workflows behind, and `Workflow(name: ...)` picks the copy nearest the cwd.** Windows 11,
workspace-parent layout (`C:\Users\Hendrik\Code\leafcutter\` holding the repo in `leafcutter-ai/`).
There are two deployed copies of every workflow:

```text
C:\Users\Hendrik\Code\leafcutter\.claude\workflows\plan-feature.js                workspace root
C:\Users\Hendrik\Code\leafcutter\leafcutter-ai\.claude\workflows\plan-feature.js  inside the dev repo
```

`Workflow(name: "plan-feature")`, invoked with cwd `leafcutter-ai`, ran the dev-repo copy, which
had been built 2026-09-09. That build predated `args.workspace_setup_permission` (ACD-2100b-5) and
still read the agent registry through a `status-checker` dispatch, which failed with
`read_failure`. The workspace-root copy was newer. Neither copy had PR #896's fixes (`06bfbddf`,
merged 2026-09-25 17:11 UTC). On 2026-09-27 both deployed files were still missing
`_shellPermittedAgentId` (0 matches) and still sent `pause-persist` to `status-checker`, while the
template had 15 matches. (The dev-repo copy has been rebuilt since the incident and is now dated
2026-09-25 09:31; it is still behind the template.)

What this adds to the entry's general statement ("the deployed tree has no freshness signal of any kind"):

- **No build ran at all, and nothing prompts for one.** The dev repo's only `post-merge` hook is
  `check_ac_done_on_merge.py` (`.pre-commit-config.yaml:533-535`), so a `git pull` that moves
  `templates/workflows-js/` leaves `.claude/workflows/` untouched and says nothing. The
  `post-checkout` drift hook that `setup_ticket_worktree.py` installs
  (`templates/scripts/setup_ticket_worktree.py:1697`) does not fire on `pull`.
- **Which copy runs depends on the cwd.** Picking the nearest `.claude/workflows/` is harness
  behaviour, observed and not traced to repo code. With two deployed copies of different ages,
  the same command runs different code depending on the directory the session started in.
- **The staleness showed up as unrelated defects.** Two bugs already fixed in the template
  (`status-checker` refusing the pause write, and the fail-open worktree setup) were observed live
  and first diagnosed as new. See `KI-BO-20260901-1620` Occurrence 2 and `KI-ACD-004`'s 2026-09-25 recurrence note.

The source-revision stamp in this entry's fix direction would have caught all three. So would a
check at use time: the workflow compares its own embedded template hash with
`templates/workflows-js/<name>.js` when that file exists, and warns before its first dispatch.

---
