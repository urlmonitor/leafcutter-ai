# leafcutter/scripts/suite_performance/

## Purpose

Cross-process-safe, lazy production of a single "shared reference layout" -- a real
deployed copy of this package -- for the whole pytest run, so read-only tests that only
need to inspect a deployed copy stop paying for their own `python scripts/build.py
--target-dir <tmp>` (measured ~60s each; 77 call sites across 52 test files before this
package existed). See `docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/`
for the full measured evidence and the read-vs-mutate boundary this fixture sits inside.

## Key Files

| File | Purpose |
|------|---------|
| `pytest_shared_reference_layout.py` | The pytest plugin/fixture registration surface. Registered whole-suite via `pytest.ini`'s `addopts` (`-p scripts.suite_performance.pytest_shared_reference_layout`), mirroring the existing `-p scripts.ac_store.pytest_ac_enforcement` precedent. Exposes the `shared_reference_layout` fixture. |
| `_shared_layout_producer.py` | Runs a real, DIRECTED `build.py --target-dir <staging>` subprocess straight into an empty private staging directory (no source-tree copy first), and publishes the result atomically once complete. Owns `get_or_produce_shared_layout()`, the low-level entry point. |
| `_shared_layout_coordination.py` | Cross-process coordination primitives: run identity (`PYTEST_XDIST_TESTRUNUID` when present, else a process-lifetime UUID), the run-scoped shared directory, the `LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG` execution signal, the `fcntl.flock`-based lock, and the durable on-disk success/failure records. |

## Critical Context

- **ONLY for read-only consumers.** A test that mutates the package before building
  (e.g. withholding a dependency to assert a build failure) must build its own copy --
  see `CLAUDE.md`'s "Tests must not spawn their own build.py" section. Routing
  individual tests onto this fixture versus their own copy is a later ticket's per-test
  selector (TQ-600a-2 / TQ-600a-5); this package only provides the mechanism.
- **Directed deploy pattern (not self-hosting).** The shared layout is produced by
  running THIS worktree's own `scripts/build.py --target-dir <staging>` straight against
  an empty staging directory -- no source-tree copy first. This uses the same
  `build.py --target-dir` invocation form `setup_ticket_worktree.py` uses, but the
  opposite starting point: `setup_ticket_worktree.py` self-targets because its target
  directory ALREADY IS a source checkout (it probes for `<root>/scripts/build.py`, then
  builds into that same `<root>`) -- it has no choice. This producer instead starts from
  an empty directory and chose the directed form deliberately: a self-targeting build
  here would first copy this repository's package SOURCE into the staging dir and build
  onto top of it, yielding package source PLUS deployed output (measured ~11,675 files)
  instead of deployed output alone (measured ~775 files) -- the same deployed tree,
  byte-identical in shape at the same relative paths. `shared_layout_integrity` re-walks
  and re-digests the whole published tree after every reader-marked test, so that file-count
  difference is a direct, recurring per-reader cost, not a one-time build-time cost. A
  consumer test asserting the root is real and complete should check
  `(root / ".build_manifest.json").exists()` -- the thing the publish gate below already
  keys on -- rather than `(root / "scripts" / "build.py").exists()`: the removed
  self-hosting shape is what made the latter assertion possible in the first place, which
  made it a circular justification for the expensive shape rather than an independent
  reason to keep it.
- **Completion is gated on `.build_manifest.json`.** The staging directory is renamed
  to its final published path only after that file exists at its root (written near the
  end of `build.py`'s `main()` -- see `scripts/build_main_helpers.py::_write_and_verify_manifest`),
  so no caller can ever observe a partially-written tree.
- **Both outcomes are cached durably.** Success (the published root) and failure (the
  captured subprocess diagnostic) are both persisted so every waiter -- this process or
  another pytest-xdist worker's -- gets the identical outcome without retrying the
  deploy.
- The run-scoped shared directory lives under the OS temp root
  (`tempfile.gettempdir()`), named `leafcutter-shared-reference-layout-<run key>` --
  never under this repository.
- **KNOWN NON-HERMETIC PROPERTY (recorded, not resolved).** Because the directed
  build's `--target-dir` is not also its `package_root`, the written
  `.build_manifest.json`'s `package_root` field is a relative path that escapes the
  staging directory back out into this live worktree (e.g.
  `"../../../../projects/leafcutter/leafcutter-ai"`), rather than the empty string a
  self-targeting build would record. `check_build_drift.py` (lines ~519-571) resolves
  template paths through that same offset, so a deployed drift-gate run pointed at the
  shared layout's root would reach OUTSIDE the layout, back into the live repository. No
  current or planned consumer runs a drift gate against the shared layout, so this is
  inert today -- but re-measure it, do not assume it fixed, the first time a drift-gate
  test migrates onto the shared layout.

## Maintenance

- If `build.py`'s manifest-write step (`_write_and_verify_manifest` /
  `write_build_manifest`) is renamed or the manifest filename changes from
  `.build_manifest.json`, update `MANIFEST_FILENAME` in `_shared_layout_coordination.py`
  -- both the completion gate and the publish check depend on it.
- `_shared_layout_producer.py` no longer copies this repository anywhere (directed build,
  not self-targeting -- see Critical Context above), so there is no `_EXCLUDED_NAMES`
  list to maintain in that file. `pytest_shared_reference_layout.py`'s own
  `_produce_private_copy` (the mutator/undeclared route) still copies this repository into
  its own private, never-shared staging dir and keeps its OWN separate
  `_EXCLUDED_NAMES` constant -- if a new top-level build-output or cache directory is
  added to this repository (like `.claude/`, `.leafcutter/`, `.ruff_cache/`), add its name
  there instead.
- Unit tests live in `unit_tests/suite_performance/test_tq_600a_1.py`. Most are suffixed
  `_MANUAL` (they pay a real ~60s deploy) and are excluded from the fast default run;
  only the boundary test that mocks-but-forwards `subprocess.run` runs by default.
- **How `_MANUAL` exclusion works (TQ-600a-13).** The plugin
  `pytest_manual_deselect.py` (registered via `-p` in `pytest.ini`'s `addopts`) auto-marks
  every test whose name -- the node id up to any `[` -- ends in `_MANUAL` with the
  registered `manual` marker, and `addopts` carries `-m "not manual"`, so the default
  collection deselects them. No decorator or list is needed; the suffix alone is the rule.
  Opt in with `python -m pytest -m manual tests/ unit_tests/` (a command-line `-m`
  overrides the one in `addopts`); `-m "manual or not manual"` collects everything.
- **Known, accepted gap.** The excluded `_MANUAL` tests currently run nowhere in CI: the
  scheduled (nightly) run that TQ-600a-13-i requires does not exist yet, so do not read
  the exclusion as "covered elsewhere".
- Locking is POSIX-only (`fcntl.flock`); there is no Windows fallback.
