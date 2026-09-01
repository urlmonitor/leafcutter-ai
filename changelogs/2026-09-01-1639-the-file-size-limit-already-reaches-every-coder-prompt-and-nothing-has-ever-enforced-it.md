---
title: "The file-size limit already reaches every coder prompt, and nothing has ever enforced it"
date: "2026-09-01"
time: "16:39"
type: manual
components: 
  - ac_store
  - commit_guardian
summary: "New acceptance criteria give the long-standing goal of keeping source files a workable size an actual owner, and design the one mechanism that lets that limit be switched on without instantly failing the two hundred files already over it — no code changed yet, so nothing is enforced today."
description: "Commit 7c014f693 (16 files, +4671/-64) adds a new GE-127 AC tree to guardrail-engine — L0 plus five L1s (GE-127a..e) and seven enriched L2/L3 records — and amends BO-210a-2 and BP-100n-4. Acceptance criteria only: no hook is registered, no gate runs, and check_file_size.py remains invoked by nothing."
pr: 688
commits: 
  - 7c014f693fb9851b5ead4a119b7ae9aa70d07ae2
---

## Entry

A 400-line `.py` limit already exists and already reaches every `python-coder` invocation as a prompt instruction — one that names an enforcement hook, `check_file_size.py`, that has never run. 200 of 845 tracked `.py` files exceed it today. A review of 725 L0/L1 records in the `guardrail-engine` component found none that owned this outcome, and four separate AC trees already *detect* that the hook is invoked by nothing without any of them committing to turning it on.

This commit closes that blank. It adds a new `GE-127` L0 — *"The codebase stays a size a person can still work in"* — with five L1 children (`GE-127a`..`e`) and seven enriched L2/L3 records underneath them. It is acceptance criteria only: no hook is registered, no gate runs, and no behaviour changes. That is deliberate — the point of this drive was to make turning the gate on possible, not to turn it on.

### The ratchet is what makes registering the gate possible at all

The obvious way to enforce a size limit — reject anything over it — cannot ship today: 200 existing files are already over, and blocking every commit that touches any of them would freeze real work. `GE-127b-1` specifies a ratchet instead: a file already over the limit may not grow *further*, but is not blocked merely for being over. The previous length is read from the file's own `HEAD` blob (`git show HEAD:<path>`), measured with the same length function applied to the staged content — so no baseline is persisted anywhere, and no baseline can go stale or drift out of sync with the tree. That single design choice is what turns "200 files already violate this" from a blocker into a non-issue.

### Extension coverage pinned from the measured distribution

`GE-127c-1` pins per-extension limits at enrichment time rather than leaving them to be guessed later: `.js`/`.mjs` at 1000 lines, `.ts`/`.tsx`/`.sh` at 400 (all three new), `.py` at 400 and `.sql` at 600 (both unchanged from the existing convention). `.md` is explicitly out of scope, since `check-doc-length` already covers `docs/*.md`.

### Two existing ACs amended, not just referenced

- **`BO-210a-2`** gets a closing clause: every id listed on `blocking_hook_ids` must be *reached* at commit time, not merely enumerated. Three of its seven currently are not — the amendment names that gap as approved-but-unreached rather than leaving it implied. It also closes a pre-existing gap where the record sat at `readiness: approved` as a code AC with no test contract at all, invisible until staged because these hooks validate the index rather than the store; only the `test_spec` contract is added here, not the tests themselves.
- **`BP-100n-4`** has four stale hard-coded population counts removed from its criteria, its disk-population rule resolved as a recursive path-keyed listing (not a bare-filename match), and an `it_requirement` corrected that would otherwise have reported a registered, required gate as invoked by nothing.

Both amended records were demoted to `draft` by their authoring pass (criteria changed) and restored to `approved` by BrainCandy the same day, judging the changes corrections to already-approved intent rather than new scope — recorded in each record's `amended_by`.

### What was deliberately not done

No hook was written, registered, or wired into `blocking_hook_ids`. `check_file_size.py` is exactly as unreached after this commit as before it. The 200 files already over the 400-line `.py` limit are unaffected — the ratchet has nothing to enforce until the gate itself is built and turned on in a later, separate change.
