---
title: "The worktree tool now finds the repository it belongs to, not the one it happens to be standing in"
date: "2026-09-22"
time: "22:50"
type: manual
components:
  - build_orchestration
  - worktree_manager
summary: "Every copy of setup_ticket_worktree.py that build.py deploys was resolving the repository from its own file location, on an assumption its docstring stated as fact. In the dev layout the deployed copy aborted with a bare git exit status 128; in a consumer install the same call SUCCEEDED and silently returned the adopter's repository instead of leafcutter-ai. Both copies now resolve through an ordered candidate list, an explicitly-supplied anchor is authoritative and never falls through, and an unresolvable location is refused with every candidate named. Covers BO-4100d-4."
description: "Found 2026-09-22 when the fast lane refused four consecutive runs against BP-1500g-2. THE MECHANISM. _git_toplevel(anchor=None) defaulted to anchor = Path(__file__).resolve().parent, and its own docstring asserted the reason: 'the script always lives physically inside the repository it operates on.' That is true of the checked-out source copy and false of every copy build.py deploys. The source copy at leafcutter-ai/scripts/ therefore worked perfectly while the deployed copy at .leafcutter/scripts/ failed on identical code — location was the entire difference. TWO SYMPTOMS, AND THE QUIET ONE IS WORSE. In the dev/self-hosting layout the deployed copy sits in the untracked workspace parent, which is not a git repository at all, so git -C <that dir> rev-parse --show-toplevel exits 128 and the call raises. Loud, and therefore survivable. In a consumer install the deployed copy sits INSIDE the adopter's own git repository, so the identical call SUCCEEDS and returns the adopter's project — no exception, no warning, and the tool proceeds to create leafcutter-ai worktrees against the wrong repository. THE FIX. Both copies now try an ordered list of candidate anchors and take the first that resolves: the explicit anchor argument when a caller supplied one, then the process working directory, then the script's own directory as a last resort. An explicit anchor is AUTHORITATIVE and never falls through — when a caller names a subject that does not resolve, the call refuses rather than quietly resolving some other repository from the cwd, which would have re-admitted the same defect through the one door the rest of the change closes. Failure names every candidate tried and states that the copy appears to be deployed outside the repository it manages, replacing a bare 'exit status 128'. Deliberately NOT a plain cwd default: KI-BO-20260921-worktree-base-resolver-defaults-to-cwd is that exact shape in a sibling file, correct in a consumer layout and silently wrong in the dev one. BOTH COPIES CHANGED, NEITHER RESYNCED. templates/scripts/setup_ticket_worktree.py is what build.py deploys and what consumer installs receive; scripts/setup_ticket_worktree.py is the repo's working copy (ADR-001). The two have deliberately drifted — the template omits the create-time pre-commit gate — so only _git_toplevel and its docstring changed in each. KNOWN LIMITATION, recorded as KI-BP-20260922-0620 and verified empirically rather than assumed: in the dev layout NEITHER candidate is a repository, so the deployed copy now refuses clearly instead of crashing opaquely but still cannot create a worktree, and the fast lane remains blocked in this workspace. Closing that needs deploy-time provenance, which is KI-BP-011's subject — the build knows where it deployed from and does not record it where the deployed code can read it. A NOTE ON THE COMMIT SEQUENCE. The first commit (1dc5adfd) passed through a check-file-size autofix that compacted the function and, in compacting, deleted the sentence naming the actual condition — a requirement of the AC with a test asserting it — so that commit shipped the test red. Caught by re-running the suite after the autofix rather than trusting the commit report, and repaired in 6cc1a383 by restoring the sentence on the existing line, leaving the ratchet satisfied at 1428 and 1354 lines."
commits:
breaking: false
---

## Entry

`setup_ticket_worktree.py` decided which repository to operate on by asking
where its own file was. Its docstring said why:

> "the script always lives physically inside the repository it operates on"

True of the checked-out copy. False of every copy `build.py` deploys.

### The quiet half is the dangerous one

In the dev layout the deployed copy sits in the untracked workspace parent, so
resolution exits 128 and the tool stops. Loud, survivable.

In a **consumer install** the deployed copy sits inside the *adopter's* git
repository. The same call succeeds, returns their project, and the tool goes on
to create leafcutter-ai worktrees against the wrong repository — no exception,
no warning. That is why this is filed high rather than medium.

### What changed

Both copies resolve through an ordered candidate list — explicit anchor, then
process working directory, then the script's own directory — taking the first
that is a git repository. An explicit anchor is **authoritative**: when a
caller names a subject that does not resolve, the call refuses rather than
falling through to whatever repository the caller happened to be standing in.
Without that clause the fix would have re-admitted the same defect through its
own fallback chain.

A failure now names every candidate tried and says the copy appears to be
deployed outside the repository it manages.

This is deliberately *not* a plain cwd default —
`KI-BO-20260921-worktree-base-resolver-defaults-to-cwd` records that exact
shape in a sibling file, right in one layout and silently wrong in the other.

### What it does not fix

Verified by running the fixed template from a simulated deploy location rather
than assuming: in the dev layout neither candidate is a repository, so the
deployed copy now **refuses clearly instead of crashing opaquely** — but still
cannot create a worktree, and the fast lane stays blocked here. Closing that
needs deploy-time provenance (`KI-BP-011`). Recorded as
`KI-BP-20260922-0620`.

Covers `BO-4100d-4`.
