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
| `_shared_layout_producer.py` | Copies this repository into a private staging directory, runs a real self-targeting `build.py --target-dir <staging>` subprocess, and publishes the result atomically once complete. Owns `get_or_produce_shared_layout()`, the low-level entry point. |
| `_shared_layout_coordination.py` | Cross-process coordination primitives: run identity (`PYTEST_XDIST_TESTRUNUID` when present, else a process-lifetime UUID), the run-scoped shared directory, the `LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG` execution signal, the `fcntl.flock`-based lock, and the durable on-disk success/failure records. |

## Critical Context

- **ONLY for read-only consumers.** A test that mutates the package before building
  (e.g. withholding a dependency to assert a build failure) must build its own copy --
  see `CLAUDE.md`'s "Tests must not spawn their own build.py" section. Routing
  individual tests onto this fixture versus their own copy is a later ticket's per-test
  selector (TQ-600a-2 / TQ-600a-5); this package only provides the mechanism.
- **Self-hosting deploy pattern.** The shared layout is produced by copying this
  repository (excluding `.git`, prior build outputs, and caches -- see
  `_EXCLUDED_NAMES` in `_shared_layout_producer.py`) into a scratch directory, then
  running that copy's own `scripts/build.py` with `--target-dir` pointed at itself. This
  is the same self-hosting invocation `setup_ticket_worktree.py` already uses to
  bootstrap a fresh ticket worktree -- it is why a consumer test can assert
  `(root / "scripts" / "build.py").exists()`: a plain (non-self-hosting) consumer deploy
  never copies `build.py` itself into its target.
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

## Maintenance

- If `build.py`'s manifest-write step (`_write_and_verify_manifest` /
  `write_build_manifest`) is renamed or the manifest filename changes from
  `.build_manifest.json`, update `MANIFEST_FILENAME` in `_shared_layout_coordination.py`
  -- both the completion gate and the publish check depend on it.
- If a new top-level build-output or cache directory is added to this repository (like
  `.claude/`, `.leafcutter/`, `.ruff_cache/`), add its name to `_EXCLUDED_NAMES` in
  `_shared_layout_producer.py` so the staging copy does not carry stale build output
  into the fresh self-targeting deploy.
- Unit tests live in `unit_tests/suite_performance/test_tq_600a_1.py`. Most are suffixed
  `_MANUAL` (they pay a real ~60s deploy) and are excluded from the fast default run;
  only the boundary test that mocks-but-forwards `subprocess.run` runs by default.
- Locking is POSIX-only (`fcntl.flock`); there is no Windows fallback.
