---
title: "KI-BO-20260921-worktree-base-resolver-defaults-to-cwd — build-feature calls the worktree-base resolver with no start path, so in the self-hosting layout it resolves against a directory outside the repository and every epic drive aborts"
description: "high — one call site omits the start argument that its sibling two lines above passes, so the resolver falls back to cwd; in the dev layout that cwd is the workspace parent, which is not a git repository, and the drive aborts before spawning any phase agent. RESOLVED 2026-09-30 by BO-4000f."
type: reference
category: reference
status: active
created: '2026-09-21'
last_updated: '2026-09-30'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260921-worktree-base-resolver-defaults-to-cwd — build-feature calls the worktree-base resolver with no start path, so in the self-hosting layout it resolves against a directory outside the repository and every epic drive aborts

> Index: [build-orchestration.md](../../build-orchestration.md).

- **Severity:** high. It stops every `/build-feature` run in the self-hosting layout before a single phase agent is spawned, and the abort message names the symptom rather than the cause.
- **Status:** **RESOLVED 2026-09-30** — fixed by AC `BO-4000f`; see the dated closure note at the foot of this entry.
  Original line, preserved: open — no AC. Root cause confirmed by reproducing the failing command by hand.
- **Occurrences:** 1 observed (2026-09-21, run `wf_7852a084-ae9`), but deterministic: it will fail this way on every dev-layout run.
- **First seen:** 2026-09-21 · **Last seen:** 2026-09-21
- **Where:** `templates/workflows-js/build-feature.js` line ~1423, and its deployed copy at `.leafcutter/workflows/build-feature.js`.

## Symptom

```json
{"status":"error","worktree_undetermined":true,
 "abort_reason":"worktree-base-unavailable",
 "message":"The repository's worktree base could not be established. No phase agent has been spawned."}
```

The workflow journal shows the first two steps succeeding and the third returning nulls:

```
resolve-target            -> {"target_type":"epic","worktree_path":"…/worktrees/EPIC-FilesStayWorkable", …}
worktree-facts-resolved   -> {"exists":true,"is_git_toplevel":true,"is_linked_worktree":true,"branch":"EPIC-FilesStayWorkable"}
worktree-base             -> {"main_checkout":null,"worktree_base":null,"layout":null}
```

## Mechanism

`worktree_base()` in `templates/scripts/worktree_repo_facts.py` has exactly ONE branch
that returns all-nulls:

```python
common_dir = _git_output(["rev-parse", "--path-format=absolute", "--git-common-dir"], start)
if common_dir is None:
    return {"main_checkout": None, "worktree_base": None, "layout": None}
```

`start` is a **positional argument defaulting to `"."`** (`base_p.add_argument("start", nargs="?", default=".")`).

The workflow's two adjacent call sites disagree about whether to supply it:

```js
1419:  …worktree_repo_facts.py facts "${resolveResult.worktree_path}"   // passes the path
1423:  …worktree_repo_facts.py base                                     // relies on cwd
```

So `base` resolves against the agent's working directory. In the self-hosting layout
that is the workspace parent, which is deliberately **not** a git repository —
`leafcutter-ai/` is the git root and its parent holds the build outputs:

```
$ git -C /home/henzeh/projects/leafcutter rev-parse --path-format=absolute --git-common-dir
fatal: not a git repository (or any of the parent directories): .git
```

Passing the path explicitly returns the right answer:

```
$ python .leafcutter/scripts/worktree_repo_facts.py base <worktree>
{"main_checkout": "…/leafcutter-ai", "worktree_base": "…/worktrees", "layout": "dev"}
```

## Why it was not caught

This is a **layout-conditional** bug. In a consumer install the repository root and the
working directory coincide, so `"."` resolves inside the repo and the default is
harmless. It fails only in the self-hosting layout, where the workspace parent sits
outside the repository — the same layout `ADR-001` establishes and that this package
develops itself in.

That is the recurring shape in this register and in `CLAUDE.md`: a default that is
correct in one layout and silently wrong in another, where the wrong answer is
indistinguishable from a legitimate "not applicable".

## Fix direction

Pass the already-computed path, exactly as the sibling call two lines above does:

```js
const base = await repoFactsCall(
  `python .leafcutter/scripts/worktree_repo_facts.py base "${resolveResult.worktree_path}"`,
  "worktree-base");
```

Worth considering alongside it: `start` defaulting to `"."` is the thing that let a
missing argument look like a working call. A required argument, or a default of the
repository root rather than the process cwd, would have made this a loud failure at the
call site instead of a null three steps later.

**Note on the workaround.** The deployed copy under `.leafcutter/workflows/` was patched
by hand on 2026-09-21 to unblock a drive. That copy is build output — the next
`build.py` overwrites it. The fix is only real once it lands in
`templates/workflows-js/build-feature.js`.

**Pattern:** two adjacent call sites into the same helper, one passing the path and one
relying on an implicit cwd default, in a layout where cwd is outside the repository.

---

## Closure — 2026-09-30

Resolved by AC `BO-4000f` in `templates/workflows-js/build-feature.js`, which is where
the Fix direction above said the fix had to land. The source now reads:

```js
1628:  const base = await repoFactsCall(
         `python {{config.output_root}}/scripts/worktree_repo_facts.py base "${repoAnchor}"`,
         "worktree-base");
```

The call no longer relies on the cwd default, and the file's own comment at `:1607`
states the mechanism this entry described — that these subcommands default to the
process cwd, "which for a phase agent is not a checkout at all, so an unanchored call
answers null about a perfectly healthy worktree and aborts the run (BO-4000f)."

Two points worth carrying forward rather than filing away:

**The fix is broader than the one call site.** `repoAnchor` (`:1608`) is computed once
and threaded through all four `worktree_repo_facts.py` calls — `facts`,
`base`, `facts` again for the instructed location, and `branch-standing`. The original
defect was two adjacent siblings disagreeing about whether to pass a path; the remedy
was not to patch the one that omitted it but to give every call in the group a single
shared anchor, so a future fifth call cannot reintroduce the disagreement by omission.

**The cwd default still exists, and deliberately so.** `repoAnchor` falls back to `"."`
when the resolved target is not an absolute path, classified by BO-3900's
`classifyPathForm` rather than by a leading-slash test — so drive-lettered and UNC
targets are correctly treated as absolute instead of silently taking the fallback. So
the "Worth considering alongside it" suggestion above — making `start` required, or
defaulting it to the repository root — was **not** adopted, and a relative target in the
self-hosting layout would still resolve against a non-repository cwd. That residual is
narrower than the original defect (it needs a relative target, where before every dev
drive failed) and is not currently known to occur, but it is the part of this entry that
the fix did not close. It is recorded here rather than as a new entry because nothing has
been observed failing that way.

Verified on `origin/main` at `da0b66c1` by reading the source, not the deployed copy —
per the note above, the deployed copy under `.leafcutter/workflows/` was hand-patched on
2026-09-21 and would have shown the fix whether or not it had landed in `templates/`.
