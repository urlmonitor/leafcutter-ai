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
- **Occurrences:** **19 refused commits across at least 5 worktrees**, 2026-09-28 to
  2026-09-30. Counted from the commit stderr logs in `~/tq600a1-backup/`: 19 distinct
  `git commit` invocations whose refusal names
  `output:   scripts/commit_guardian/commit_guardian.json`. Per worktree:
  `tq600a5` 6, `close-a5` 1, `ki-register` 1, and 11 across `tq600a-migration` and the
  two worktrees this entry originally recorded.
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-30
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

**Correction, 2026-09-30: it is not "the second commit" — it is every commit after
the first.** This entry's title and its original `Occurrences: 2` both read the defect
as firing once per worktree, and that understated it by an order of magnitude. The
`tq600a5` worktree is the clean measurement: **7 commits landed, 1 passed, and all 6
subsequent ones were refused** — at 09-29 13:21, 09-29 16:45, 09-30 08:59, 09-30 09:19,
09-30 09:36 and 09-30 11:01, each cleared by the one-line `config/` restore below and
then re-run. A 1:1 correspondence with no exceptions. The rewrite therefore happens on
**every** hook run, not only the first: the repair is not a one-off per worktree but a
step before every commit after the first, for the life of the worktree.

Two counting traps, both hit while recounting this:

- The hook name appears in every commit log, passing or failing. `grep -l "Check Output
  Drift"` matches ~all of them and proves nothing. Count the refusal message
  (`output file(s) were directly edited`) or the `…Failed` line.
- Not every `check-output-drift` failure is *this* defect. Two logs in the same corpus
  fail the same hook on gitignored `.claude/.cache/readme_markers/` GAP entries — a
  different issue entirely. Match on the named output path, not on the hook.

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
2. The advertised fix — re-run `build.py` — was, while this entry was being
   written, the command that stubbed the tracked `docs/INDEX.md`. That was
   KI-BP-016, and it is **now resolved** on main (BP-1500a-1, `c1bccb7e`,
   verified 2026-09-28: the self-host replay leaves `docs/INDEX.md`
   byte-identical at 252 lines with zero `No docs found.`). Both occurrences
   behind this entry predate that fix. What survives the fix is narrower but
   still real: on this workspace `build.py --force` is refused by the
   permission layer as irreversible local destruction, so an operator may be
   unable to run the remedy the gate prints, whatever the doc index now does.
   The per-file restore below does not depend on either.

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

**Do NOT restore from `templates/` instead — it looks equivalent and is not.**
The obvious-seeming `cp templates/scripts/commit_guardian/commit_guardian.json`
over the deployed copy trades this entry's drift for a second, quieter one. The
deployed artifact is not a byte copy of its template: `inject_config` resolves
`{{config.output_root}}` at deploy time, so the two differ by **150 lines** —
every `hooks_manifest[].entry` path. Restoring from the template reintroduces
150 unresolved `{{config.output_root}}` tokens, and `check-output-drift`
refuses again with the identical message naming the identical file, which reads
as "the workaround did not work" rather than "you restored the wrong content."

Only the `config/` copy is post-deploy content. That is the whole reason this
workaround names it.

Observed 2026-09-29 on `feature/tq600a-migration`: the template restore was
tried first, failed indistinguishably from the original symptom, and cost two
commit attempts before a full `build.py --force` re-run cleared it by
regenerating outputs and manifest together. A `build.py` re-run is therefore a
valid second remedy where the permission layer allows it (see the
irreversible-local-destruction caveat above) — but the one-line `config/`
restore above is cheaper and does not touch the doc index.

**A related detail that makes this harder to diagnose in a worktree.**
`<worktree>/scripts/commit_guardian` is a symlink to
`../.leafcutter/scripts/commit_guardian`, so the path `check-output-drift`
prints (`scripts/commit_guardian/commit_guardian.json`) and the path this
workaround writes (`.leafcutter/scripts/…`) are the same file. Reading one
before a repair and the other after can look like two copies disagreeing when
there is only ever one.

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
the artifact moved underneath it). KI-BP-016 (the `build.py` doc-index stub —
**resolved** by BP-1500a-1 on 2026-09-28, after the occurrences recorded here;
it no longer makes the advertised remedy unsafe, though the permission-layer
refusal noted above can still make it unavailable).

**Pattern:** a gate whose own enforcement run mutates the artifact it is
enforcing, so the guarantee holds only for a worktree's first commit and the
artifact must be repaired before every commit thereafter.
