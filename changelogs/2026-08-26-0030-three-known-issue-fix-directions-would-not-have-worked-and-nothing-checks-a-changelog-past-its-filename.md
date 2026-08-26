---
title: "Three known-issue fix directions would not have worked, and nothing checks a changelog past its filename"
date: "2026-08-26"
time: 0030
type: manual
components: 
  - build_pipeline
  - build_orchestration
summary: "Review notes on three known issues whose recorded remedies were wrong or self-contradictory, a CLAUDE.md step that told readers to run a command a same-day high-severity issue documents as destructive, and a new issue recording that no gate reads a changelog entry past its existence."
description: "Appends dated review notes to KI-BP-016, KI-BP-017 and KI-BO-026 rather than rewriting them, so the original reasoning stays readable next to the correction. KI-BP-016: the primary fix direction would have reproduced the bug, because every _CATEGORIES entry already carries the docs/ prefix, so passing a docs root makes the generator scan root/docs/docs and render the same empty stub; two coherent alternatives are set out and the refuse-on-empty-scan guard is called out as the part worth landing first. KI-BP-017: the KI-FC-001 prerequisite was attached only to fix (b), but _find_project_root resolves __file__ through symlinks, so fix (a) reaches the same install-tree sink; the note also records that the symlink now exists in the GE-120 worktree, which makes the original crash unreproducible there. KI-BO-026: the fix direction claims the comparison already has both inputs and then instructs the reader to capture one of them, so the note marks the second half as the true one and flags the missing-snapshot case as a design decision to settle rather than inherit. CLAUDE.md: the feedback_categories.yaml remedy told readers to run build.py --target-dir workspace-root, which KI-BP-016 documents as silently overwriting the tracked docs index; replaced with the symlink route plus the symlink caveat. Adds KI-BP-021 recording that CI checks only that a changelog file was added, no pre-commit hook reads one, and emit_entry.py writes a bare ## Entry placeholder by construction, so the sanctioned tool produces exactly the artefact no gate rejects."
breaking: false
---

## Entry

A code review of the six defects filed from the GE-120 epic drive found the *evidence* in
those entries unusually solid — every line citation checked out against source — and the
*remedies* unreliable. Three of them would not have worked. The notes below are appended to
each entry rather than replacing it, so whoever picks the work up sees the original reasoning
next to the correction and can judge both.

**KI-BP-016 — the recommended fix reproduces the bug.** The entry says `generate_index` should
be handed `target_root / docs_dir`. But all nine `_CATEGORIES` entries already carry a `docs/`
prefix, so a root ending in `docs/` makes the generator scan `<root>/docs/docs/...`, find
nothing, and write the identical nine-section `No docs found.` stub — indistinguishable from
no fix at all, and with every rendered link broken as well. Two coherent alternatives are
written out. The entry's *second* suggestion, refusing to overwrite a populated index from an
all-empty scan, is correct, independent, and the one worth landing first: it converts a silent
175-line deletion into a loud failure, and it cannot be got subtly wrong.

**KI-BP-017 — the prerequisite was attached to the wrong half.** The entry warns that fix (b)
must land together with the KI-FC-001 sink fix, implying (a) is safe alone. It is not:
`_find_project_root()` resolves `__file__` through symlinks, so the symlink that fix (a)
creates lands the walk-up in the install tree and routes feedback to the install tree's sink —
the same destination as (b). KI-FC-001 gates both. The note also records that the symlink now
exists in the GE-120 worktree, so the original crash is no longer reproducible there; anyone
retrying will silently exercise the sink-split path instead and should check for the symlink
before drawing conclusions.

**KI-BO-026 — the fix direction contradicts itself.** "The comparison already has both inputs
needed" is followed two sentences later by an instruction to capture one of them. The second
is true: no plan-time folder snapshot exists anywhere in the data flow, so the optimistic
reading sends the reader hunting for a value that was never recorded. The rest of the entry —
the distinction between never-selected and added-mid-drive, and the observation that its remedy
sentence is right by accident — is sound and left intact.

**CLAUDE.md pointed at a destructive command.** The `feedback_categories.yaml` remedy told
readers to run `build.py --target-dir <workspace-root>` — the exact invocation KI-BP-016, filed
the same day at severity high, documents as silently overwriting the tracked `docs/INDEX.md`.
Replaced with the symlink route, a `git status` warning for anyone who runs the build anyway,
and the caveat that a symlinked `scripts/feedback` moves the feedback sink into the install
tree.

**KI-BP-021 is new, and answers a question worth asking of any gate: what does it actually
read?** For changelog entries the answer is almost nothing. CI's blocking `changelog-presence`
job checks only that a file was *added* under `changelogs/` — it never opens it. No pre-commit
hook looks at changelogs at all; the single mention in commit-guardian config is an
*exclusion*. The one real validator, `emit_entry.py`, checks the payload before the file exists
and then writes `frontmatter + "\n## Entry\n"` — an empty body by construction. So the
sanctioned tool's default output is precisely the artefact no gate rejects, which is how an
entry with its whole narrative crammed into a one-line YAML field passed everything. That
matters more than it sounds, because `release.yml` computes the next SemVer from these files.
