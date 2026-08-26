---
title: "The negative control for the proof-kind tag — and the one of its four tests that could not fail"
date: "2026-08-26"
time: "10:31"
type: manual
components:
  - build_pipeline
  - testing_quality
summary: "BP-1100g-3-i proves the `# angle:` axis feeds no pass, done, or eligibility decision. Four tests, all green on arrival by construction — so they were falsified by injecting the leak they forbid. Three caught it. The fourth, carrying the AC's headline clause, did not, and was strengthened until it did."
description: "BP-1100g-3-i, the negative control BP-1100g-3 (merged earlier today as 2f740cc4, PR #574) left open. g-3 shipped work_status: done while this child stayed todo -- the falsely-done-composite shape CLAUDE.md's AC-store-commits rule warns about, and the thing ac-validator flagged as status: question on the g-3 drive. Closing this makes that done honest. The AC asserts an ABSENCE: that stripping every kind tag from a suite changes no run outcome and no completion decision. n_location_rule is 0 -- no production file is edited, and the entire deliverable is four tests. Because the property is an absence and 2f740cc4 left _classify_outcomes and verify_done_eligible byte-for-byte unmodified, the suite is green on arrival BY CONSTRUCTION. That inverts this repo's standard red-baseline rule, and the ticket says so explicitly so the drive neither halts on a false TDD-order violation nor manufactures a red by weakening an assertion; it also states the converse, that a RED result here names a real leak to surface as a blocker rather than a test to adjust. THE PART THAT MATTERED: a negative control that cannot fail is worth nothing, and green tests do not prove they can go red. So the four were falsified by mutation rather than trusted. Two leaks were injected into scripts/ac_store/done_proof.py and reverted after each run -- leak A, consumption only, where _classify_outcomes treats an angle-carrying record as passing; leak B, A plus the plumbing that makes the axis reachable end-to-end by attaching angles onto the covers records in _scan_single_test_file; and leak C, leak B applied to the deployed .leafcutter/ copy. Results: the criterion test caught leak A and B; the seam test caught B; the reachability test correctly ignored A and B, because it resolves scripts/commit_guardian through the symlink into .leafcutter/ and a source-tree mutation SHOULD be invisible to it, and under leak C it failed decisively with exit 0 tagged versus exit 1 untagged -- a flipped merge decision, exactly what it guards. The real_artifact test caught NOTHING, and it carries AC-5, this AC's headline clause. Its only FAILING fixture test carried no angle tag, and the likeliest real leak -- an angle-tagged test proves what it claims, so count it passing -- is observable only on a test that is both angle-tagged AND failing. Fixed in scope by adding `# angle: failure` to that fixture, with a DISCRIMINATING FIXTURE docstring note recording the mutation result so the tag is not later removed as noise; re-verified green unmutated and RED under leak B alongside the other two. Every mutation was reverted and checked: done_proof.py is byte-identical to origin/main and the deployed copy byte-matches its pre-mutation backup. Worth stating plainly, because it is the same failure mode one level up: both test-runner and python-coder reported all-green correctly and neither had reason to ask whether green meant anything. A test written to prevent phantom-done was itself, in one of four cases, phantom. Also recorded: the drive halted mid-run because test-runner's Edit tool was disabled for its session, so it could not write its own sign-off. It refused to fall back to a Bash file mutation -- correct, both CLAUDE.md files forbid it and ticket files are untracked and unrecoverable if truncated -- and returned a halt naming the exact three edits it owed. An environment gap surfaced rather than worked around; the edits were applied verbatim by hand."
breaking: false
---

## Entry

`BP-1100g-3` shipped `done` with this child `todo`. This closes it — and the closing turned out to be the interesting part.

**What the AC asserts** is an *absence*: strip every `# angle:` tag and nothing about pass, done, or eligibility changes. `n_location_rule: 0` — no production file is edited. The whole deliverable is four tests.

**Which means the suite is green on arrival**, by construction, if `g-3` was built right. That inverts the standard red-baseline rule, so the ticket said so up front — otherwise the drive either halts on a false TDD-order violation or weakens an assertion to manufacture a red.

**And a negative control that cannot fail is worth nothing.** So the four tests were falsified by injecting the leak they exist to forbid:

| test | angle | consumption leak | + plumbing | deployed leak |
|---|---|---|---|---|
| 1 | `criterion` | **RED** | **RED** | — |
| 2 | `seam` | green | **RED** | — |
| 3 | `real_artifact` | green | **green** | — |
| 4 | `reachability` | green *(correct)* | green *(correct)* | **RED** |

Test 4's green under a source mutation is right, not a gap: it resolves `scripts/commit_guardian` through the symlink into `.leafcutter/`, so a source edit *should* be invisible. Mutating the deployed copy made it fail hard — **exit 0 with the tag, exit 1 without**. A flipped merge decision.

**Test 3 caught nothing, and it carries AC-5.** Its only *failing* fixture test had no angle tag, and the likeliest leak — *"this test is angle-tagged, so it proves what it claims"* — is only visible on a test that is both tagged **and** failing. So the whole-suite strip test could not observe the very leak it exists to forbid.

Fixed by tagging that fixture `# angle: failure`, with a `DISCRIMINATING FIXTURE` note recording the mutation result so nobody strips it as noise later. Now red under the leak, still green without it.

**The uncomfortable part.** `test-runner` and `python-coder` both reported all-green, correctly. Neither had reason to ask whether green *meant* anything. A test written to prevent phantom-done was, in one case out of four, phantom.

**One process note.** The drive halted because `test-runner`'s `Edit` tool was disabled for its session. It refused to fall back to a Bash file mutation — correct, and ticket files are untracked and unrecoverable if truncated — and returned a `halt` naming the exact three edits it owed. That is the right failure: surfaced, not worked around.
