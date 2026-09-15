---
title: "KI-TQ-20260908-node-check-and-xfail-masking-agree-on-a-broken-script — `node --check` cannot prove the engine can load a workflow script, and a bare `pytest` on a not-done AC cannot distinguish pass from masked failure — together they nearly verified a script the engine could not run at all"
description: "KI-TQ-20260908-node-check-and-xfail-masking-agree-on-a-broken-script — `node --check` cannot prove the engine can load a workflow script, and a bare `pytest` on a not-done AC cannot distinguish pass from masked failure — together they nearl"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-20260908-node-check-and-xfail-masking-agree-on-a-broken-script — `node --check` cannot prove the engine can load a workflow script, and a bare `pytest` on a not-done AC cannot distinguish pass from masked failure — together they nearly verified a script the engine could not run at all

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1 (caught only by an unrelated gate, during BP-600d-5)
- **First seen:** 2026-09-08 · **Last seen:** 2026-09-08
- **Where:** `unit_tests/_workflow_engine_harness.py` (`run_e1_import_check`, `run_workflow_under_e2`)
  · `scripts/ac_store/pytest_ac_enforcement.py` (`pytest_runtest_makereport`) · `templates/skills/quick-fix/SKILL.md` §"Phase 3.5 — Scope Expansion Warning (BP-600e-1)" · `templates/workflows-js/quick-fix.js`

**Symptom.** During work on `BP-600d-5`, a change to `templates/workflows-js/quick-fix.js` introduced three pairs of unescaped backticks nested inside a template literal, corrupting an `agent(...)` call. Two independent verification surfaces both reported success on this file, and neither of them could have detected the break:

- **Blind spot 1 — `node --check` parses a file the real engine cannot load.** Workflow scripts use top-level `return`, which is only legal inside a function. `node --check <file>` runs in CommonJS script mode, and Node's module wrapper silently supplies that enclosing function scope — so the corrupted file parses as valid script-mode JS and `node --check` exits 0. The real engine has no such wrapper: it loads scripts by wrapping the body in an async IIFE and executing it via `vm.runInContext()` (see `_JS_SHIM_TEMPLATE` and `_build_shim()` in `unit_tests/_workflow_engine_harness.py`, lines 721–815 and 974–1055), and under that path the same file throws `SyntaxError: missing ) after argument list`. `run_e1_import_check()` (same file, lines 1241–1316) exists specifically to close this gap for the sibling ES-module engine, via `node --check --input-type=module`, which does reject top-level `return` — but nothing routes a CommonJS-mode `node --check` result through it, so a plain syntax check on a `workflows-js/*.js` file still proves nothing about loadability under the engine that actually runs it.
- **Blind spot 2 — a brand-new AC's tests cannot report red under plain `pytest`.** All four tests in `unit_tests/workflows/test_bp_600d_5.py` (confirmed present and covering `BP-600d-5`) were failing on `assert result.result is not None` — the harness could not get a terminal payload back from the corrupted script at all. A bare `pytest` run reported `4 xfailed`, exit 0. `pytest_ac_enforcement.py`'s `pytest_runtest_makereport` hookwrapper (lines 172–260) downgrades any failing `call`-phase test whose `# covers: <AC-ID>` tag resolves to a `work_status` other than `done` to an `xfailed` outcome — and a brand-new AC is, by definition, not yet `done`. The module's own docstring calls this masking "opt-out": `AC_ENFORCE_STRICT=1` was required to see the four failures as real.

**Why the compounding is the finding, not either blind spot alone.** Each mechanism is individually documented and individually defensible — `node --check` was never meant to validate the E2 engine's load path, and xfail-downgrading a not-done AC's red baseline is deliberate TDD-convenience behaviour (see the related `KI-TQ-011` above, which covers a different failure mode of the same plugin). But stacked on the same change, they produced two independently "green" verification surfaces for a script that could not be loaded by the engine at all: a syntax check that could not see the real parse path, and a test result that could not tell "red because the feature is unfinished" from "red because the harness never got a result back." Neither surface, on its own, claims to prove what the other's absence would have exposed.

**Why it did not ship.** `/quick-fix`'s Phase 3.5 scope-expansion gate (`templates/skills/quick-fix/SKILL.md`, confirmed at that heading; mirrored in `quick-fix.js` around lines 702–714 as the `BP-600e-1` check inside the Phase 3 — Fix block) halted the run before the green phase could execute, because the change also touched `templates/skills/quick-fix/SKILL.md` — a second file, which that gate exists to flag. The gate has nothing to do with syntax validity or test masking; it caught this by coincidence. Had the fix been confined to `quick-fix.js` alone, the green phase would have run, reported `4 xfailed`, and read as success.

**The generalisable rule.** A check that passes is not evidence unless you know what it examined. Concretely for this repo: `node --check` on a `workflows-js/*.js` file does not prove the E2 engine can load it — only running it through the engine harness does. And a bare `pytest` result on a test covering a not-yet-`done` AC cannot distinguish "the feature isn't built yet" from "the harness is silently returning nothing" — only `AC_ENFORCE_STRICT=1` surfaces which one occurred.

**Detection that actually works.**

```bash
# Prove the engine can load the script and get a result back — not just that it parses:
python -c "
from pathlib import Path
from unit_tests._workflow_engine_harness import run_workflow_under_e2
result = run_workflow_under_e2(Path('templates/workflows-js/quick-fix.js'))
assert result.result is not None, result.stderr
"

# Always use the strict flag for a new AC's own tests, never a bare run:
AC_ENFORCE_STRICT=1 python -m pytest unit_tests/workflows/test_bp_600d_5.py -v
```

**Fix direction.** Route workflow-script syntax checks through the E1/E2 harness path (`run_e1_import_check` / `run_workflow_under_e2`) rather than a bare `node --check`, wherever a syntax gate exists for `templates/workflows-js/*.js`. For the masking half, `AC_ENFORCE_STRICT=1` should be the default (not opt-in) for any test run scoped to a single not-yet-`done` AC's own new test file — the convenience masking exists for the ambient full-suite run, not for the developer actively driving that AC's red-to-green cycle.

**Related.** `BP-600d-5` (the AC whose tests were masked here) · `KI-TQ-011` above (the same plugin's masking disagreeing with CI's global opt-out — a different angle on the same mechanism) · `KI-BP-20260907-bootstrap-swallows-build-failure` and `KI-BO-20260907-resume-replays-cached-resolver` (same 2026-09-07/08 window, same shape: a loud-looking failure path that a nearby mechanism silently absorbs).

**Pattern:** a check that examined the wrong parse path, and a check that could not distinguish "not built yet" from "silently broken," stacked on the same change — two green surfaces, neither of which was evidence of what the reader assumed it proved.

---
