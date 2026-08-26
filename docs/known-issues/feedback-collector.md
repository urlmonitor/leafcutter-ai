---
title: "Known issues — feedback-collector"
description: "Open, observed defects in the feedback-collector component: submit_feedback.py's sink and config resolution, the feedback.jsonl corpus it appends to, and the sidecar fallback agents use to recover a feedback id. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-25
last_updated: 2026-08-26
components:
  - feedback_collector
related_docs:
  - docs/architecture/components/feedback-collector.md
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/supervisor-system.md
---

# Known issues — feedback-collector

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-FC-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-FC-001 — The sink is resolved from `__file__` while callers pass a CWD-relative override, so one drive splits its feedback across two corpora

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/feedback/submit_feedback.py` — `_find_project_root()` (`:65-77`),
  `_JSONL_DEFAULT` (`:101-104`), the `--jsonl` branch (`:522`); callers in
  `templates/agents/ticket-supervisor.md` (`:529`, `:541`, `:553`, `:563`)

**Symptom.** During the GE-120 epic drive, feedback from a single run landed in **two**
different `feedback.jsonl` files. Nine entries went to the worktree's
`debugging/logs/feedback.jsonl`; others — including `fb_2026-08-25_d84ec0a4` — went to
`/home/henzeh/projects/leafcutter/.leafcutter/debugging/logs/feedback.jsonl`, a sink 78
entries deep that nothing in the drive reads back.

The split is per-invocation, not per-run: `c3eaef10` reached the worktree sink 53 seconds
after `d84ec0a4` reached the other one, in the same drive.

**Root cause — two anchors in one function.** `--jsonl` is used verbatim (`:522`), so the
CWD-relative `debugging/logs/feedback.jsonl` that `ticket-supervisor.md` prescribes resolves
against the **working directory**. When `--jsonl` is omitted the default resolves against
**`__file__`** via `_find_project_root()`, which walks up looking for a `.claude/` directory.

In the worktree layout those anchors diverge, because `.resolve()` follows the symlink chain
out of the worktree and the walk then stops at a `.claude/` that lives *inside* the install
tree:

```text
<worktree>/.leafcutter -> leafcutter-ai/.leafcutter -> /home/henzeh/projects/leafcutter/.leafcutter
/home/henzeh/projects/leafcutter/.leafcutter/.claude   EXISTS   <-- ancestor walk stops here
```

Confirmed from the deployed script's own help text:

```text
$ python3 <worktree>/.leafcutter/scripts/feedback/submit_feedback.py --help
  --jsonl JSONL  Override JSONL output path. Default: /home/henzeh/projects/
                 leafcutter/.leafcutter/debugging/logs/feedback.jsonl
```

So whether an agent's feedback is findable depends on whether that agent happened to pass
`--jsonl`.

**Explicitly ruled out during investigation.** This is not a lost write and not a race. The
id is minted at `:516` but printed only at `:530-541`, after a flushed append, entirely
inside `flock(LOCK_EX)`; an `open()` failure at `:525-529` returns 1 **without** printing an
id. Source and deployed copies are byte-identical (md5 `441112614a6a8b15cca9e5eae174b083`).
A recorded id always corresponds to a real appended line — the question is only *which file*
it was appended to.

**Consequence.** No data is lost, but the corpus is fragmented, and `/feedback-report` and
the retrospective read one sink. They will silently under-report — arriving at the same
"quantitative breakdown unavailable" outcome the CLAUDE.md pre-drive check exists to prevent,
by a route that check does not look for. An investigator searching one sink will also
conclude an id was never persisted; that mistake was made and corrected while filing this
entry.

**Fix direction.** Anchor the default sink to the invoking project rather than to the script
file: resolve from `git rev-parse --show-toplevel`, which is correct inside a worktree, and
fall back to the `__file__` walk only when that fails. Harden the walk so a `.claude/` found
*inside* `.leafcutter/` is not accepted as a project root — that marker is an install
artifact. And echo the resolved sink path to stderr on every run, so a split is visible at
the call site instead of at retrospective time.

**Pattern:** two resolution anchors in one code path, agreeing in the layout it was developed
in and diverging in the one it runs in.

---

### KI-FC-002 — The sidecar id-recovery fallback is keyed on whole seconds and shares one stderr file, so parallel agents can read each other's feedback id

- **Severity:** medium
- **Status:** open (latent — mechanism confirmed, no wrong id observed in a ticket yet)
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/feedback/submit_feedback.py` (`:549-550`);
  `templates/skills/signoff/SKILL.md` (`:180`, `:186`)

**Symptom.** When an agent cannot capture the id from stdout, the documented fallback is to
read a sidecar file whose path the script writes to stderr. Both halves of that fallback are
shared state under parallel dispatch:

1. The sidecar is named `feedback_id_<epoch_seconds>.txt` (`:549-550`) — one-second
   granularity. Two entries in this drive, `869bc2f7` and `9057159a`, share timestamp
   `18:52:29Z`. Only one sidecar exists for that second
   (`/tmp/feedback_id_1787683949.txt`), containing `fb_2026-08-25_9057159a`. The other was
   overwritten.
2. Every agent redirects stderr to the **same** `/tmp/feedback_err.txt` (`SKILL.md:180`) and
   greps it for the sidecar path (`SKILL.md:186`).

`/build-feature` dispatches a batch of tickets concurrently, so both collisions are reachable
in an ordinary drive.

**Why it is worth recording while still latent.** It did not bite here — stdout capture
worked for every agent that got that far. But the failure it produces is a *wrong* id written
into a ticket sign-off, not a missing one. A missing id is visible; a plausible id belonging
to another agent's phase is not, and it corrupts the traceability the field exists to provide.

**Fix direction.** Add PID and a random suffix to the sidecar filename. Give each agent a
distinct stderr file — `ticket-supervisor.md` already uses a `feedback_err_<slug>.txt`
convention that the signoff skill does not follow. Neither change is large; the current
naming is only safe under serial dispatch, which is not how epics run.

**Pattern:** a recovery path that assumes one writer, invoked from a fan-out.

---

### KI-FC-003 — `ac-validator` is in no category's `allowed_writers`, so it has never submitted a single feedback record

- **Severity:** medium — silent, and it invalidates the corpus rather than just losing one record
- **Status:** open — code and config are on `main` and live
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `config/feedback_categories.yaml` — the nine `allowed_writers` lists (lines 30, 56,
  82, 91, 119, 147, 176, 185, 212); `scripts/feedback/submit_feedback.py`

> **Recovered from an unmerged branch.** Recorded as `KI-FC-1` in PR #495's parallel
> known-issues register, which was discarded during reconciliation. Re-verified before filing:
> `grep -n 'ac-validator' config/feedback_categories.yaml` still returns **nothing**.

**Symptom.** `ac-validator` is absent from `allowed_writers` in every category.
`submit_feedback.py` therefore rejects it for **every** category, and the agent falls back —
correctly, per the `signoff` skill — to recording `feedback-id: (submit-failed)` and continuing,
because a failed submit is explicitly not a phase failure.

Found on 2026-08-19 when `ac-validator` signed off `GE-122e-2` and reported that every category
had been refused.

**Why this is worse than a lost record.** It is not intermittent. Every `ac-validator` run since
the allowlist was written has contributed **nothing**, so any analysis of the feedback corpus
silently under-represents AC-coverage findings — and reads as *"ac-validator rarely has anything
to report"* rather than *"ac-validator has never been able to report"*. The absence is
indistinguishable from a quiet agent, which is why nine months of runs produced no signal that
anything was wrong.

**Root cause.** Two lists that must agree — the agent registry and the feedback allowlist — with
nothing checking that they do. The file's own decision history shows this is the recurring
failure mode, not a one-off: `user-surface-smoker` (2026-06-03), `frontend-coder` and
`llm-expert` (2026-06-08), and `documentation-verifier` (2026-07-17) were each added
retroactively after the same silent rejection was noticed by hand. `ac-validator` is the fifth.

**Detection.** Grep the corpus for the agent name; an agent with zero entries across many runs is
the tell. Or check membership directly:

```bash
grep -n "allowed_writers" -A 20 config/feedback_categories.yaml
```

**Fix direction.** Add `ac-validator` to the appropriate categories — but that is the fourth
instance of the same manual patch, so it is the smaller half. The useful fix is a build-time or
startup consistency check that every agent with `signoff: true` in `config/agent_registry.json`
appears in at least one category's `allowed_writers`. The general defect is that the two lists
can disagree with nothing noticing.

**Pattern:** the same silent-gate shape as the commit-guardian register's `KI-CG-024` — exit 0, a
fallback that keeps the pipeline moving, and no signal that a capability is entirely absent.
