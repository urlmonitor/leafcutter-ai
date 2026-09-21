---
title: "KI-BP-017 — `scripts/feedback/` is never provisioned into a worktree, so the documented signoff feedback call crashes and every affected phase records `(submit-failed)`"
description: "KI-BP-017 — `scripts/feedback/` is never provisioned into a worktree, so the documented signoff feedback call crashes and every affected phase records `(submit-failed)`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-017 — `scripts/feedback/` is never provisioned into a worktree, so the documented signoff feedback call crashes and every affected phase records `(submit-failed)`

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **RE-VERIFIED 2026-08-25 — LIVE, on a real worktree rather than a fixture.** Running the
> documented call in `worktrees/ge122-acs` gives
> `can't open file '.../scripts/feedback/submit_feedback.py': [Errno 2] No such file or directory`,
> exit 2 — byte-identical to the recorded evidence. **14 of 54 live worktrees are in this
> state**, including `EPIC-DeploymentCompleteness`, `ci-ac-gate`, `consumer-install` and
> `ge122-acs`.
>
> **Root cause refined, and it changes the fix.** The entry says the directory is never
> provisioned. In fact `setup_ticket_worktree._bootstrap` *does* run `build.py` at step 5, and
> when that succeeds `install_shims` creates the shim — which is why the other 40 worktrees
> have it. So the real defect is that **a skipped or failed bootstrap build is
> indistinguishable from a successful one** (KI-BP-018). Adding the symlink to
> `setup_ticket_worktree.py` is still worth doing, but it treats the symptom.
>
> *Naming trap for anyone checking coverage:*
> `unit_tests/build_guards/test_bp017_shim_relative_targets.py` is about **AC BP-017**
> (relative symlink targets), which is a different thing from this register entry
> **KI-BP-017**. It is not coverage for this.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/setup_ticket_worktree.py` (no `feedback` reference anywhere);
  `scripts/build_phases.py:1642-1676` (deploys `scripts/feedback/` to the target root only);
  `templates/skills/signoff/SKILL.md:180` and the agent templates that repeat its literal

**Symptom.** Caught live during the GE-120 epic drive — the running agents left their own
stderr on disk:

```text
python3: can't open file '/home/henzeh/projects/leafcutter/worktrees/
  EPIC-TrustThatAGreenCheckActuallyChecked/scripts/feedback/submit_feedback.py':
  [Errno 2] No such file or directory
```

Python exits 2 before the script runs — no config read, no id minted, empty stdout — so the
signoff skill's fallback writes `feedback-id: (submit-failed)` into the ticket. Reproduced
independently with the same command shape: byte-identical message, exit code 2.

**Root cause — this is the deployed-dependency-closure rule violated for an executable.**
`scripts/feedback/` is a build output: `build_phases.py:1642-1676` writes it to
`<target_root>/scripts/feedback/`, and `install_shims` realizes it in the **project root
only** (`/home/henzeh/projects/leafcutter/scripts/feedback -> ../.leafcutter/scripts/feedback`).
It is gitignored (`.gitignore:14`; `git ls-files scripts/feedback` is empty), so it cannot
arrive with the checkout either. `setup_ticket_worktree.py` provisions `.leafcutter` and
`.pre-commit-config.yaml` symlinks and contains **zero** references to `feedback`. The
worktree's `scripts/` therefore exists and is fully populated — 74 entries — with no
`feedback/` subdirectory.

Meanwhile `signoff/SKILL.md:180` prescribes the **CWD-relative** literal
`python3 scripts/feedback/submit_feedback.py ...`, repeated verbatim in
`_signoff_block.md:21`, `python-coder.md:643`, `documentation-verifier.md:465`,
`user-surface-smoker.md:300`, `live-surface-tester.md:358` and
`build-single-ticket/SKILL.md:293`.

**Same family as the entries above.** This register already documents the deployed-dependency
closure failing for `.leafcutter/config/` contents (lines 171-194, 937, citing `BP-900g-8-ii`:
"the deployed-dependency closure covers the data and configuration files a script reads, not
only the modules it imports"). This is the identical rule broken for an executable rather than
a config file, and the register's own "Masking trap" note explains why it stayed invisible:
the workspace root **has** the shim, so the relative call works everywhere except a worktree
— and worktrees are where epics are driven.

**Why high rather than medium.** It is silent by design — `SKILL.md:706` instructs agents not
to abort signoff on feedback failure — so it mints an unfalsifiable `(submit-failed)` that
reads as an environment hiccup. Every phase agent on an affected ticket loses its feedback for
the whole drive. In this run, all three `(submit-failed)` entries were on the one ticket whose
agents followed the documented literal each time; agents on other tickets improvised a working
path. That is the same shape as the 23-lost-events incident CLAUDE.md's pre-drive checklist
was written for, and the pre-drive check does not detect it.

**Fix direction — two independent changes, both needed.** (a) Provision it: have
`setup_ticket_worktree.py` create the `scripts/feedback` symlink alongside the `.leafcutter`
one it already makes. (b) Stop prescribing a relative path: change `SKILL.md:180` and the six
agent templates to invoke `.leafcutter/scripts/feedback/submit_feedback.py`, which resolves in
both layouts. (b) alone stops the crash but routes the write to the install-tree sink, which
is `KI-FC-001` — so it must land together with that fix, not before it.

> **Review note, 2026-08-26 — the KI-FC-001 condition belongs on (a) as well, not only (b).**
>
> As written, the "must land together with that fix" condition is attached only to (b), which
> reads as though (a) were safe to ship alone. It is not, and for the same underlying reason.
>
> `_find_project_root()` (`templates/scripts/feedback/submit_feedback.py:65-77`) starts from
> `Path(__file__).resolve().parent`, and `.resolve()` follows symlinks. So the moment
> `scripts/feedback` in a worktree becomes a **symlink** into the shared install tree — which
> is precisely what (a) creates — `__file__` resolves into the install tree, the six-level
> walk-up finds the install tree's `.claude/`, and `_JSONL_DEFAULT` becomes
> `<install-tree>/debugging/logs/feedback.jsonl`. Same destination as (b). Either way the crash
> stops and the feedback lands somewhere nobody is looking, which is arguably worse than the
> loud `(submit-failed)` it replaces, because it reads as success.
>
> So the accurate statement is: **KI-FC-001 gates both (a) and (b)**, since both route through
> a `__file__` resolved into the install tree. Fix the sink resolution first and (a) and (b)
> become interchangeable in ordering.
>
> One thing to check before reproducing: that symlink now **exists** in the GE-120 worktree,
> created after this entry was filed. A fresh attempt to reproduce the original
> `(submit-failed)` crash there will not reproduce it — it will silently exercise the
> install-tree-sink path instead. Confirm whether `scripts/feedback` is a symlink before
> concluding which of the two failure modes you are looking at.

**Pattern:** a build output that reaches the project root and not the worktrees, called
through a path that only resolves at the project root.

---
