---
title: "KI-BP-022 — A deployable script that fails to parse gets an empty closure and a clean bill of health — and 107 of the 152 scripts the guard parses are in `templates/`, which CI's ruff run excludes"
description: "KI-BP-022 — A deployable script that fails to parse gets an empty closure and a clean bill of health — and 107 of the 152 scripts the guard parses are in `templates/`, which CI's ruff run excludes"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-022 — A deployable script that fails to parse gets an empty closure and a clean bill of health — and 107 of the 152 scripts the guard parses are in `templates/`, which CI's ruff run excludes

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED 2026-08-31.** `_closure_walk` now raises `ClosureAnalysisError`
  instead of returning an empty closure, and the guard collects those into a distinct
  `UNANALYSABLE SCRIPT` finding that aborts the build naming the file. The read handler
  now catches `UnicodeDecodeError` alongside `OSError`. The 107-file ruff blind spot is
  NOT closed by this and remains worth closing on its own merits (see Fix direction).
  Found by an adversarial third review round on PR #578, 2026-08-26, after two prior
  rounds had passed the same code.
- **Occurrences:** 1 (latent — no unparseable source today, see Exposure)
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/build_referential_integrity.py:863-873` `_closure_walk`;
  amplifier at `.github/workflows/ci.yml:74`

**Symptom.** `_closure_walk` reads and parses each script inside two handlers:

```python
try:
    text = script.read_text(encoding="utf-8")
except OSError as exc:
    _log.warning("... cannot read %s: %s", script, exc)
    return                      # <-- closure stays empty
try:
    tree = ast.parse(text, filename=str(script))
except SyntaxError as exc:
    _log.warning("... cannot parse %s: %s", script, exc)
    return                      # <-- closure stays empty
```

Both return early, so the script's closure is `set()` and
`find_uncovered_closure_dependencies` reports **zero** missing dependencies for it. A
script with real, undeployed intra-package imports comes back indistinguishable from one
with no dependencies at all. The build proceeds and reports it clean.

There is a WARNING, so this is not literally silent — but it is one line in a build that
emits many, it does not change exit status, and nothing downstream distinguishes "this
script has no dependencies" from "this script's dependencies could not be determined."
That distinction is the entire value of the guard.

**Why the obvious mitigation does not apply.** The natural objection is that a committed
`.py` with a `SyntaxError` would be caught by the required `Lint (ruff)` gate long before
this mattered. That is true for 45 of the guard's inputs and false for the other 107.

CI runs `ruff check scripts tests unit_tests` (`ci.yml:74`), and `ci.yml:8` states the
exclusion outright: "The templates/ source tree is excluded (see ruff.toml)." Measured on
the BP-900g-8 branch by resolving every Set B entry through
`_source_file_for_deploy_path` and recording where it lands:

```
SET B: 152
PARSED FROM templates/ (ruff-excluded): 107
PARSED FROM scripts/  (ruff-covered):    45
```

So **70% of what this guard parses is never linted**, and that 107 is not an arbitrary
slice — it is `templates/scripts/commit_guardian/` in its entirety, every AC hook and
schema validator in the repository, which is the single most consequence-bearing deploy
population there is. A syntax error there is caught by neither ruff nor this guard; the
guard actively reports the file clean.

**Related, same boundary: `except OSError` does not catch `UnicodeDecodeError`.**
`read_text(encoding="utf-8")` on a file with invalid UTF-8 raises `UnicodeDecodeError`,
which subclasses `ValueError`, not `OSError`. It therefore escapes the handler and
propagates out of `compute_intra_package_closure` and
`_check_intra_package_closure_guard`, aborting `build.py` with a raw traceback instead of
the designed `[CLOSURE GUARD]` message. This one **fails closed** — the build stops
non-zero, which is the correct outcome — so it is a diagnosability defect rather than a
false-green, and it is worth noting that it accidentally protects against the read-failure
half of the symptom above. It still violates the repo's own Rule 1 (catch what the
operation can actually raise) and should be fixed alongside, not instead of, the parse case.

**Exposure today.** Verified 2026-08-26: all 152 Set B sources parse, none raise on read,
and both silent-skip branches at `build.py:1109-1113` (`resolved is None`,
`not source_file.is_file()`) fire zero times. Nothing is mis-reported now.

**Fix direction.** Treat "could not determine" as a distinct third outcome from "no
dependencies," not as a synonym for it. The guard is a *preflight* gate whose whole
purpose is to fail closed, so an unparseable or unreadable deployable script should exit
non-zero naming the file — there is no legitimate build in which one of the 152 scripts
about to be deployed cannot be parsed. If that proves too strict during rollout, the
minimum is to surface the count in the guard's own summary output so a human sees "N
scripts could not be analysed" rather than nothing. Widen the read handler to
`(OSError, UnicodeDecodeError)` in the same change. Independently, and cheaper than
either: add `templates/` to the ruff invocation, or add a standalone
`ast.parse`-every-deployable-source check — the 107-file blind spot is worth closing on
its own merits regardless of what this guard does with the result.

**Pattern:** an analyser that reports "I found nothing" and "I could not look" through the
same return value, wired to a gate that only understands the first.

---
