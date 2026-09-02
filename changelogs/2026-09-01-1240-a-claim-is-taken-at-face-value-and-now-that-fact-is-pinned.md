---
title: "A claim is taken at face value, and now that fact is pinned"
date: "2026-09-01"
time: "12:40"
type: manual
components:
  - build_pipeline
  - testing_quality
summary: "Adds three tests that lock in, on purpose, a known gap in the commit-time proof check: it never looks at whether a test actually does what it claims. No code changed — the gap is accepted by design, and the tests exist so nobody later 'fixes' it by having the check read test source, which would itself be phantom-done one layer up."
description: "BP-1100g-4-i adds unit_tests/commit_guardian/test_bp_1100g_4_i.py (3 tests, 0 production changes) pinning the accepted-paste invariance in check_proof_promise_claim.py (BP-1100g-4): a promise matched only by a pre-existing test given nothing but the covers/angle tags is not refused, the outcome is byte-identical whether the claiming test's body is genuine, unrelated, or wholesale-swapped, and the wording is exactly 'promised and claimed' — never reached/proven/verified/done. All three tests are green on arrival by construction, which is the point, not a gap in coverage."
breaking: false
---

## Entry

The commit-time gate that compares a plan's promised proof against a test's claimed
proof (`check_proof_promise_claim.py`, from BP-1100g-4) has always taken the claim at
face value: if a test is tagged as answering a promise, the gate accepts it and never
opens the test body to check whether it's telling the truth. That is deliberate — the
sibling AC BO-2900a-2 forbids a phantom-done guard from doing its own source-scanning,
on the grounds that a source scan inside a phantom-done guard is itself phantom-done.
The lie this leaves open is only catchable downstream, by an execution observer that
watches the run rather than reads the file.

BP-1100g-4-i's job was to turn that acceptance into a falsifiable, tested fact rather
than a warning buried in a notes field. Because the behaviour was already correct, there
is no production change here — the deliverable is three tests in
`unit_tests/commit_guardian/test_bp_1100g_4_i.py` that pin it: a pasted-tag claim is not
refused and is worded "promised and claimed"; the outcome stays byte-identical across a
genuine body, an unrelated body, and a wholesale body swap; and the invariance holds when
run through the actual deployed hook via `run_hook.py`, not just the library function.

The fast lane could not build this one on its own, and it was right not to. Its
`verify_red_baseline` gate requires at least one newly-added test to fail before a coder
is dispatched, as evidence that the tests constrain something real. These three tests are
a negative control — they assert an absence — so they were green from the moment they were
written, and the lane halted with `all_new_tests_green_at_baseline` and correctly handed
the AC back to `todo`. The gate did its job; the class of AC is what does not fit it. This
is KI-TQ-010 showing up in the machinery instead of on paper.

In place of a red baseline, the verification here was a mutation proof: the exact
prohibited behaviour — judging whether a tagged test actually invokes a subprocess before
counting its claim — was injected into `collect_test_tag_records`, and all three tests
went red, with the byte-identity assertion reporting `'promised and claimed'` against
`'...was never claimed by any test...'`. Reverting brought all three back to green.

Worth recording plainly: that mutation took four attempts, and the first three each
reported "3 passed" while proving nothing. The condition keyed on a token every fixture
already contained, so it never fired. Fixed, and it still didn't fire, because only one
of two real copies of the module was mutated — `scripts/ac_store/` and
`.leafcutter/scripts/ac_store/` are two separate real directories in this tree, not a
symlink pair. Fixed again, and it still didn't fire, because the probe checked a record
field named `angle` when the actual field is `angles` — plural, a list. A mutation that
doesn't land looks exactly like a test that can't fail, and it fails green: "3 passed" was
true and worthless three times in a row. Confirming a probe is present is not the same as
confirming it discriminates. This is the working instance behind
KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy.
