---
title: "The emitter and the harvester now read the same list of entry kinds"
date: "2026-09-14"
time: "18:12"
type: manual
components:
  - knowledge_system
  - build_orchestration
summary: "Two sides of the knowledge loop each carried their own idea of what an entry_kind could be, so a learning emitted under a name the harvester did not recognise was silently unroutable. Both now resolve through one declared vocabulary in config/entry_kind_vocabulary.json, and the harvester normalises variants on the READ path — so a record already sitting in a sink, written with an underscore where the canonical name uses a hyphen, routes rather than sits."
description: "New scripts/knowledge/entry_kind_vocabulary.py resolves any written form to its canonical entry kind against config/entry_kind_vocabulary.json; emit_knowledge.py and harvest_learnings.py both go through it instead of their own literals. harvest_learnings.py went from 775 to 744 content lines in the same change, with harvest_result.py, sink_resolution.py, capture_write.py and harvest_cli.py extracted as siblings. All five new modules are registered at both manifest sites (_manifest_knowledge_scripts, build_knowledge_scripts's deploy_scripts) and in build.py's _get_source_paths_for_guard, whose 1:1 cardinality with the deployable set is itself asserted by test_guard_source_paths_match_deployable_set. A dedicated test runs a real build.py --target-dir and then invokes the DEPLOYED emit_knowledge.py as a subprocess."
commits:
  - d46b57325
breaking: false
---

## Entry

### The gap this closes

The loop had a vocabulary problem at its seam. The emitting side wrote an
`entry_kind` onto each captured learning; the harvesting side decided where that
learning went by matching the kind against its own set. Neither side could see
the other's list, so the two drifted the only way they could: quietly. A learning
emitted under a name the harvester did not hold was not an error — it was simply
never routed, and it stayed in the sink looking exactly like a sink with nothing
in it.

`config/entry_kind_vocabulary.json` is now the one declared list, and
`entry_kind_vocabulary.resolve_canonical()` is the one way either side reaches it.

### Normalisation is on the read path, deliberately

`resolve_canonical()` runs when the harvester **reads** a record, not only when
the emitter writes one. That ordering is the point: records already sitting in a
sink were written before this change and cannot be retroactively corrected, so a
write-path-only normalisation would have left every existing record as unroutable
as it was.

Verified against a real sink on a freshly deployed build rather than a fixture:
writing `entry_kind: "memory_project"` — underscore — directly into the sink and
running the harvester produced `1 learnings routed: 1 memory-project; 0
outstanding`. Underscore in, hyphen out.

### The decomposition that came with it

`harvest_learnings.py` measured **775** content lines against a 400 limit. It now
measures **744**, with four siblings carved out along seams that were already
there rather than at arbitrary line counts:

| module | what it owns |
|---|---|
| `harvest_result.py` | the result record the harvester reports |
| `sink_resolution.py` | finding the declared sink |
| `capture_write.py` | writing one routed learning to its destination |
| `harvest_cli.py` | argument parsing and the command entry point |

744 is still 1.9× the limit. The net drop is small because the extraction paid for
the vocabulary read path added in the same commit. This is a step, not an arrival,
and the file stays owned by the decomposition work.

### Registration, and why a manifest entry is not evidence

A knowledge script has to be registered in three places or it fails at a different
layer each time: `build_knowledge_scripts()`'s `deploy_scripts`,
`_manifest_knowledge_scripts()`, and `build.py`'s `_get_source_paths_for_guard()`.
All five new modules are in all three, and the JSON config is registered in the
first and in `build.py`'s output-drift map.

Being *listed* in a manifest is the kind of claim a grep passes on a manifest
nothing consults, so `test_inf_400c_5_h1_deployed_layout.py` does not grep. It
copies the package tree, runs a real `build.py --target-dir`, asserts
`emit_knowledge.py`, `entry_kind_vocabulary.py` and
`config/entry_kind_vocabulary.json` are physically present under the deployed
`.leafcutter/`, and then invokes the **deployed** `emit_knowledge.py` as a
subprocess — which only exits 0 if its sibling import resolves and its vocabulary
config loads. The remaining four modules are held 1:1 with the deployable set by
`test_guard_source_paths_match_deployable_set`, which fails on cardinality.

That distinction is the H-1 finding from this AC's own review: every pre-existing
test resolved these scripts through the source tree, so a green suite said nothing
about a deployed install. A module that imports fine from `scripts/` and raises
`ModuleNotFoundError` from `.leafcutter/` is a failure this repo has shipped
before.

### Verification

| stage | result |
|---|---|
| `tests/knowledge/` | green |
| real `build.py --target-dir` + deployed-subprocess invocation | green |
| real sink, fresh build, underscore variant | `1 learnings routed: 1 memory-project; 0 outstanding` |
| `ruff check` | clean |

### What is still open

`harvest_learnings.py --state` remains a bare relative path, recorded on three ACs
and not addressed here. The completion-path step that calls this harvester without
anyone asking is `INF-700a-1`, in a separate PR — until that lands, this vocabulary
is correct and still only runs when a human types the command.
