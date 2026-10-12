---
title: "The harvester's state file no longer lands in the directory it was started in"
date: "2026-10-08"
time: "15:00"
type: manual
components: 
  - knowledge_management
  - build_pipeline
summary: "harvest --state used to default to a path relative to the working directory, so one harvest run from the package root could leave a gitignored file that made every later build.py abort. It now defaults to the directory of the resolved sink."
description: "One content commit (bbc4a2df7). scripts/knowledge/harvest_cli.py no longer defaults --state to a cwd-relative literal: --state and --marker default to None and a new apply_state_defaults() fills them from the resolved sink after the caller resolves it (harvest_state.json beside the sink, harvest_last_run.json beside --state). An explicit --state still wins and --status still creates nothing. No directory-qualified literal naming either file remains in scripts/knowledge, so the build closure guard has nothing to match. harvest_learnings.py main() makes the one call and is five lines shorter for the file-size ratchet. Adds AC INF-400c-4-vi with a subprocess test that runs the harvester from a foreign working directory. Resolves KI-KM-20261008. The three workflow knowledge-routing steps and the knowledge-harvester agent omit --state and become correct without edits."
commits: 
  - bbc4a2df7
breaking: false
---

## Entry

`harvest_learnings.py` defaulted `--state` to `debugging/logs/harvest_state.json`, relative to
whatever directory the process was in. A run from the package root that routed an event left that
file there, and the build's closure guard then aborted every later `build.py` run. The file is
gitignored, so `git status` showed nothing.

- **Default is now anchored to the sink.** `--state` defaults to `harvest_state.json` in the
  directory of the resolved sink, and `--marker` to `harvest_last_run.json` beside it.
- **Unchanged:** an explicit `--state` wins, and `--status` still creates nothing and exits 0.
- **Test:** `tests/knowledge/test_inf_400c_4_vi.py`, under new AC `INF-400c-4-vi`.
- **Worth knowing:** the state file for an existing install moves from the working directory to the
  sink's directory, so the first run after upgrading sees an empty watermark there.
