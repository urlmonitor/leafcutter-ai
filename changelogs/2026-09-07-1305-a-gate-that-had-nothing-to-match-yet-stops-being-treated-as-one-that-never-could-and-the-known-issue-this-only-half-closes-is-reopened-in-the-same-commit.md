---
title: "A gate that had nothing to match yet stops being treated as one that never could, and the known issue this only half-closes is reopened in the same commit"
date: "2026-09-07"
time: "13:05"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
  - build_pipeline
summary: "Fixed the pre-commit safety check so a brand-new project with no Python files yet is no longer permanently blocked from its first commit, while flagging plainly that most adopters will still hit a related, still-open blocker from the same gate."
description: "Single-commit fix (889a13334) to templates/scripts/commit_guardian/check_hook_trigger_reachability.py and _hook_trigger_reachability_helpers.py: evaluate_gate gains a fourth verdict, NOTHING-TO-MATCH, for a kind-based files condition (e.g. \.py$) the project holds no matching file for yet, while a location-based condition no checkout could ever produce still reports UNREACHABLE and still blocks. A review finding (H-1) reordered evaluate_gate to consult the exemption registry before the kind check, because the original leading-caret heuristic silently discarded audited ground text for two real entries (check-doc-types-agents, check-hook-parity), measured live as exempt 6->8, nothing_to_match 7->5. Also narrows AC-6/AC-7 to the kind-based population after ac-validator held them, and corrects KI-CG-20260831-0713 from a false CLOSED back to open, since ~28 location-based conditions still block a real adopter's first commit."
commits: 
  - 889a13334
breaking: false
---

## Entry

### The problem: "nothing matches yet" was being read as "nothing ever will"

The `check-hook-trigger-reachability` pre-commit gate walks every registered hook's
`files` pattern and flags one as `UNREACHABLE` when it matches none of the current
checkout's tracked paths. Two of those patterns select files by **kind** — an
extension like `\.py$` — rather than by a fixed location in the tree. A brand-new
project that has not yet added a Python file was treated identically to a pattern
naming a path that literally cannot exist: both came back `UNREACHABLE`, and because
this gate is `always_run: true` with `pass_filenames: false`, that meant an adopter
tracking no Python could not make a commit at all.

### What changed

`evaluate_gate` now draws a distinction between "could this ever match, in principle"
and "does it match right now." A kind-based condition matching zero tracked paths gets
a new, non-blocking fourth verdict, `NOTHING-TO-MATCH`, instead of `UNREACHABLE`. A
location-based condition naming a path no checkout could ever produce is completely
unaffected — it still reports `UNREACHABLE` and still blocks, exactly as before.

A review finding changed how that distinction gets applied. The first version decided
kind-vs-location by looking for a leading `^` anchor, and its own docstring claimed
every location-anchored entry has one. That claim was false for two real, audited
exemption entries — `check-doc-types-agents` and `check-hook-parity` — which both name
exact package-internal locations with no `^` at all. Under the original ordering, the
kind-based check ran first and silently discarded their human-authored exemption
ground before it was ever read. The fix consults the exemption registry **before** the
kind check, so an audited entry is always honored. Widening the `^` heuristic instead
was explicitly rejected: a pattern guess must never override an audited registry entry.

Measured against a real deployed consumer, the effect is exactly the two entries
above moving out of the blocked category: `exempt` went from 6 to 8, `nothing_to_match`
from 7 to 5, and `unreachable` stayed at 28.

### Scope — this is not "adopters can commit now"

This commit fixes the **kind-based** half of the defect only. Of the 46 registered
conditions that carry a `files` pattern, just 3 are kind-shaped; the other 43 are
location-shaped, and 35 of those carry no exemption at all. A real adopter's first
commit **still fails**, with roughly 28 conditions reported `UNREACHABLE`. Because of
that, `KI-CG-20260831-0713` is corrected in this same commit from a false `CLOSED`
back to `open` — it had been closed prematurely when this fix landed, even though the
symptom it describes still reproduces. `BP-100n-4`, the same gate's opposite defect
(it only ever inspects hooks the registry already knows about), is a separate,
unbuilt piece of work. Nothing here should be read as resolving the adopter-blocking
symptom — it is not resolved.

One more thing worth keeping visible: AC-6 and AC-7 were narrowed to the kind-based
population after `ac-validator` held them on review, because the test backing them
uses a synthetic, all-kind-based registry that structurally cannot exhibit the
location-based blocking population above. The narrowing is recorded, with its
justification, in the AC's own `amended_by` history.
</content>
