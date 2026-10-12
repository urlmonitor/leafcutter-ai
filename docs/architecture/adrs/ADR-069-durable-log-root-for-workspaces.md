---
title: "ADR-069: One Durable Log Root for Every Workspace, Declared as a Build Input"
description: "config/knowledge_sink.json names one absolute operational_log_root under which every operational log (feedback, telemetry, knowledge emissions) sits, and a per-drive worktree inherits that root from the main install's recorded declaration, because a worktree-relative log directory is destroyed with the worktree and the evidence a retrospective needs goes with it."
type: "adr"
status: "active"
created: "2026-10-09"
last_updated: "2026-10-12"
deciders:
  - adr-author
  - architect-review
components:
  - infrastructure
  - feedback_collector
  - build_pipeline
  - worktree_manager
  - knowledge_system
related_docs:
  - docs/architecture/adrs/ADR-004-consolidated-output-root.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/adrs/ADR-011-learning-emission-sink.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/components/knowledge-system.md
  - docs/architecture/components/feedback-collector.md
  - docs/acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500d-4-iii.yaml
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-400c-4-v.yaml
related_code:
  - scripts/build_phases_knowledge.py
  - scripts/build.py
  - scripts/build_log_root.py
  - scripts/knowledge/sink_resolution.py
  - templates/scripts/feedback/feedback_sink.py
  - templates/skills/agent-telemetry/scripts/emit_event.py
  - templates/hooks/inline_work_guard.py
  - scripts/ci/check_sink_parity.py
  - templates/scripts/setup_ticket_worktree.py
  - scripts/setup_ticket_worktree.py
  - unit_tests/portability/test_inf_500d_4_iii.py
---

# ADR-069: One Durable Log Root for Every Workspace, Declared as a Build Input

## Status

| Field | Value |
|---|---|
| **Status** | Proposed — implemented on `epic/one-durable-log-root-for-every-workspace` 2026-10-12, not yet merged (see [Implementation record](#implementation-record-2026-10-12)) |
| **Date** | 2026-10-09 |
| **Author** | adr-author (dispatched for ticket INF-500d-4-iii after architect-review) |
| **Supersedes** | None |

The status stays `Proposed` until the epic is merged. Promotion to `Accepted` is the user's
call ([write-adr §5](../../how-to/documentation/write-adr.md#5-status-values)).

---

## Context

Every install's build writes one declaration, `<output_root>/config/knowledge_sink.json`,
produced by `build_knowledge_sink_declaration` in `scripts/build_phases_knowledge.py`.
[INF-400c-4-v](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-400c-4-v.yaml)
introduced it to hold `knowledge_emission_sink`, and INF-400c-4-iii added
`operational_telemetry_stream`. Both values come from `target_root.parent`, so each one
lands under `<project_root>/debugging/logs/`. The output root itself is the consolidated
`.leafcutter/` from [ADR-004](ADR-004-consolidated-output-root.md).

The derivation is correct for a plain install. It is wrong for a per-drive worktree.
`templates/scripts/setup_ticket_worktree.py` runs `build.py --target-dir <worktree>` in
every new worktree, so the worktree's declaration names `<worktree>/debugging/logs/`. That
directory is deleted when the worktree is removed. The agent-telemetry log, the
knowledge-emission log and the feedback log all live there, and all three are deleted with
it. INF-400c-4-v records this as an open gap: a build run inside a worktree declares the
worktree's own root. Before this ADR the feedback sink was not in the declaration at all.
Its writers worked out their own location, so it could disagree with the other two streams.

Not deciding has a known cost. The repo's pre-drive checklist was written after a drive in
which 23 `submit-failed` events went unnoticed and no telemetry was captured, which left
nothing for the retrospective. A log directory that disappears with its worktree causes
the same loss without any failure being reported.

Two resolution rules already exist and must not change:

- **Rule (a).** Configuration resolves to the workspace's own `.leafcutter/` (INF-100c-1-i).
- **Rule (b).** Commit-time guards resolve to the worktree toplevel they are judging
  (GE-113c-1-iv).

This ADR adds **rule (c)**: the durable report location. The first scenario of
[INF-500d-4-iii](../../acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500d-4-iii.yaml)
requires rule (c) to be determined independently of (a) and (b). It also requires the
location to resolve to the enduring project, not to the workspace root. The second
scenario requires every log in the directory to move together, so the directory is never
split between a disposable root and an enduring one.

The ticket's originating epic is `EPIC-OneDurableLogRootForEveryWorkspace`, and this
ticket is its first.

---

## Decision

### 1. One declaration names one log root

`build_knowledge_sink_declaration` MUST write two new keys into the existing
`<output_root>/config/knowledge_sink.json`:

- `operational_log_root`: an absolute directory.
- `feedback_sink`: `<operational_log_root>/feedback.jsonl`.

The existing keys `knowledge_emission_sink` and `operational_telemetry_stream` MUST stay.
Every file-valued key MUST sit directly under `operational_log_root`, and every value MUST
be an absolute string. `feedback_sink` MUST NOT equal any other stream's path. A second
declaration artefact MUST NOT be created.

### 2. The root is a build input, never something the build discovers

When no root is supplied, the default MUST be `<target_root.parent>/debugging/logs`. For an
ordinary build this keeps `knowledge_emission_sink` and `operational_telemetry_stream`
byte-identical to their current values, so existing installs and INF-400c-4-iii's
identical-results invariant are not affected.

`build.py` MUST accept an explicit inherited log root, such as a `--log-root` argument, and
MUST record it exactly as given for every key. A relative value MUST be refused before any
declaration is written, with a non-zero exit and an error that names the value. To choose
the root, the build MUST NOT invoke git, walk upward through directories, or search for
marker files. It decides from what was recorded, never from what is around it, which is the
principle INF-400c-4-v set.

### 3. The worktree bootstrap passes the root the main install already recorded

`templates/scripts/setup_ticket_worktree.py` MUST pass the inherited log root to its
`build.py --target-dir <worktree>` call. It MUST read that value from the main install's
existing declaration at `<main_repo>/.leafcutter/config/knowledge_sink.json`:

- the `operational_log_root` key, or
- for a declaration written before this change, the parent directory of
  `knowledge_emission_sink`.

The bootstrap MUST NOT compute the root from `main_repo`'s path. In the development
workspace `main_repo` is `leafcutter-ai/`, but the main install's declared root sits one
level higher. Deriving the root from the path would create yet another log location.

`scripts/setup_ticket_worktree.py` is a tracked build output of the template. It MUST get
the same change, applied as a targeted edit, never as a whole-file resync.

A worktree whose `.leafcutter` is a symlink to the main install MUST keep reading the main
install's declaration through that symlink, with no change in behaviour.

### 4. An unreadable main declaration is reported loudly, never papered over

When the bootstrap cannot get an enduring root from the main install, because the
declaration is absent, unreadable, has no root key, or holds a relative value, it MUST print a stderr `WARNING` that names the path it tried and says that
logs written in this worktree will not survive the worktree's removal.

It MUST NOT leave a declaration that silently names the worktree's own root as
`operational_log_root`. Two outcomes satisfy this rule, and the implementer picks one:

- omit the root, so writers refuse per INF-500d-4-i, or
- refuse the bootstrap.

The declaration read MUST use typed `except` clauses and report at `WARNING` or above, per
the repository error-handling policy.

A bare manual build pointed at a worktree with no inherited root MUST keep INF-400c-4-v's
behaviour: it declares that directory and prints the NOTE. The NOTE MUST now also name the
`operational_log_root` it declared.

### 5. Rules (a) and (b) are untouched; rule (c) lives only in the declared value

Configuration resolution MUST still return the workspace's own `.leafcutter/config`. The
guard root MUST still return the worktree toplevel. The declaration file itself is read
from the workspace's own deployed config, which is rule (a). Only the value it holds names
the enduring root, which is rule (c).

One unified resolver for all three rules MUST NOT be introduced. Rule (c) stays separate
because it is carried by data, not by where the resolver looks.

### 6. One side-effect-free location query

`scripts/knowledge/sink_resolution.py`, or an entry point backed by it, MUST provide one
CLI query. Given `feedback`, `telemetry`, `knowledge` or `root`, it MUST print exactly one
absolute path on stdout and exit 0. It MUST create no file, directory or record.

If the declaration is absent, or the requested key is missing, the query MUST exit non-zero,
print nothing on stdout, and name the expected declaration path on stderr. These are the
same refusal semantics as INF-400c-4-i's `--print-sink`.

Every consumer that needs a log location MUST use this query and MUST NOT restate a path.
The named consumers are the BO-100d pre-drive probe, the prompt surfaces (INF-500d-4-vi)
and `plan-feature.js` (INF-500d-4-iv).

### 7. The parity check enforces the shape; existing branches stay as they are

`scripts/ci/check_sink_parity.py` MUST fail, naming the offending key and value, when any
of these is true:

- `operational_log_root` or `feedback_sink` is missing or not absolute;
- a file-valued key does not sit directly under `operational_log_root`;
- `feedback_sink` equals another stream's path.

Its existing branches 1-3 (INF-400c-4) MUST keep their current behaviour.

### 8. The declaration stays untracked and is deployed with its readers

The declaration holds an absolute path that is specific to one machine. It MUST stay under
the gitignored output root and MUST NOT be committed. Any new helper module the location
query or the bootstrap's declaration read depends on MUST be added to the build deploy
manifest, so deployed readers do not raise `ModuleNotFoundError`.

The files `build_phases_knowledge.py`, `build.py` and `setup_ticket_worktree.py` are
already over the 400-line file-size limit. Root validation and the declaration read MUST be
extracted into `sink_resolution.py` or a new helper rather than added to those files.
`check-file-size` MUST NOT be skipped.

---

## Consequences

### Positive

- Telemetry, knowledge-emission and feedback logs from a worktree drive outlive the
  worktree, so retrospectives keep their evidence.
- All three streams share one directory and one source of truth, so `feedback_sink` can no
  longer disagree with the other two.
- Consumers get locations from one query with no side effects, which removes paths
  restated in prompts, workflows and probes.
- Ordinary installs see no change: their existing values stay byte-identical.
- Because the root is a recorded input, the build stays deterministic and testable. No
  environment probing decides where logs go.

### Negative

- The declaration's schema grows from two keys to four. Every reader and the parity check
  have to understand the new shape, and a declaration written before this change needs a
  fallback in the bootstrap (the parent of `knowledge_emission_sink`).
- The bootstrap now depends on the main install's declaration being present and valid. A
  broken main install produces warnings, or a refused bootstrap, where it used to fail
  silently.
- Logs from every worktree of a project go into one shared directory, so concurrent drives
  append to the same files. Writers must tolerate interleaved appends. This is the same
  property the main install's single sink already has.
- The ratchet requires extraction work in files that are already over the size limit,
  which adds to the change surface.

### Operational

- Worktrees created before this change keep their worktree-local declaration until they
  are re-bootstrapped or rebuilt with `--log-root`.
- A bare manual `build.py --target-dir <worktree>` without `--log-root` still declares the
  worktree's own root. The NOTE now names that root, so the operator can see it.
- The pre-drive feedback-sink check in `CLAUDE.md` and the probes in `building-epics` §1.0
  and `epic-supervisor` get their location from the location query instead of a hard-coded
  `debugging/logs/` path.
- `docs/architecture/components/worktree-manager.md`, `knowledge-system.md` and
  `feedback-collector.md` describe rule (c) and link back to this ADR.

---

## Implementation record (2026-10-12)

What was built on the epic branch, where it refines the decision above:

- **The usable-stream rule.** A declared stream is usable only when the declaration also
  records an absolute `operational_log_root` and the stream is an absolute path directly
  under it. `sink_resolution.read_usable_stream` is the rule. `emit_event.py` stays
  standard-library only and carries an inline copy in `_declared_stream`. Every stream
  writer, every reader that defaults to the declaration, `--print-sink` and the `feedback`,
  `telemetry` and `knowledge` keys of `--print-location` refuse a stream that fails it. This covers hand-written and legacy two-key
  declarations as well as new ones.
- **§4 option chosen: `--no-log-root` records an empty declaration.**
  `build_log_root.declaration_values` returns `{}`, so no root, sink or stream is recorded,
  not only the root. The build prints a NOTE that writers will refuse. Every writer then
  refuses: nothing is written into the worktree. The bootstrap is not refused.
- **Stale means the enduring root is gone.** `sink_resolution.enduring_root_exists` checks
  the directory holding `operational_log_root`: its parent, or the project above it when
  that parent is `debugging` (`enduring_holder`). A declared sink that differs from
  `<project>/debugging/logs` is not stale, because an inherited root (§3) differs on
  purpose. A log directory missing under a live root is a fresh install and gets its first
  write. `feedback_sink.py`, `emit_event.py` and `inline_work_guard.py` apply the same rule,
  and the last two keep an inline copy. These three writers and `plan-feature.js` create only
  up to the log directory, and only under a live root. A vanished project is refused and
  never recreated.
- **Retry for older worktree builds.** When the worktree's own `build.py` predates
  `--log-root` / `--no-log-root` and exits 2 with `unrecognized arguments`,
  `setup_ticket_worktree._bootstrap` retries the build once without the flag. It prints a
  WARNING that the worktree has no durable log root. This case is not reported as
  `missing_config`.
- **§6 query refusal extended.** `--print-location` also refuses a `telemetry`, `knowledge`
  or `feedback` stream that fails the usable-stream rule. It does not test staleness.
- **Gemini copies.** The `.gemini` deployments of `emit_event.py` and `inline_work_guard.py`
  step out of the `gemini` directory, so they read the same install's declaration.

---

## Alternatives

- **Derive the root from `main_repo`'s path inside the bootstrap.** Rejected. In the
  development workspace `main_repo` is `leafcutter-ai/`, while the main install's recorded
  root is one level higher. Path arithmetic would produce a fourth log location that
  matches neither, which is exactly the split the AC forbids.
- **Have the build discover the enduring root (for example with `git rev-parse
  --git-common-dir` or an upward walk for a marker).** Rejected. It breaks INF-400c-4-v's
  rule to decide from what was recorded, never from what is around. It also gives
  different answers depending on the install shape (nested consumer, workspace, symlinked
  `.leafcutter`), and the absolute-path declaration exists to remove exactly that
  variability.
- **One unified resolver for configuration, guard root and log root.** Rejected. Rules (a)
  and (b) must resolve to the workspace and the judged tree, while rule (c) must resolve to
  the enduring project. A single resolver cannot return both answers. The test
  `test_config_and_guard_roots_still_resolve_to_the_worktree` exists to catch this.
- **Move only the feedback sink to the durable root.** Rejected. The second scenario of
  INF-500d-4-iii requires every log in the directory to move together. Moving one stream
  splits the directory across a disposable root and an enduring one.
- **A second declaration file just for the log root.** Rejected. The two streams already
  share one artefact so they cannot drift apart (INF-400c-4-iii). A second file would bring
  that drift back.
- **Symlink every worktree's `.leafcutter` to the main install instead.** Rejected as the
  general mechanism. Symlinking changes rule (a): the worktree would read the main
  install's configuration and deployed templates instead of its own, which is wrong for a
  worktree testing unmerged templates. Existing symlinked worktrees stay supported (§3),
  but the bootstrap cannot require them.
- **Fall back silently to the worktree's own root when the main declaration cannot be
  read.** Rejected. That is the original defect again: logs written into a directory that
  will be deleted, with nothing to say so (INF-400c-4-v: "a second sink produced in silence
  is the original defect restored in full").

---

## References

- Ticket: `tickets/00_inbox/epics/EPIC-OneDurableLogRootForEveryWorkspace/01_TICKET-20261009-INF-500d-4-iii.md`
- AC: [INF-500d-4-iii](../../acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500d-4-iii.yaml)
- Related AC: [INF-400c-4-v](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-400c-4-v.yaml)
- [ADR-004: Consolidated Output Root](ADR-004-consolidated-output-root.md): the output root that holds the declaration.
- [ADR-001: Self-Hosting Boundary](ADR-001-self-hosting-boundary.md): the template/build-output mirroring that §3 relies on.
- [ADR-011: Learning Emission Sink](ADR-011-learning-emission-sink.md): the original split of `knowledge_emissions.jsonl` from the telemetry stream.
