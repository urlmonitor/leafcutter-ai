---
title: "KI-BP-011 — `.build_manifest.json` is written to the package that ran the build, not the target install it describes, so it is not portable to any consumer install"
description: "KI-BP-011 — `.build_manifest.json` is written to the package that ran the build, not the target install it describes, so it is not portable to any consumer install"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-011 — `.build_manifest.json` is written to the package that ran the build, not the target install it describes, so it is not portable to any consumer install

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — AC: BP-1500d
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_helpers.py:185` (manifest write target); `:83`, `:95-96`
  (`output_mappings` keying); `:193-195` (manifest key relativization)

**Second occurrence, 2026-08-25 — reached from a git worktree, and it blocked a commit.** A
phase agent ran `build.py --target-dir <worktree>` inside a worktree whose `.leafcutter` was a
symlink to the workspace parent's, per the bootstrap `CLAUDE.md` recommends. Two things
followed. The deploy went *through* the symlink into the parent's `.leafcutter`, and the
manifest written carried **no `output_mappings` at all** — the target sits under
`.../worktrees/`, which is not a subpath of the package, so the same `UserWarning` this entry
already documents fired and the mapping was silently dropped.

The consequence was not theoretical. On the next commit, `check-build-drift` read that manifest
and reported **every template in the repository** as unregistered:

```text
UNCOMPARABLE: GAP templates/agents/README.md action=run build.py to register it
UNCOMPARABLE: GAP templates/agents/ac-validator.md action=run build.py to register it
... (one line per template)
```

The commit contained no template change whatsoever — only a changelog entry and two AC YAML
files. Recovery was to re-run the canonical `build.py --target-dir .` from the workspace parent,
which regenerates a manifest that does have `output_mappings`.

**What this adds to the entry.** The original framing is about portability to a *consumer*
install. This shows the same defect reached from the package's own recommended worktree
workflow, where it is not merely unportable but actively corrupting: a worktree-targeted build
overwrites the shared parent manifest with one that no gate can use. Any fix should treat
"target is a worktree of this repo" as a first-class case, not an exotic one — `/feature`,
`worktree-agent` and `building-epics` all create worktrees by design.

**SYMPTOM CORRECTED 2026-09-07 — THE WRITE-TARGET CLAIM BELOW IS NO LONGER TRUE, AND THIS
ENTRY NEEDS RE-SCOPING BY ITS OWNER.** `BP-1500d-1` and `BP-1500d-3` — the ACs this entry
is filed against, via their parent `BP-1500d` — both landed on 2026-09-07 (merged in #715
and #689) and closed most of what this entry documents. Read against current source on the
same date:

- The record's own directory is resolved from the **target** whenever a target is supplied,
  falling back to the package only in the no-target call shape. It is therefore the target
  by default, not "always the package's own directory, never `--target-dir`".
- A real build invoked through the ordinary command line into a receiving project that is a
  **sibling** of the producing package, under a system temp root, wrote the record into the
  **receiving** project — the case the Symptom paragraph says produces no manifest at all.
- The output-mapping keys are computed against the target as their base, not against
  `package_root.parent`, so the anchor this entry names as the single common cause of all
  its symptoms is gone.
- The fail-open half is closed for the trigger that remains reachable: the record-writing
  step now returns its failure to the build's exit path, which reports it naming the record
  and the target project and then exits non-zero.

Every line number cited in the **Where** field and in the paragraphs below predates that
work and no longer locates what it names — the surviving broad handler sits roughly a
thousand lines from the line this entry cites for it.

**What is still true, and is the only part of this entry that should be relied on:** the
SHAPE — a record computation that gives up, an empty record written anyway, and a
per-artifact success line printed for that record before any failure is reported. A reader
who stops at the build's first statement about the record is still told it was written.
`KI-BP-008` is the same fail-open shape and is unaffected by any of the above.

Two further findings from the same 2026-09-07 pass, neither closed: the account of the
**producing** package (where it stood, and which of its own files the deployment came from)
is still position-relative and is `BP-1500d-1-i`, still open; and a record entry can now be
keyed to the receiving project's root and **still point outside it**, when a managed file's
destination is reached by a parent step — exit 0, a full record, an empty failure field.
That is a record that is produced and untruthful rather than one that could not be
produced, and it is `BP-1500d-1-ii`, authored 2026-09-07.

**Status line, for the owner:** this entry still reads `open — AC: BP-1500d`. A large part
of what it documents has been fixed underneath it, so it wants either closing against the
two merged ACs with the residue re-filed, or amending down to the surviving shape.

The original text is kept verbatim below, as the 2026-08-25 observation it was.

**Symptom (as observed 2026-08-25 — see the correction above before acting on any of it).**
The build's own record of what it wrote is not written to the install it
describes. `scripts/build_helpers.py:185` computes
`manifest_path = package_root / ".build_manifest.json"` — always the package's own
directory, never `--target-dir`. Running `python3 scripts/build.py --target-dir
/tmp/lc_probe2` printed `build manifest (61 template + 0 output_mappings entries) ->
/home/henzeh/projects/leafcutter/worktrees/bp900-deploy/.build_manifest.json`, and
`/tmp/lc_probe2` — the actual target — contained no manifest at all. Consequence:
`check_output_drift.py` and `check_build_drift.py`, which both read this file to detect
drift, have nothing to read in a consumer install. Both guardrails are **absent**, not
degraded, in that install.

**Evidence — a consumer build overwrites the package's own baseline, violating
BP-1500a.** Because the write target is always the package, building into another
project rewrites the package's own manifest with data about that OTHER build. Verified
immediately after the run above: the package's own `.build_manifest.json` then reported
`output_mappings: 0, templates: 0`. It is gitignored, so the corruption is invisible —
nothing shows in `git status`. BP-1500a is the existing acceptance criterion that "a
build leaves the repository it is run from exactly as it found it"; this is a live
violation of that guarantee, not a newly discovered one.

**Evidence — `output_mappings` cannot be computed for a foreign target, and the build
fails open.** `scripts/build_helpers.py` lines 83 and 95-96 key entries via
`output_path.relative_to(package_root.parent)`, which raises `ValueError` whenever the
target sits outside that parent — true of essentially any real consumer install.
Observed:

```text
[WARNING] could not compute output_mappings: '/tmp/lc_probe2/agents/README.md' is not
in the subpath of '/home/henzeh/projects/leafcutter/worktrees'. Direction B detection
will be unavailable until next build.
```

The build then reports success and exits 0 — it fails open, exactly the shape this file
already documents in KI-BP-008.

**Evidence — manifest keys carry a non-portable prefix.** Lines 193-195 key by the same
`relative_to(package_root.parent)`, so keys read `leafcutter-ai/templates/agents/x.md`
from the canonical checkout but `bp900-deploy/templates/agents/x.md` from a worktree
named `bp900-deploy`. Observed directly in this worktree's own manifest: every top-level
key is prefixed `bp900-deploy/templates/agents/...`, and the `templates` count reads 0
because the reader looks for a `templates` key in a shape the writer never produced in
this layout.

**Root cause.** All four symptoms above trace to one assumption: every path is resolved
relative to `package_root.parent`. That holds only inside this repo's own self-hosted
workspace layout (a `leafcutter/` workspace parent containing `leafcutter-ai/`) — it
breaks for any real consumer install, where the target sits outside that parent
entirely, and for any worktree not laid out identically to the canonical checkout.

**Why this matters — BP-1500c has no record to check.** BP-1500c ("report drift against
the record of what a build wrote") has this defect as a hard prerequisite: you cannot
report drift against a manifest that was never written to the install being checked.
Same failure family, one layer deeper, as BP-016 / BP-017.

**Fix direction.** Anchor the manifest write target, and every path computed relative to
it, to something that holds for an arbitrary consumer install — e.g. write
`.build_manifest.json` into the actual `--target-dir`, and key/relativize entries
against that target root (or the package root itself) rather than
`package_root.parent`.

**AC.** BP-1500d
(`docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500d.yaml`) is
authored against this defect.

---
