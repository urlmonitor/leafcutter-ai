---
title: "Out-of-package installs blocked every commit; the manifest now describes where the package actually stood"
date: "2026-09-07"
time: "10:23"
type: manual
components: 
  - build_pipeline
  - commit_guardian
summary: "Fixed a build defect where installing this package as a sibling of the project it deploys into produced a record that falsely claimed the package and the project were in the same place, which blocked every commit in that install with a message the user could not act on."
description: "3 commits (spec, fix, tests) on fast-lane/bp-1500d-1 for PR #715: _relative_package_offset() now uses os.path.relpath instead of Path.relative_to so a sibling install resolves to a real offset instead of raising and silently falling back to package_root: \"\"; template_hashes keys are derived from that same offset via _package_relative_key() so the two halves of the manifest cannot disagree; check_build_drift.py's reader stops collapsing an explicit null package_root into \"\". Verified against a real out-of-package build: template entries 0->174, drift gate BLOCKED verified=0 -> clean verified=174 gaps=0 drifted=0. Tests were green on arrival (harness reads committed content only) and were instead proven to constrain via six mutation-and-revert proofs."
pr: 715
commits: 
  - 1747480b8
  - 317517346
  - 4ea6c5ed1
---

## Entry

If you install this package the way the repo's own consumer-simulation harness deliberately exercises — the producing package cloned as a **sibling** of the project it deploys into, not nested inside it — the build produced a manifest that was wrong at both ends of the producing side, and that record then blocked every commit you tried to make.

### What was broken

`write_build_manifest()` records two things about where the package producing the deployment stood: a `package_root` position field, and an account of every template file it deployed from. For a genuine sibling install, both were wrong, and wrong in the same shape.

`package_root` came out as `""`. That is not a neutral default — the code's own comment defines `""` as *"the package root and the manifest directory are the same directory."* For a sibling install, that is a **definite false claim**, not an absence of information.

The template account came out empty. Every one of the package's template fingerprints was computed via `Path.relative_to(repo_root)`, which raises `ValueError` for a path that isn't a literal subpath of another — exactly the sibling case — and each raise was caught and the entry silently dropped, one file at a time. The record ended up fully accounting for what was deployed, and not at all for what it was deployed *from*.

### What that cost

The drift gate (`check_build_drift.py`) draws its verified count from manifest keys, not a directory walk. An empty template account meant `verified == 0`, and `verified == 0` trips a floor that **blocks every commit** — in a real, working, out-of-package install — with a message the user cannot act on, because the record the gate is reading is itself the thing that misdirected it.

### The fix

Both halves now go through one computation, `_relative_package_offset()`, instead of two that happened to agree only in the two layouts anyone had tested:

- **`os.path.relpath` instead of `Path.relative_to`.** `relpath` resolves a sibling install to a real `"../leafcutter-ai"`-style relative offset instead of raising. `pathlib` never normalises a `..` component, so that offset stays anchored under the manifest's own directory — which is exactly what `check_build_drift.py`'s existing `templates_dir.relative_to(repo_root)` call already expects on the reading side, with no reader change needed for this part.
- **`None` (JSON `null`) only when the position is genuinely inexpressible** (the one case `relpath` itself can't resolve lexically — no shared drive on Windows) — a value distinguishable from both `""` and a real offset at the data level. When it fires, neither template-hashing loop runs, so an empty account arrives *with* the explicit `null`, not silently, as though the package had shipped nothing.
- **Template keys are composed from the same offset the position field records**, via the new `_package_relative_key()` helper. The two halves are now one computation reused twice, not two independent ones that could silently diverge.
- **The reader had the identical fail-open.** `check_build_drift.py`'s `main()` did `manifest.get("package_root", "") or ""`, which collapsed an explicit `null` into `""` — the same "package is right here" misreading, one level downstream. It now checks for `None` first and returns a distinct `BLOCKED` verdict naming the cause, before ever deriving a `family_prefix` from it.

`check_output_drift.py` was read end to end and consumes neither half of the producing-end record (only `output_mappings`), so it needed no change and is unregressed.

### Measured, independently of the test harness

Against a real out-of-package build (package and target as independent sibling directories under a temp root):

| | Before | After |
|---|---|---|
| `output_mappings` | 471 | 471 (unregressed) |
| `package_root` | `""` (false) | a truthful relative offset |
| template entries | 0 | 174, keyed on the same base as the position |
| drift gate | `BLOCKED verified=0` | `clean verified=174 gaps=0 drifted=0` |

Negative controls against hand-corrupted manifests all came back not-clean, as they should: a `null` position is `BLOCKED` naming the cause; a stated-but-wrong position falls through to the pre-existing `verified == 0` floor; and a truthful position paired with a deliberately emptied template account hits that same floor. None of the three reads as clean.

### Scope, stated plainly

This is the fix for the **producing** end of the record — where the package installing the templates said it stood, and what it accounted for from there. The **deployed**-artifact half (`output_mappings`, the per-output side of the same manifest) was already fixed earlier on this branch and is unregressed here, not newly working today.

### A residual, left open

When the position and the key space disagree with each other in a way outside the checks above, the drift gate can still return the right verdict with a misleading diagnosis: exit 2, *"compared 0 templates against a manifest holding N entries,"* without ever naming the record itself as the cause. Not fixed here.

### On the tests

`4ea6c5ed1` adds six tests, one per `BP-1500d-1-i` test-spec entry, plus a paired-layout harness that builds a same-directory install and a sibling install in one session. They were **not** a red-baseline TDD cycle — they were green on arrival, because the harness builds its package copy with `git archive HEAD` and so can only observe committed content; the implementation (`317517346`) necessarily landed first. In place of a red baseline, each test was proven to constrain the behaviour it names by a one-line mutation of that behaviour, shown to fail, then reverted and shown to pass again — six mutations, six failures, six reversions verified byte-identical against the working tree.
