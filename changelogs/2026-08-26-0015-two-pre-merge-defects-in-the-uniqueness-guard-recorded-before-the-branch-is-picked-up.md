---
title: "Two pre-merge defects in the uniqueness guard, recorded before the branch is picked up"
date: "2026-08-26"
time: "00:15"
type: manual
components: 
  - commit_guardian
summary: "Files KI-CG-032 and KI-CG-033 (filed as KI-CG-016/017, renumbered 2026-08-26 after an id collision with two entries already on main) against unmerged PR #495 — a YAML fast path that fabricates id claims for records a full parse rejects, and a placeholder-marker rule that treats markdown emphasis as a list bullet on the strength of a false-positive measurement taken from one marker and claimed for six."
description: "Documentation only — no code changes, and neither defect is present on main. Both live on the unmerged PR #495 branch feat/ge-122-integrity-guard and are recorded now so they survive the branch being picked up later. KI-CG-032, filed as KI-CG-016 and renumbered 2026-08-26 (medium): _fast_scan_top_level_id validates only the id: line and its immediate successor, while _read_yaml_id's contract is that an unparsable record yields no claim; the caller falls back to the full parse only when the fast path returns None, so a wrong non-None answer is never corrected and any YAML syntax error after the id: line produces a fabricated claim. Reproduced end to end with an unquoted value containing a colon — scan_acceptance_criteria returns passed=False with a phantom collision naming two claimants where the contract admits one, so the author is blocked with a duplicate-id message when the real fault is a syntax error in a different file. A fuzz comparison diverged on 6 of 24 inputs. It is latent today — zero divergences across all 3097 real AC files — but the reason it is latent is itself the concern: 3096 of 3097 are answered by the fast path, so the full-parse safety net runs exactly once across the whole store and is not a meaningful second opinion. The entry explicitly rules out another token special-case as the fix, because rounds 4, 5 and 6 of this PR's review each added one and each introduced the defect the next round found; the durable options are bailing on any unclassified non-blank line after id:, or re-scoping the documented contract. It also records that the round-6 document-end token fix IS correct — lone trailing ..., with trailing space, with trailing comment, and with no trailing newline all agree with the full parse — so nobody reopens it. KI-CG-033, filed as KI-CG-017 and renumbered 2026-08-26 (medium): the placeholder bullet-required rule matches a bullet character rather than a list bullet, so *Placeholder* is flagged while **Placeholder** is not, and 3. Placeholder naming... is flagged; the italic/bold inconsistency is the tell that it matches punctuation rather than structure. The second half is the more important one — the recorded claim that TODO/FIXME/Replace with carry no repo-wide false-positive cost is measurably wrong. A scan of 5063 files returns 55 hits, 14 of them surviving purely on the optional-bullet rule, and nearly all plainly false: Mermaid state transitions in ticket-lifecycle.md, a count field in the roadmap-query skill, wrapped prose in four ACs. Marker distribution is todo 42, question 8, replace with 3, placeholder 2 — so the cost was measured for PLACEHOLDER alone and asserted for all six markers, and the tightening landed on the marker responsible for 2 hits while leaving the one responsible for 42 untouched. A prior round of the same work made the same shape of error, measuring a widening with a grep that shared the widening's blind spot. Both entries carry an explicit status line stating the code is not on main, since a register entry describing a file the reader cannot find is otherwise indistinguishable from a stale one."
breaking: false
---

## Entry

Both entries were produced by an independent code review of PR #495 and are recorded against
`main`'s register rather than the branch's, because `main`'s `KI-<COMP>-NNN` register is the
canonical one and the branch's parallel register is being discarded during reconciliation.

Each entry states in its `Status` line that the code is **not on `main`**. Without that, a
reader who greps for `_uniqueness_scanners.py` and finds nothing cannot tell a
not-yet-merged entry from a stale one describing a deleted file.

### What was confirmed working, and is recorded as such

Two things the same review checked and found sound, noted inside the entries so they are not
re-litigated:

- The document-end token `...` handling in `_uniqueness_scanners.py` is correct in all four
  shapes tested.
- The fail-closed commit disposition reaches the process exit code — verified by subprocess,
  not by reading. An earlier round of this PR had a fix that computed the right value and
  never consumed it; that regression did not recur.
