---
title: "KI-FC-001 — The sink is resolved from `__file__` while callers pass a CWD-relative override, so one drive splits its feedback across two corpora"
description: "KI-FC-001 — The sink is resolved from `__file__` while callers pass a CWD-relative override, so one drive splits its feedback across two corpora"
type: reference
category: reference
status: active
created: '2026-08-25'
last_updated: '2026-10-14'
components:
  - feedback_collector
related_docs:
  - docs/known-issues/feedback-collector.md
  - docs/known-issues/README.md
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/architecture/feedback-lifecycle.md
  - reports/feedback-snapshots/README.md
  - docs/known-issues/build-orchestration/resolved/resolved-high-ki-bo-20261009-bo100d-probe-pins-a-relative-telemetry-path.md
---

# KI-FC-001 — The sink is resolved from `__file__` while callers pass a CWD-relative override, so one drive splits its feedback across two corpora

> One known issue, split out of `docs/known-issues/feedback-collector.md` on
> 2026-09-14. Index: [feedback-collector.md](../../feedback-collector.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** **RESOLVED** — PR #1169 (merge `818c301c0`, 2026-10-12), INF-500d-4 / ADR-069.
  Verified on `origin/main` `435c11395` on 2026-10-14. See the resolution section at the end.
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

## 2026-09-30 — measured at scale: 18 sinks, 787 records, and the canonical one holds 1

This entry was filed on one drive splitting across two sinks, severity `medium`, occurrences
`1`. Five weeks later the same mechanism has produced a corpus that is almost entirely
unreadable, and it is now actively misleading people about whether feedback works at all.

**The census**, taken 2026-09-30 across the whole workspace
(`find /home/henzeh/projects/leafcutter -name feedback.jsonl`):

| sink | records |
|---|---:|
| `debugging/logs/feedback.jsonl` (workspace root — **the one people check**) | **1** |
| `.leafcutter/debugging/logs/feedback.jsonl` (install tree) | 131 |
| 14 per-worktree `<worktree>/debugging/logs/feedback.jsonl` | 377 |
| remaining sinks (nested `.leafcutter` copies inside worktrees) | 278 |
| **total, 18 files** | **787** |

Parsed cleanly: 787 of 787, zero unparseable lines. Timestamps run **2026-06-05 to
2026-09-30** — unbroken, including the same day as this census. By category: 643 `complete`,
77 `blocker`, 26 `quality-concern`, 21 `tooling-issue`, 10 `knowledge-gap`, 9
`convention-ambiguity`, 1 `subagent-quality`. By severity: 649 `low`, 105 `high`, 33
`medium`.

**Why this matters more than "the corpus is fragmented".** The report that prompted this
census was *"agents are still not writing feedback"*. That conclusion is wrong, and it is
the reasonable conclusion to draw: the canonical workspace-root sink holds **one** record,
so anyone who opens it — or runs a reader pointed at it — sees an empty inbox. The capture
side has been working continuously for four months. **105 `high`-severity records have never
been read by anybody.**

This is the same false-quiet shape `INF-700a-2` closed on the knowledge side: a zero that
means "nothing here" and a zero that means "you are looking in the wrong place" are
indistinguishable to the reader, and the system offers nothing to tell them apart.

**Severity is understated.** `medium` / occurrences `1` described a two-way split in one
drive. What is measured now is an 18-way split in which the consultable sink contains 0.13%
of the corpus, and the practical effect is a stakeholder concluding a working subsystem is
dead. The grading above is left unchanged per this register's convention, but a reader
triaging by severity should weigh this amendment, not the header.

**What the fix direction above does not yet cover.** The `git rev-parse --show-toplevel`
anchor is still right, but on its own it makes every worktree write to its *own* root — 14
correct-but-separate sinks instead of 14 wrong ones. Two further pieces are needed:

- **One declared sink per install**, the way the knowledge plane already does it:
  `config/knowledge_sink.json` is written at build time and read by every producer, so all
  producers agree without each re-deriving a path. `INF-400c-4-v` established that pattern
  and it is working; feedback has no equivalent.
- **A reader that reports where it looked and how many sinks it found**, so a low count is
  attributable. `harvest_learnings.py --status` (INF-700a-2) now does exactly this for
  knowledge — it names the resolved sink and whether it exists. A feedback reader that
  printed `read 1 record from <path>` would have made this four-month gap visible on day one.

**Not done here.** No sink was moved, merged, or deleted — 787 records are intact where they
lie, and consolidating them is a data-migration decision, not a filing decision. The
aggregate above is reproducible from the `find` command at the top of this section.

---

## 2026-10-12 — fix built under INF-500d-4; not closed yet

**What the fix is.** The work follows the "one declared sink per install" direction above.
It does not use the `git rev-parse` anchor proposed in the original fix direction.
[ADR-069](../../../architecture/adrs/ADR-069-durable-log-root-for-workspaces.md) records why
git-based discovery was rejected. The commits are on the epic branch:

| Commit | AC | Change |
|---|---|---|
| `01bf0610a` | INF-500d-4-iii | `config/knowledge_sink.json` gains `operational_log_root` and `feedback_sink`. `build.py --log-root` records the root. The worktree bootstrap passes the main install's recorded root, or warns and passes `--no-log-root`. `sink_resolution.py --print-location`. Parity check for the new keys. |
| `3f356b815` | INF-500d-4-i | `submit_feedback.py` writes only to `feedback_sink`, or refuses with one `destination could not be written` line and exits 1. `_find_project_root` and `_JSONL_DEFAULT`, this entry's root cause, are removed. |
| `81dbae3b2` | INF-500d-4-iv | `emit_event.py`, `inline_work_guard.py` and `plan-feature.js` write under the declared root. |
| `abb24ba8f` | INF-500d-4-v | Readers default to the declared sink and print `read N records from <path>`. They name a differing populated pre-declaration sink once. |
| `eede17c6c` | INF-500d-4-vi | Shipped prompts drop their `--jsonl` / `--log` overrides. The pre-drive probes are read-only. |
| `6dc2df06c` | INF-500d-4-i, -v | One usable-stream rule: a stream counts only directly under an absolute `operational_log_root`. `--no-log-root` records an empty declaration, so writers refuse. `extract_epic_facts.py` reads the declared stream or exits 1. |
| `2a222cb54` | INF-500d-4-iii | Stale means the enduring root holding `operational_log_root` is gone, so an inherited-root harvest is no longer refused as STALE. |
| `59ed536f8` | INF-500d-4 review | A fresh install gets its first write. The Gemini copies resolve the install. `weekly_health.py` reads the declared stream. The bootstrap retries an older worktree build without the flag. Rewrites back the sink up first. |
| `aaffaf70b` | INF-500d-4-iv | `inline_work_guard.py` creates its log directory under a live root and refuses a vanished project. |
| `9ce8d8052` | INF-500d-4-vi | `knowledge-harvester.md` asks `--print-sink` for the sink instead of naming `debugging/logs`. |

Both anchors in the root cause are gone. With no `--jsonl`, the sink is the declared one.
Prompts no longer pass a working-directory-relative `--jsonl`. The symlink route described
above now leads to the main install's declaration, which names the same enduring root.

**Migration decision: none.** No sink is moved, merged or deleted. Reports written into
per-drive worktrees before this change stay where they are. The one-off rescue is
[`reports/feedback-snapshots/`](../../../../reports/feedback-snapshots/README.md).

**Why this entry stays open.** INF-500d-4-vii requires that this entry not be closed until
INF-500d-4-iii through -vi are done, and never on the strength of a documentation record
alone. As of this amendment their AC records are still `work_status: todo`, their tickets'
`test-runner` and `commit` phases are still `needed`, and the branch is unmerged. Close the
entry once those land: move it to `resolved/` and update the index.

Update at finalize (2026-10-12): INF-500d-4-i and -iii through -vi are now
`work_status: done` on the branch. All 175 covers-tagged INF-500d-4 / INF-400c-4 tests pass
under `AC_ENFORCE_STRICT=1`. The entry still stays open until the epic PR is merged, because
"land" means merged.

**Still open after the epic:**

- The BO-100d probe ACs still pin the relative `debugging/logs/agent_telemetry.jsonl`. See
  [KI-BO-20261009](../../build-orchestration/resolved/resolved-high-ki-bo-20261009-bo100d-probe-pins-a-relative-telemetry-path.md).
  Their owner has to change them.
- The harvester's record identity collides. `harvest_learnings._event_hash` keys a record on
  `(timestamp, agent, component, destination, entry_kind)` and leaves out `text`. The
  2026-10-12 knowledge snapshot (PR #1152, `reports/knowledge-snapshots/README.md` on `main`)
  found 16 distinct records sharing 3 hashes. Once one of them is marked processed, the others
  look processed too. INF-500d-4 does not change the hash.

Fixed on the branch since the first amendment, and no longer open:
`extract_epic_facts.py` reads the declared stream or exits 1 (`6dc2df06c`), and
`knowledge-harvester.md` no longer names `debugging/logs` (`9ce8d8052`).

---

## Resolution (2026-10-14)

**Fixed by** PR #1169, `epic/one-durable-log-root-for-every-workspace`, merged to `main` as
`818c301c0` on 2026-10-12. The close condition in INF-500d-4-vii is met. It was checked on
`origin/main` `435c11395`, against the AC records and the code, not a documentation record:

- **The ACs are done on `main`.** `INF-500d-4-i`, `-iii`, `-iv`, `-v`, `-vi` and `-vii` all carry
  `work_status: done` under
  `docs/acceptance-criteria/infrastructure/INF-500-operational-observability/`.
- **Both anchors in the root cause are gone.** `templates/scripts/feedback/submit_feedback.py`
  no longer defines `_find_project_root` or `_JSONL_DEFAULT`; its decision history records the
  removal (`:442`). Without `--jsonl`, the sink is `feedback_sink.resolve_feedback_sink(...)`
  (`:336`), the build-time declaration in `config/knowledge_sink.json` (ADR-069).

**Remainders.** The amendment above listed two. Neither keeps this entry open:

- **The harvester identity collision is fixed.** PR #1175 (`fix/harvest-identity-includes-text`,
  merge `3af00c0b6`, INF-400b-2-iii, `work_status: done`) moved record identity into
  `scripts/knowledge/record_identity.py`. There `event_hash` digests the five required fields
  **plus `text`** (`:55-63`), so distinct learnings that share the five fields no longer collapse
  into one processed record.
- **The BO-100d probe ACs are still open, and are tracked elsewhere.** They still describe an
  appending probe pinned to the relative `debugging/logs/agent_telemetry.jsonl` (for example
  `BO-100d.yaml`, `BO-100d-1.yaml` and `BO-100d-2.yaml` under
  `docs/acceptance-criteria/build-orchestration/BO-100-smart-sequencing/`). That is owned by
  [KI-BO-20261009-bo100d-probe-pins-a-relative-telemetry-path](../../build-orchestration/resolved/resolved-high-ki-bo-20261009-bo100d-probe-pins-a-relative-telemetry-path.md),
  which stayed open when this entry was written and was resolved 2026-10-16.

**Not done here.** No sink was moved or merged. The 2026-09-30 census records stay where they
are, as the 2026-10-12 migration decision says.
