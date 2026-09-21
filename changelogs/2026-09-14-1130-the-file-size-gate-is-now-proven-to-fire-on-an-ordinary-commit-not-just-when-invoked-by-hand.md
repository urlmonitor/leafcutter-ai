---
title: "The file-size gate is now proven to fire on an ordinary commit, not just when invoked by hand"
date: "2026-09-14"
time: "11:30"
type: manual
components:
  - commit_guardian
  - ac_store
summary: "GE-127a-1 required the file-length refusal to happen on an ordinary commit with nothing invoked by hand, but all five of its tests invoked the hook by hand — so the one clause separating the criterion from a mere registration fact went unexercised for six days. Every descriptor now drives a real commit, and removing the hook from the commit chain makes them fail, which is the check the old tests could not perform."
description: "Test-only change plus the AC note that recorded the gap; no production file is touched. The obstacle was always collateral rather than a judgement call: a full commit round-trip in a nested build target ran the whole hook suite and check-build-drift failed there for unrelated reasons. GE-120g-1 (PR #767, merged 2026-09-09) shipped the answer — a temp repo whose .pre-commit-config.yaml carries one hook, so the suite that would have failed is never assembled. _ge_127a_1_ordinary_commit_fixture.py applies that shape, seeding the real check_file_size.py plus _resolve_root, _file_size_ratchet, config, run_hook and check_outcome, wiring check-file-size alone, running a real pre-commit install and driving a real git commit. Ablation verified independently: with the hook removed from the generated config the crossing and deployed descriptors go red with the commit silently completing; restored, all five pass."
commits:
  - c5ba155d3
breaking: false
---

## Entry

### A test that asserted more than it did

`GE-127a-1` says the refusal must happen when the author *"performs an ordinary commit —
no extra command, no extra flag, and nothing invoked by hand."* All five of its
descriptors invoked `pre-commit run check-file-size`, which is exactly an extra command
invoked by hand. Two of them said so in their own failure messages — *"An ordinary commit
… must be refused"* — while making no commit.

What they genuinely proved: the hook is registered under that id and behaves correctly
when run, against a real repository with real deployed config and a real exit status.
That is considerably more than a source-grep.

What they could not prove is the clause that separates this criterion from a registration
fact: **that the ordinary commit path reaches the gate at all.** A build where the
manifest entry exists but the hook is never wired into the commit chain passed all five.

### Why it stayed `done` while the gap was open

The behaviour was real throughout, and observed in production — the gate refused an
ordinary commit of a 467-line test file on 2026-09-07 and ran on every ordinary commit
since PR #728. So the criterion was met; what was missing was a test that would notice
if it stopped being met.

Flipping `work_status` to `todo` would have asserted the behaviour was *absent*, which
was false — a second wrong statement rather than a correction of the first. **"Unproven"
and "untrue" are different findings**, and the store has one field for each. The gap was
recorded in the AC's own notes instead, which is how it stayed visible until it could be
closed.

### What unblocked it, exactly as predicted

The AC's notes named `GE-120g` as the blocker and nothing else. That held.

`GE-120g-1` needed the same thing for its own reasons — it governs what a check may do to
the working copy, only observable across a real commit — and shipped a fixture whose
`.pre-commit-config.yaml` carries **one hook**. The collateral `check-build-drift` failure
that forced the original substitution cannot occur in a config that does not contain it.

`_ge_127a_1_ordinary_commit_fixture.py` applies that shape here. Module sufficiency was
established by running the hook rather than by reading imports. Both files sit under the
400-counted-line limit this very gate enforces — 281 and 204 — with the fixture factored
out for that reason.

### The ablation is the evidence

Setting `INCLUDE_CHECK_FILE_SIZE_HOOK = False` removes the hook from the generated config
— registered, never wired — and the crossing and deployed descriptors go red, the commit
silently completing. Restored, all five pass. Run twice, once independently of the
authoring agent.

That world passed all five of the old descriptors. It is the entire reason the
substitution mattered, and the AC now carries a standing constraint: any future change to
this file must keep the ablation reddening something, or the descriptors have drifted back
to proving registration rather than reach.
