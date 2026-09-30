---
title: "The guard — candidate fixes for the cwd regression escape"
description: "Seven candidate guards (G1-G7) evaluated against 'would this, mechanically, have turned red on 2026-09-22': fixing the CLAUDE.md pytest recipe, a root conftest pinning cwd, making the bo2400f13 fixture isolate by cwd, a cwd-invariance test, a lint/AC rule on Path.cwd() usage, a CI-mirroring local runner, and a CLAUDE.md knowledge-transfer entry."
type: explanation
status: active
created: 2026-09-28
last_updated: 2026-09-28
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/analysis/2026-09-28-why-the-cwd-regression-escaped-verification.md
---

> **Parent document:** [2026-09-28-why-the-cwd-regression-escaped-verification.md](2026-09-28-why-the-cwd-regression-escaped-verification.md)

## 3. The guard

Evaluated against the standard "would this, mechanically, have turned red on 2026-09-22."

### G1 — Fix the CLAUDE.md test recipe to pin cwd · **do now**

Surface: `CLAUDE.md:657-658`. Change

```bash
python -m pytest <worktree-root>/unit_tests/ -q
```

to

```bash
env --chdir=<worktree-root> python -m pytest unit_tests/ -q
```

**Cost:** one line. **Catches:** this incident outright, and every future
cwd-conditional regression reached through the documented local-suite recipe. **Misses:**
ad-hoc runs that don't use the recipe; agents that construct their own pytest command.
**Why it belongs here:** the prose already says "from the worktree root"; the command
contradicts it. This is not adding a rule, it is repairing one that is currently a
no-op — the fourth instance of that pattern in this file, and the cheapest one yet.
`env --chdir` is a single simple command, compatible with the no-`cd` shell convention
that produced the workspace-parent habit in the first place.

### G2 — A conftest that pins the suite's cwd to rootdir · **do now**

Surface: a new `conftest.py` at the repository root. There is currently **none**
(`pytest.ini` exists; no root `conftest.py`, no `unit_tests/conftest.py`). A
session-scoped autouse fixture that `os.chdir(config.rootpath)` makes every local run
match CI's cwd by construction.

**Cost:** ~10 lines. **Catches:** this incident, and it makes local/CI divergence
structurally impossible for cwd, whether or not anyone follows G1. **Misses:** nothing
in this class — but note it *hides* the variable rather than testing it, so it must be
paired with G4 or the invariance is never asserted, only assumed. **Caveat worth
stating honestly:** pinning cwd to rootdir means a local suite run now behaves exactly
like CI, which for this family means it will create real worktrees in the developer's
repository until the fixture is fixed (G3). G2 without G3 converts a silent
false-green into a loud repo-mutating red. That is the right trade, but it should be
sequenced.

**Do not randomise cwd.** It was on the table; it is theatre with a cost. Randomising
would make failures non-reproducible and would surface dozens of pre-existing
cwd-dependent hook scripts (see §4) as flaky noise unrelated to any change under test.
Determinism plus one explicit invariance test beats randomisation here.

### G3 — Make the fixture isolate by cwd as well as by location · **do now**

Surface: test. `_bo2400f13_fixtures.py:129-143` should pass `cwd=script_path.parent`
(or the fixture `repo_root`) to `subprocess.run`. Today it passes neither, so the
subprocess's repository is decided by whoever launched pytest.

**Cost:** one keyword argument. **Catches:** nothing, prospectively — this is not a
detector. **What it does:** makes the fixture's isolation independent of the resolution
order, so the family stops accidentally encoding a resolver contract it was never
written to test, and stops being able to mutate the real repository. It is the
difference between "these tests fail because the contract changed" and "these tests
fail because occupancy detection is wrong," which is what they exist to say.
**Important:** this must not be the *only* change made, or the regression becomes
invisible again — it removes the accidental detector without adding a deliberate one.
That is G4's job.

### G4 — A test that asserts resolution is invariant under cwd · **do now**

Surface: test, in `unit_tests/build_orchestration/`. Take the same relocated-copy
harness BO-4100d-4's own tests already use
(`unit_tests/build_orchestration/test_bo_4100d_4.py`, which loads the real module via
`importlib.util.spec_from_file_location` from a copied file) and assert that, for a
fixed anchor/subject, the resolved repository is **the same** from at least three
working directories: inside the target repo, inside an unrelated repo, and inside a
non-repo directory.

**Cost:** one test file, no subprocess, fast. **Catches:** this incident, directly and
by name. **Misses:** callers that pass no anchor at all — the invariance assertion is
only as good as the contract it encodes, which is precisely the thing being designed
separately. **Sharpest observation about this guard:** BO-4100d-4's own test file
already varies cwd deliberately, with `os.chdir` in every test and an
`_original_cwd` restore in `tearDown` (`test_bo_4100d_4.py:165-168`, `:199`, `:252`,
`:302`, `:362`, `:407`). The author knew cwd was the live variable and controlled for
it — *within their own file*. What was missing was not awareness, and not a test that
varies cwd; it was a test asserting cwd makes **no difference** to the resolved answer.
Varying a variable and pinning a variable are opposite acts, and only the second is a
regression guard.

### G5 — A lint or AC rule requiring cwd-varying tests for `Path.cwd()` in resolvers · **follow-up, and partly theatre as usually framed**

Surface: pre-commit hook, or an AC `it_requirement`.

**Would it have fired?** Yes — BO-4100d-4's diff adds a literal `Path.cwd()` to a
resolver. **But a rule keyed on the token `Path.cwd()` / `os.getcwd()` is substantially
weaker than it looks**, for a reason §4 makes concrete: the repository's largest
cwd-sensitive surface contains no cwd token at all. Roughly 25 call sites run
`subprocess.run(["git", "rev-parse", "--show-toplevel"], …)` with neither `-C` nor
`cwd=`. Those are cwd-resolved with nothing to grep for. A token-based rule creates the
impression of coverage over a surface it cannot see — which is exactly the failure mode
this whole document is about.

If built, key it on the *behaviour* instead: a check that flags `git rev-parse` invoked
without `-C` or `cwd=`, alongside `Path.cwd()`/`os.getcwd()`. That is a real signal.
The "requires a cwd-varying test" half is unenforceable mechanically (a hook cannot tell
whether a test varies cwd meaningfully) and should be an AC `it_requirement` on
resolver ACs, not a hook.

### G6 — A local runner that mirrors CI · **follow-up**

Superseded in practice by G1 + G2 at a fraction of the cost. CI's environment differs
from local in more than cwd (it runs `python scripts/build.py --target-dir .` first,
`.github/workflows/ci.yml:185`, and sets `AC_ENFORCE_STRICT=1`), so a faithful mirror is
a real project. Worth doing eventually; not the lesson of this incident.

### G7 — Encode the cwd hazard where a resolver author will hit it · **follow-up**

The knowledge exists three times over (`_ac_store_locator.py:30-53`, KI-CG-20260901,
KI-BO-20260921) and reached nobody, because it is filed by component. A short
`CLAUDE.md` entry — *cwd is never a resolution candidate in code that mutates a
repository; anchor on the subject or refuse* — is cheap and at least sits where every
agent reads. Rate it honestly: prose, so weak. It is worth adding only because
`CLAUDE.md` is the one surface every agent loads, not because prose guards work.
