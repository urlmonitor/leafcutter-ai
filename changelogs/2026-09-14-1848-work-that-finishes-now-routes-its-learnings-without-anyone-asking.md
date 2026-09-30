---
title: "Work that finishes now routes its learnings without anyone asking"
date: "2026-09-14"
time: "18:48"
type: manual
components:
  - knowledge_system
  - build_orchestration
  - infrastructure
summary: "The knowledge harvester had no caller. Emission worked, the sink resolved, the vocabulary routed — and none of it ran unless a human typed the command, which is why the loop reported zero routed learnings while records sat unread in the sink. Three completion paths now dispatch a routing step immediately before their own publishing commit, and a build-time guard refuses to build when a new completion path ships with neither wiring nor a declared exclusion."
description: "build-epic.js, fast-lane-ship.js and quick-fix.js each gain a knowledge-routing step anchored to the commit that path already makes, per ADR-040. config/guardrail_gates.yaml gains a knowledge_routing_wiring section listing wired and excluded paths, each exclusion carrying a reason and the path that covers its emissions instead. check_knowledge_routing_wiring() and its guard live in build_phases_knowledge.py and enumerate templates/workflows-js/*.js; build.py's main() holds only the call site. On a PASSING run the guard states which artefact kinds it examined and which it structurally cannot see, so a green build never implies coverage it does not have. Three subprocess tests drive build.py's real entry point and assert a non-zero exit."
commits:
  - 3d0f050a7
breaking: false
---

## Entry

### The thing that was missing was a caller

Every piece of the knowledge loop worked in isolation. An agent could emit a
learning. The sink resolved. The vocabulary routed the entry kind to a
destination. What nothing did was *run the harvester*.

That is why this morning's measurement read `0 routed; 0 outstanding` while 28
records sat in the sink. Zero routed and zero outstanding is the reading you get
from a healthy empty pipeline and from a pipeline nobody ever started, and nothing
in the output told the two apart.

Three completion paths now dispatch a routing step: `build-epic.js`,
`fast-lane-ship.js`, `quick-fix.js`.

### Where the step is anchored, and why that is a decision

Immediately before each path's **own** publishing commit — so any learning the
step routes is carried by a commit the path was already going to make. That is
ADR-040's requirement, and for quick-fix specifically it means the **fix** commit,
not the later changelog commit. `INF-700a-5`'s requirements name the fix commit
and call the changelog commit out as the wrong anchor.

This broke `test_quick_fix_workflow.py`'s topology test at index 9:
`'knowledge-routing-step' != 'commit'`. The implementation was right and the
expected list was stale; the list was updated with a comment recording which
anchor is correct and why, so the next reader does not re-derive it.

### The guard, and the half of it that was missing

`check_knowledge_routing_wiring()` enumerates `templates/workflows-js/*.js` and
aborts the build when an artefact is neither wired nor excluded.
`config/guardrail_gates.yaml`'s new `knowledge_routing_wiring` section holds both
lists, and every exclusion carries a reason plus the path whose routing step covers
its emissions instead.

Its own review blocked it on two findings, both real.

**The residual-disclosure criterion was not implemented.** `INF-700a-1-i` requires
the detection to state which kinds of artefact it examined and which kinds it
cannot see — **on a passing run**, so a green build never implies coverage it does
not have. The guard printed nothing on success, and the test the AC names by name
did not exist under that or any other name. The passing path now prints the
workflow artefacts examined, by name and count, and the kinds it structurally
cannot see: skills and commands.

**No test reached the guard through the real entry point.** All five tests imported
the function directly; the file had zero subprocess invocations. That is verbatim
the failure this AC's own `test_rationale` warns about — *"a guard that exists, is
tested in isolation, and is never reached from the deployed entry point"*.

The naming told the story. The AC names
`..._BLOCKS_THE_BUILD`; what existed was `..._is_reported`. Reported is not blocked.

Three subprocess tests were added — including
`test_removing_a_path_from_the_exclusion_list_makes_the_guard_block`, which was
absent under any name. Each copies the real `templates/`, `scripts/` and `config/`
trees into a synthetic package root and runs `build.py`. The original five
direct-call tests were kept unweakened as unit coverage: added to, not substituted.

### Reachability was proven, not asserted

Twice — once after the tests were written, once after the guard moved out of
`build.py`. Comment out the call in `main()`, watch all three subprocess tests fail
on `returncode 0`, restore, confirm green.

Both runs under `AC_ENFORCE_STRICT=1`. Without it, `pytest_ac_enforcement`
downgrades a not-yet-done AC's failure to `xfail`, and a genuine red reads as "did
not fail" — so the disable-and-watch-it-break proof would have produced a green
result on a disabled guard. Three separate agents hit that mask on the same day.

### Two oversized files grew, and both are named here

| file | before | after |
|---|---|---|
| `scripts/build.py` | 1915 | 1924 (+9) |
| `scripts/build_phases.py` | 2677 | 2681 (+4) |

Both are grandfathered far over the **400**-line limit, and GE-127b-1 forbids any
growth in an already-oversized file. The guard's body was moved out of `build.py`
into `build_phases_knowledge.py` (206 content lines), beside the knowledge helpers
it belongs with; `build.py` keeps only the call site. The residual nine lines are
that call site — an import, the if/return, and a five-line explanatory comment that
predates this work. The four in `build_phases.py` are a re-export and its comment.

Getting under would have meant deleting the comment or shaving blank lines, which
is gaming a guard whose purpose is to make oversized files shrink honestly.
`check-file-size` was skipped on explicit instruction instead, with **both** files
named in the commit rather than letting the second ride along silently. At 1924 and
2681 against a 400 limit, both need the decomposition work that owns them.

### Verification

| stage | result |
|---|---|
| `unit_tests/workflows/` + `unit_tests/build_guards/` | 793 passed, 3 skipped |
| `validate_ac_schema.py docs/acceptance-criteria/infrastructure/` | all 249 valid |
| real `build.py --target-dir` | exit 0, disclosure printed |
| disable the call site, under `AC_ENFORCE_STRICT=1` | 3 red; restored, green |
| `ruff check scripts/ unit_tests/` | clean |

### What this completes, and what it does not

With the shared `entry_kind` vocabulary (`INF-400c-5`, separate change) the loop
closes: an agent emits a learning with its text, it lands in the install's declared
sink, a completion path routes it without anyone asking, and it rides that path's
own commit into the merged tree.

Still open: `INF-700a-2`'s last-run marker, `INF-700a-5` and its children, and the
`INF-700a-3`/`-4` documentation. The guard also cannot see skills or commands — it
says so on every passing run rather than leaving that to be discovered.
