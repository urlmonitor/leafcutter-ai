---
title: "A tree where the routing step has never run now says so"
date: "2026-09-23"
time: "09:00"
type: manual
components:
  - knowledge_system
  - build_orchestration
summary: "The count of knowledge waiting to be written reads zero for a healthy loop and zero for a loop that has never run once — so the number people check to ask whether captured learnings are reaching their surfaces could not answer the question. A new --status flag answers it from run recency instead: when the routing step last completed in this tree, over which sink, and whether that sink exists."
description: "New scripts/knowledge/harvest_status.py owns the --status payload, the marker read and the marker write. harvest_cli.py gains --status and --marker; an ordinary completed run writes the marker, --status only ever reads it. sink_resolution.py gains deployed_output_root() and resolve_sink_for_status(). Both already-over-limit files shrank rather than grew: harvest_learnings.py 744 to 743 and build.py 1644 to 1637, funded by relocating code. harvest_status.py is registered at all three deploy sites plus a fourth nobody had documented."
commits:
  - 897c49e0
breaking: false
---

## Entry

### The number that could not answer the question

`INF-700a`'s parent criterion promised that an unwired pipeline "shows up as a
number someone can see". That was true while the 28 retained records read as a
permanent backlog. It stopped being true on 2026-08-26, when `INF-700c-1` and
`INF-700c-2` landed: a textless record is ineligible and **not outstanding**, so
the corpus reports zero and the run exits 0.

Which means the waiting count now reads **zero for a healthy loop and zero for a
loop that has never run once**. The signal people were told to look at cannot
distinguish the two.

Restoring a non-zero backlog to recreate the old signal is explicitly forbidden —
`INF-700c` exists to remove exactly that false backlog. So the answer had to come
from somewhere else: **run recency**.

```
$ harvest_learnings.py --status --sink <path> --marker <path>
{"last_run": "never-run", "sink": "<resolved path>", "sink_exists": false}
```

Always exits 0, even never-run. An ordinary completed run writes the marker;
`--status` only reads it.

### Four properties that look like details

**The query creates nothing.** Not the marker, not its parent directory, not the
sink's. A status query that creates its own marker turns the first query into a
run that never happened, and `never-run` becomes unreachable for the life of the
tree. Verified by hand against the real CLI, not only in the suite: the probe
printed `never-run`, and `ls` on the target directory afterwards returned *No
such file*.

**`sink_exists` is a fresh stat at answer time** — never inferred from the marker
or a previous run, which is how a stale figure ends up reported as a current one.
The resolved path sits beside the boolean, so a sink nothing writes to is
distinguishable from a misconfigured one.

**`never-run` is its own value** — not an epoch timestamp, not an empty string,
not an error. `debugging/logs/` is gitignored, so the marker is absent from every
fresh clone, and "never run in this tree" is the *correct* answer there. No
runtime state was committed into the tracked tree to avoid that.

**No figure is shared with the capture-health report.** That one counts agent
runs; this counts timestamps. The payload carries no `routed`,
`skipped_unknown` or `no_learning_text`, so neither report can be derived from
the other. The `--help` text names which of the two to consult for which
question.

### A deliberate deviation from the criterion's own test plan

The fourth descriptor asks for the seam to be driven "under the engine harness".
It is not, and the reason is recorded in the test file.

Under that harness the routing-step dispatch is answered by a hand-typed
dictionary, so no harvester process runs and **no marker is ever written**. A
seam test built on it would be precisely the "status answer tested only against
hand-constructed marker files" failure the criterion's own rationale names as the
thing that descriptor exists to catch. Two real unmocked subprocess invocations
of the production script are used instead — an ordinary completion, then a
`--status` query — so both sides of the seam are the real entry point.

### The ratchet was paid by relocation

| file | before | after |
|---|---:|---:|
| `scripts/knowledge/harvest_learnings.py` | 744 | **743** |
| `scripts/build.py` | 1644 | **1637** |

Both were already over the 400-line limit, so GE-127b-1 refuses any growth. The
budget came from moving code — `HarvestResult.exit_code()` to its own module,
`_deployed_output_root` to `sink_resolution.py` beside the rest of that cluster,
and `build.py`'s knowledge guard-path helper delegating to the manifest function
instead of hand-listing the same tuple a third time. No pre-existing prose was
deleted to make room.

### A fourth deploy site

`harvest_status.py` is registered in `build_knowledge_scripts`'s
`deploy_scripts`, in `_manifest_knowledge_scripts`, and in `build.py`'s
source-path guard.

There is a fourth that was not written down anywhere:
`tests/knowledge/_inf_400c_4_helpers.py` carries a required-siblings tuple whose
own comment says it must track `deploy_scripts`. Five real-subprocess tests broke
without it, because they assemble a synthetic install by copying files
individually rather than running `build.py`. It holds no test function and no
assertion, so the one-line addition is not a specification change — it is the
same deploy-manifest defect this package keeps shipping, in a place nobody had
catalogued.

### What this unblocks

`INF-700a-3` (the how-to) and `INF-700a-4` (the reference) both depend on this.
`-3` in particular requires a *runnable command* for "has the routing step ever
completed in the tree I am standing in", and explicitly refuses an import as a
step. `--status` is that command.
