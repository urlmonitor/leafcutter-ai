---
title: "How to Confirm a Captured Learning Reached Its Page, or Route It by Hand"
description: "Confirm from a finished piece of work's result and from the destination file that an agent's learning was written, establish whether the routing step has ever run in your tree, and run it by hand against an explicitly named sink."
type: how-to
status: active
created: 2026-10-08
last_updated: 2026-10-08
components:
  - knowledge_system
  - infrastructure
related_docs:
  - docs/architecture/agent_knowledge_system.md
  - docs/architecture/adrs/ADR-034-knowledge-write-ownership.md
  - docs/architecture/components/knowledge-system.md
related_code:
  - scripts/knowledge/harvest_learnings.py
  - config/guardrail_gates.yaml
---

# How to Confirm a Captured Learning Reached Its Page, or Route It by Hand

You finished a piece of work during which an agent captured a learning; this
guide confirms the learning landed in its destination file, and routes it
yourself when no routing step ran or the routing step failed.

## Prerequisites

- Python 3 and a shell open at the **tree root**: the repository root in a
  package checkout, the project root in a consumer install. Destination paths
  in the sink are relative to where the routing step runs.
- Background (read once, not restated here): the eligibility rule, the waiting
  count and the exit codes are in
  [Agent Knowledge System, section 5](../architecture/agent_knowledge_system.md#5-write-eligibility-and-the-waiting-count).
  Who writes and why is [ADR-034](../architecture/adrs/ADR-034-knowledge-write-ownership.md).

Two layouts are used below. Every command is given for both.

| Layout | Script path (from the tree root) |
|---|---|
| Package checkout | `scripts/knowledge/harvest_learnings.py` |
| Consumer install | `.leafcutter/scripts/knowledge/harvest_learnings.py` |

The consumer path assumes the default output root `.leafcutter/`. If your
install sets another `output_root`, substitute it. A consumer install built
before the `--status` flag existed rejects it: see Troubleshooting 1.

## What carries the routing step

Routing runs on its own, once, at the end of a completed unit of work, before
that path makes its own commit, so the learning is written into the tree that
commit publishes. Only the completion paths listed as **wired** carry it.

The authority is the top-level `knowledge_routing_wiring` section of
`config/guardrail_gates.yaml` (in a consumer install, `.leafcutter/config/guardrail_gates.yaml`).
Its `wired` list names the paths that carry the step; its `excluded` list names
the ones that do not, each with a reason. A build-time guard fails the build if
a workflow is in neither list. Read that section, not this page, for the
current set: this page does not carry a copy.

For illustration only, as of this writing: `build-epic.js`, `fast-lane-ship.js`
and `quick-fix.js` are wired, and `build-ticket.js` and `finalize-feature.js`
are completion paths that are excluded, so work finished through those carries
no routing step.

Routing is by hand for:

- any completion path in the `excluded` list that is a real completion path
  (the reason text says which);
- work finished outside any workflow script, such as an interactive session;
- any run whose routing step reported `could_not_complete` or `did_not_run`.

## Steps

### Step 1 - Read the routing figures in the finished work's result

Find the `knowledge_routing` object in the terminal result of the wired path
you used:

```json
{"knowledge_routing": {"case": "completed", "read": 1, "written": 1, "unwritten": 0, "detail": null}}
```

- `case: "completed"` - the step ran. Go to Step 6 to prove it worked.
- `case: "could_not_complete"` - the step ran and failed; `detail` says what. Go to Step 3.
- `case: "did_not_run"` - no usable reply; nothing is known. Go to Step 3.
- No `knowledge_routing` key at all - the path does not carry the step. Go to Step 3.

These figures are the step's own report, not proof. `written: 1` does not
tell you the text is on the page.

### Step 2 - Establish whether the routing step has ever completed in this tree

Run `--status` with the same `--state` file the routing step uses. The marker
it reads sits beside that state file, so a different `--state` answers a
different question. It prints one JSON line and always exits 0.

Package checkout:

```bash
python3 scripts/knowledge/harvest_learnings.py --status --state debugging/logs/harvest_state.json
```

Consumer install:

```bash
python3 .leafcutter/scripts/knowledge/harvest_learnings.py --status --state debugging/logs/harvest_state.json
```

Real output (package layout, scratch paths, a tree where nothing had run):

```json
{"last_run": "never-run", "sink": "/home/henzeh/projects/leafcutter/test-logs/inf700a3/sink/knowledge_emissions.jsonl", "sink_exists": true}
```

- `"last_run": "never-run"` - the step has not completed here. Nothing has been
  routed from this tree, whatever the figures in Step 1 said.
- `"last_run": "<ISO timestamp>"` - a run completed here at that time.
- `sink` is the file it would read. `sink_exists: false` is the normal state on
  a fresh tree with nothing emitted yet, not an error to fix.

A timestamp means a run **completed**, not that a learning was written. A
`--dry-run`, and a run over an absent sink, both set it (both were run to
confirm). Step 6 is the check that a learning arrived.

### Step 3 - Resolve the sink you will route from

Name the sink explicitly in every command. Do not rely on the default: outside
a built install the default is `debugging/logs/knowledge_emissions.jsonl`,
which may not exist.

In a consumer install, print the sink the build declared:

```bash
python3 .leafcutter/scripts/knowledge/harvest_learnings.py --print-sink
```

Real output (consumer layout, this workspace):

```text
/home/henzeh/projects/leafcutter/debugging/logs/knowledge_emissions.jsonl
```

A package checkout has no build-time declaration, so `--print-sink` refuses
with exit 1 and a message naming the missing `config/knowledge_sink.json`.
There, use the path your emitting agents wrote to. Substitute your resolved
path for `<SINK>` below.

### Step 4 - Run a dry run first

A dry run decides routing and writes nothing. Use a throwaway `--state` so it
does not disturb the real one.

Package checkout:

```bash
python3 scripts/knowledge/harvest_learnings.py --dry-run --sink <SINK> --state /tmp/harvest_state_dry.json
```

Consumer install:

```bash
python3 .leafcutter/scripts/knowledge/harvest_learnings.py --dry-run --sink <SINK> --state /tmp/harvest_state_dry.json
```

Real output (one text-bearing record in a scratch sink):

```text
1 learnings routed: 1 memory-project; 1 outstanding
```

`outstanding` is the waiting count from section 5: records with text not yet
written. Nothing was written; the destination file does not exist yet.

### Step 5 - Run the routing step by hand

Use the same `--state` the automatic step uses (`debugging/logs/harvest_state.json`
from the tree root), or a record already written may be written a second time.

Package checkout:

```bash
python3 scripts/knowledge/harvest_learnings.py --sink <SINK> --state debugging/logs/harvest_state.json
```

Consumer install:

```bash
python3 .leafcutter/scripts/knowledge/harvest_learnings.py --sink <SINK> --state debugging/logs/harvest_state.json
```

Real output and exit status (scratch sink and state):

```text
1 learnings routed: 1 memory-project; 0 outstanding
exit: 0
```

An absent sink is the no-work state, not a fault. Real output for a sink path
that does not exist (exit 0, nothing created):

```text
INFO harvest_learnings: Declared sink not found (no-work run): /home/henzeh/projects/leafcutter/test-logs/inf700a3/absent/knowledge_emissions.jsonl
0 learnings routed: none; 0 outstanding
exit: 0
```

For exit codes 1 to 4, use the table in section 5. To recover from a failed
routing step, fix what the message names (an unwritable destination, a corrupt
state file) and run this step again: records not yet written are retried, and
written ones are skipped.

### Step 6 - Open the destination file and find the learning text

The check that counts is the artefact, not the exit code. Find the record you
expect in the sink, read its `destination` and `text`, then search the
destination for that text.

```bash
tail -n 3 <SINK>
```

```bash
grep -n -F "<first words of the record's text>" <destination>
```

Real result (scratch destination, after Step 5):

```text
1:DEMO-LEARNING-7c41: the routing step must be pointed at an explicit sink.
```

If the destination is relative, open it from the tree root where the routing
step ran. If the work ran in a worktree that has since been removed, look in
the merged tree, and check the file was committed with the work:

```bash
git log --oneline -n 3 -- <destination>
```

A record with no `text` is ineligible by design (section 5) and writes
nothing; its absence from the destination is correct.

## Verification

```bash
grep -c -F "<first words of the record's text>" <destination>
```

Expected output: `1` (the text appears once). `0` means the learning is not
on the page: return to Step 5. `2` or more means it was written more than once:
see Troubleshooting 3.

## Troubleshooting

1. **`--status` fails with `unrecognized arguments: --status`.** The deployed
   consumer copy predates the flag. Real output from a stale install:
   `harvest_learnings: error: unrecognized arguments: --status`. Rebuild the
   install from a current package checkout (`python <package>/scripts/build.py --target-dir <project-root>`)
   and re-run Step 2.
2. **`--print-sink` exits 1 naming `config/knowledge_sink.json`.** You are in a
   package checkout with no build-time declaration. This is the refusal working
   as designed: pass the sink path you know to `--sink` instead.
3. **The text is in the destination twice.** The routing step ran under a
   different `--state` than the automatic one. Remove the duplicate line by hand
   and use `debugging/logs/harvest_state.json` from the tree root from now on.
4. **`--status` says `never-run` after a wired path finished.** Either the path
   was not wired (check the `excluded` list), or it ran in a different tree or
   `--state` than the one you queried. Query the tree it ran in.

## See Also

- [Knowledge-routing step reference](../reference/knowledge-routing-step.md) - the
  report fields, the three outcomes and the `--status` answer, field by field.
- [Agent Knowledge System](../architecture/agent_knowledge_system.md) - eligibility,
  waiting count, exit codes (section 5).
- [ADR-034](../architecture/adrs/ADR-034-knowledge-write-ownership.md) - why the
  harvester writes and agents only emit.
- [Knowledge System component](../architecture/components/knowledge-system.md)
- [Documentation Index](../INDEX.md)
