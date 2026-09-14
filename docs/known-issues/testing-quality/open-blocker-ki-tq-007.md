---
title: "KI-TQ-007 — Six review rounds verified a component without once asking what invokes it"
description: "critical as a pattern — the largest miss in the GE-122 review, and the one every"
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

# KI-TQ-007 — Six review rounds verified a component without once asking what invokes it

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** critical as a pattern — the largest miss in the GE-122 review, and the one every
  other finding was standing on
- **Status:** **open as a pattern, with detection shipped and remediation under way** (updated
  2026-09-14). The detection half is closed:
  `unit_tests/commit_guardian/test_hook_registration_inventory.py` is on `main` and asks
  disk → manifest for every hook script, so a new unregistered gate now fails on the day it is
  written. The backlog it exposed is being drained — **18 → 9** (two deleted as bybit-trader
  residue, two reclassified as non-hooks, five registered). `GE-120h` in the AC store is the
  durable parent for the rest. The **pattern** stays open because the review-method half is not
  fixed by a test: nothing yet forces a reviewer to ask the question, and the store's own
  remaining nine are evidence the class persists. The **instance**, `commit-guardian.md`'s
  `KI-CG-021`, is also still open — its code lives only on unmerged PR #495. The **class**
  overlaps `build-orchestration.md`'s `KI-BO-011` (an unreachable file serving as a criterion's
  proof) and `KI-BO-028`, but is not the same: those are about a *test* pointed at dead code,
  this is about a *review method* that never leaves the source tree. Filed separately and
  cross-referenced rather than folded in.
- **Occurrences:** 1 (six rounds), plus 18 standing instances found when the question was
  finally asked mechanically
- **First seen:** 2026-08-25 · **Last seen:** 2026-09-14 (inventory measured on `main`)
- **Where:** the adversarial review method itself; instance at PR #495's
  `check_identifier_uniqueness.py`

**Symptom.** Rounds one through five of adversarial review each found real defects under a green
suite, and each verified the fix by importing the module or running the script directly. Round
six asked a different question — *what calls this in production?* — and the answer was **nothing**
(see `KI-CG-021`). Five rounds of increasingly careful verification had been measuring a
component that could not fire.

Every individual verification was accurate. **None of them was the question.**

**Detection.** For any gate, hook, or runner, verification is not complete until you have
answered, with a grep and not from memory:

1. What config registers this? (`commit_guardian.json`, `.pre-commit-config.yaml`, a CI workflow
   — name the file and the line.)
2. Does it survive `build.py` into a consumer layout? Build one in `/tmp` and run it.
3. Does the **production entry point** produce the observable effect — the exit code, the block,
   the message? Not the function. The entry point.
4. Is the output actually *seen*? A passing `pre-commit` hook's stdout is discarded
   (`KI-CG-026`).

**Fix direction (pattern).** Every hook AC should carry a registration test: assert the hook's id
appears in the deployed `.pre-commit-config.yaml` and that its script resolves. That is a
three-line test which would have failed on day one of the epic and saved six rounds.

**Partially addressed, 2026-09-14 — and the remedy above needed correcting twice.**
`unit_tests/commit_guardian/test_hook_registration_inventory.py` now makes the unasked question
a standing assertion. Two corrections to the fix direction as originally written:

1. **Do not assert against `.pre-commit-config.yaml`.** It is **gitignored build output** emitted
   by `build.py` (`git status --ignored` → `!!`; no git history; absent in a fresh clone).
   Asserting against it verifies the generator's last local run, not the committed registry —
   the same class of mistake as the entry it is meant to prevent. The source of truth is
   `hooks_manifest.hooks` in `templates/scripts/commit_guardian/commit_guardian.json`. A first
   pass of this work did measure against the deployed file and reported 5 phantom "unregistered"
   ids that were only local build staleness.
2. **Per-AC is the wrong unit.** A registration test attached to each hook AC has to be
   remembered by the author of hook nineteen, and not remembering is the defect class. The test
   is an inventory over the whole guardian directory instead, scoped by the repo's own
   `hook_parity.hook_script_patterns` so it cannot drift from `check_hook_parity.py`.

**What it measured on `main` at `2524993b9`: 18 hook scripts on disk that no `hooks_manifest`
entry invokes.** Nine of those (`check_complexity`, `check_docstrings`, `check_documentation`,
`check_doc_coverage`, `check_doc_links`, `check_folder_density`, `check_root_files`,
`check_sql_complexity`, `check_debug_scripts`) carry a settings block in **both** `config.py`
and `commit_guardian.json` while being invoked by nothing — `KI-CG-021`'s shape exactly, and
worse for a reader, because the presence of configuration reads as evidence of registration.
They are held in a shrink-only ratchet baseline; the test is green today and red on the
nineteenth. Triaging the 18 is **not** done and is the remaining work on this entry.

Neither existing gate covered this, which is why the orphans survived: `check_hook_trigger_reachability.py`
iterates the *registry* asking whether any tracked path can fire each gate, so a script absent
from the registry is invisible to it; `check_hook_parity.py` compares scripts across
*directories* and ids across *manifests*, and never asks whether a script on disk is named by
any entry. The unasked question was disk → manifest.

**The general form:** *"does the code work"* and *"is the code reachable"* are different
questions, and a test suite answers only the first. Nothing in 3,772 passing tests could
distinguish this gate from a gate that had never been wired up, because nothing in it looked
outside the source tree.

---
