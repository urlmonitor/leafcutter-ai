---
title: "KI-CG-20260928 — the first commit in a worktree rewrites the deployed `commit_guardian.json`, so the second commit fails `check-output-drift`"
description: "KI-CG-20260928 — the first commit in a worktree rewrites the deployed `commit_guardian.json`, so the second commit fails `check-output-drift`"
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - commit_guardian
  - build_pipeline
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260928 — the first commit in a worktree rewrites the deployed `commit_guardian.json`, so the second commit fails `check-output-drift`

- **Severity:** high
- **Status:** open
- **Occurrences:** 2 (two independent worktrees, same day)
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-28
- **Where:** `.leafcutter/scripts/commit_guardian/commit_guardian.json` (deployed
  output), `check_output_drift.py`, and whichever hook performs the rewrite —
  **not yet identified**

**Symptom.** A freshly bootstrapped worktree commits cleanly once. Every commit
after that in the same worktree is refused:

```
[check-output-drift] BLOCKED — output file(s) were directly edited instead of their source templates:
  output:   scripts/commit_guardian/commit_guardian.json
  template: templates/scripts/commit_guardian/commit_guardian.json
check-output-drift: RESULT verified=495 uncomparable=5 exempt=5 gaps=0 drifted=1 missing=0 unreadable=0
```

The ordering is the whole finding: `check-output-drift` **passes** on the first
commit and fails on the second. The worktree bootstrap is not what breaks it —
**the first commit is**. Something in that commit's own hook run rewrites the
deployed config, and the next run compares the rewritten file against a manifest
hash that no longer describes it.

**Evidence.** In a worktree created by `setup_ticket_worktree.py create-only`
at 10:50 and committed at 11:09, measured immediately after that commit
(hashes are sha256 over CRLF-normalised bytes, matching
`check_output_drift._sha256_of_file`):

```
manifest expects : e9b58e6eacd930b0f9c762a7f0a2e64a671b24024b76f5c9e9b7dda1f813d4d2
deployed actual  : dce619b70487f8bbc3bd5713a3e59442642713e9336e72894f7598ed609abf81
template actual  : 753ac36fd2417065e512030f0bb4b14bf1db78578f8e3a1bbaa5f811e10e1b42
```

Three distinct values. The rewrite is not a re-serialisation of the template:
the post-commit file contains **neither** the template's literal em-dashes
**nor** `—` escapes, so the em-dashes present in the pristine deployed copy
have been removed by something rather than re-encoded. The pristine deployed
copy does contain literal em-dashes, so this is loss, not normalisation toward
the template.

Reproduced independently in a second worktree the same day, with the same
`e9b58e6e` manifest expectation — the manifest hash is stable across worktrees,
which is what makes the post-commit divergence attributable to the commit.

**Why it is worse than one blocked commit.** Any workflow that commits twice in
one worktree — `quick-fix` (fix commit, then changelog commit), any drive that
follows a commit with a sign-off or changelog commit, `git commit --amend` —
hits the wall on its second step, with the first step already landed. The
failure names a file the author never touched, in a directory that is
gitignored, so the natural reading is "my tree is corrupt" rather than "the
previous commit did this".

**Two traps while diagnosing this.**

1. **The gate compares deployed against `.build_manifest.json`, not against the
   template**, despite the message naming the template. Making the deployed file
   byte-identical to its template does **not** clear the gate and moves the file
   further from the recorded hash. This was tried first and made things worse.
2. The advertised fix — re-run `build.py` — is the command that stubs the tracked
   `docs/INDEX.md` (KI-BP-016, live). On this workspace it is additionally denied
   by the permission layer as irreversible local destruction, so the documented
   remedy is not reliably available.

**Workaround that does not require `build.py`.** `build.py` deploys this config to
two locations. Only the `scripts/` copy is rewritten; the `config/` copy retains
the pristine content at exactly the hash the manifest records:

```bash
cp <worktree>/.leafcutter/config/commit_guardian/commit_guardian.json \
   <worktree>/.leafcutter/scripts/commit_guardian/commit_guardian.json
```

Verified to restore `deployed actual` to `e9b58e6e…`, after which the commit
proceeds with every gate passing and no `SKIP=`. This satisfies the gate's
invariant rather than bypassing it — the deployed artifact genuinely becomes the
content the manifest describes again.

**Remediation.**

1. Identify the hook that rewrites the deployed `commit_guardian.json` during a
   commit. Candidates to rule out first: any self-healing config hook, and any
   gate that reads then re-writes the config while normalising text. Whatever it
   is, a hook must not write to a manifest-tracked deploy artifact — that is the
   invariant `check-output-drift` exists to protect, and a gate breaking it is
   the same class of defect as a gate that cannot fail.
2. Until that lands, having `check-output-drift` name the manifest path and the
   recorded-vs-actual hashes in its refusal would have removed most of the
   diagnosis cost here. The current message points at the template, which is the
   wrong file to look at.

**Related.** KI-CG-20260831-manifest-shadowing (a different `check-build-drift`
defect: the wrong manifest is selected; here the right manifest is selected and
the artifact moved underneath it). KI-BP-016 (the `build.py` doc-index stub that
makes the advertised remedy unsafe).

**Pattern:** a gate whose own enforcement run mutates the artifact it is
enforcing, so the guarantee holds exactly once per worktree.
