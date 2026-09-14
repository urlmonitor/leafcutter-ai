---
title: "A refusal now tells you what is in the file and where it divides"
date: "2026-09-14"
time: "17:20"
type: manual
components:
  - commit_guardian
  - ac_store
summary: "A file refused for being too long used to give you a number and a fixed sentence. It now names the parts actually found inside that file, accounting for at least half its measured length, and names a division stated as which parts fall each side and what each side would weigh — so the next step is a decision rather than a research task."
description: "New sibling module _file_description.py inside templates/scripts/commit_guardian/, placed there deliberately so build_commit_guardian copies it verbatim and no deploy-map entry is needed. Parts are located in the refused file's own content, never from a table keyed on its kind; the division falls at a boundary between named parts, never at a fixed fraction of the length; a file accounted for by a single part is told no division was found and none is invented. Length arithmetic goes through count_content_lines, so GE-127d keeps owning the counting rule. Both of the AC's named mutations were executed against the finished implementation rather than argued: a kind-keyed fixed inventory reddens three descriptors including the real-artifact one, and a halfway cut reddens the reconciliation arm."
commits:
  - 981b00128
breaking: false
---

## Entry

### Why this one mattered more than it looks

`GE-127e`'s notes make an economic argument, not an ergonomic one: the pressure that
destroys a size standard is the cost of complying **at the moment you are stopped**.
Faced with a bare verdict and a deadline, the cheap responses — strip content, raise the
limit, switch the gate off — win whenever the expensive path stays expensive. Telling
people not to take the cheap path is weaker than making the expensive path cheap.

Until now a blocked author got a length and a fixed sentence pointing at a helper. The
refusal now also names the parts actually found in that file, has them account for at
least half the length the gate itself quoted, and names a division — which parts fall
each side, and what each side would weigh.

A file accounted for by a single part is told no division was found. None is invented.

### Where it lives, and why that is not incidental

`_file_description.py` sits **inside** `templates/scripts/commit_guardian/`.
`build_commit_guardian` copies every file in that directory verbatim, so a sibling there
needs no entry in `scripts/build_phases.py`'s deploy map. A module imported from outside
it would raise `ModuleNotFoundError` in the deployed hook at commit time while every
source-tree test stayed green — this repo has been bitten by exactly that before. The
deployed descriptor would have caught it; not needing it caught is better.

Length arithmetic goes through `count_content_lines`, the same function the ratchet uses.
`GE-127d` owns the counting rule and this record consumes it rather than writing a second
one that could drift.

### The mutations were run, not described

The test author deferred them because there was nothing to inject into yet. There is now,
and they are what distinguishes this from a fixed sentence with more words in it:

- **A fixed inventory keyed on the file's kind**, instead of parts located in its own
  content → **3 red**, including the real-artifact descriptor that runs against a
  genuinely tracked over-limit source file.
- **A division at a fixed fraction of the length**, instead of at a boundary between
  named parts → **1 red**, the reconciliation arm.

Both probes were reverted exactly and their absence confirmed by grep before the suite
was re-run. The fixture's part sizes — 100/130/90/110 of 430 — were chosen by the test
author so that no subset sums to half, which is precisely why a halfway cut cannot
satisfy whole-parts-per-side reconciliation and why the second mutation bites.

### Verification

All under `AC_ENFORCE_STRICT=1`. `GE-127e-1` was `todo` for the whole build, so without
that flag every failure would have been downgraded to `xfail` and the red baseline would
have looked green:

| stage | result |
|---|---|
| red baseline, before any implementation | 7 failed |
| after implementation | 7 passed |
| mutation 1 / mutation 2 | 3 red / 1 red |
| after reverting both | 7 passed |
| `unit_tests/commit_guardian/` | 1452 passed, 4 skipped, 1 xfailed |

1457 collected, with the seven new tests confirmed present rather than deselected. AC
store: `OK: all 470 AC YAML files are valid.`

### Still open

`GE-127e` itself stays `todo`. `GE-127e-2` (two different files must not get the same
advice), `-3` (only help that actually arrives), `-3-i` and `-4` all constrain what this
record produces, and none of them is built. This is the engine; they are the guarantees
about it.
