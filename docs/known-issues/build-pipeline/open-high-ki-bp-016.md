---
title: "KI-BP-016 — `build.py` honours `docs_root` when writing the doc index but ignores it when reading, and overwrites the real index with \"No docs found.\""
description: "KI-BP-016 — `build.py` honours `docs_root` when writing the doc index but ignores it when reading, and overwrites the real index with \"No docs found.\""
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

# KI-BP-016 — `build.py` honours `docs_root` when writing the doc index but ignores it when reading, and overwrites the real index with "No docs found."

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **RE-VERIFIED 2026-08-25 — LIVE. Absorbs KI-BP-001, which is the same defect.**
> Reproduced with the exact command CLAUDE.md documents (`--target-dir .` from the workspace
> parent, with the real `skills_config.json` and its `docs_root: "leafcutter-ai/docs/"`):
> `docs/INDEX.md` went from 221 lines with zero `"No docs found"` to 57 lines with nine, and
> the build printed `✓ wrote leafcutter-ai/docs/INDEX.md` and exited 0. Isolating
> `generate_doc_index.py` reproduced the numbers exactly: repo root → 221 lines / 0 stubs,
> workspace root → 57 lines / 9 stubs.
>
> Root cause confirmed in `build_doc_index` — `output_path` is built from
> `target_root / config["docs_root"]` while `content` comes from `generate_index(target_root)`.
> Write honours `docs_root`; read ignores it.
>
> One precision on "every run": the *second* consecutive build is a no-op, because the stub it
> wrote now matches what it reads. It destroys the index every time the index is in its
> correct state — i.e. immediately after every `git checkout -- docs/INDEX.md`, which is
> exactly the loop that made it look like "every run".
>
> **The build does not merely fail to reveal this — it reports it as a green success**, on a
> tracked file that CLAUDE.md points agents at, in a form trivially committed by accident.
>
> **Occurrence 2 — 2026-09-01, still live at `931b4beb4`.** Hit again during a routine
> pre-drive `build.py` sync, which is the context this defect will keep appearing in: the
> standing instruction is to rebuild before every drive, so every drive re-arms it. Numbers
> this time: 178 table rows deleted, 0 added, all nine sections `No docs found.`, sole
> working-tree modification on an otherwise clean tree, build exit 0.
>
> The line citations above had drifted by ~350 lines and would have sent a fixer to the
> wrong function; they are replaced with symbol names, which do not rot. The phase function
> is `build_doc_index`, registered in the phase list as `("Doc index", build_doc_index)`.

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-09-01
- **Where:** `scripts/build.py` — `build_doc_index` (the `("Doc index", build_doc_index)`
  phase entry); `scripts/generate_doc_index.py` (`generate_index`, and its `No docs found.`
  emitter)

**Symptom.** Running the documented self-hosting build

```
python3 scripts/build.py --target-dir /home/henzeh/projects/leafcutter --force-breaking
```

rewrote `leafcutter-ai/docs/INDEX.md` from a populated 221-line index to a 57-line stub whose
every section reads `No docs found.` — **172 table rows deleted**, all nine categories emptied.
The build printed `wrote leafcutter-ai/docs/INDEX.md` and exited 0.

**Root cause — the read root and the write root are computed differently.** In the build phase:

```python
docs_dir = config.get("docs_root", "docs/").rstrip("/")   # "leafcutter-ai/docs"
output_path = target_root / docs_dir / "INDEX.md"          # <ws>/leafcutter-ai/docs/INDEX.md
content = generate_index(target_root)                      # scans <ws>/docs/
```

The **write** path applies `docs_root` from `skills_config.json`, which in this workspace is
`"leafcutter-ai/docs/"` — so it correctly targets the repo's index. The **read** path passes
`target_root` straight to `generate_index`, which hardcodes `<root>/docs` and never consults
`docs_root`. In the self-hosting layout `<workspace>/docs/` is a five-entry deployed stub
(`INDEX.md`, `how-to/`, `product-truth/`, `reference/`, `ui-context.md`), not the repo's docs
tree. So the generator scans the stub, finds nothing in nine of its categories, and the result
is written over the index of a tree it never looked at.

**Reproduced directly**, which isolates it from the rest of the build:

```text
$ generate_doc_index.py --repo-root .../leafcutter-ai       --output /tmp/idx_repo.md
$ generate_doc_index.py --repo-root .../leafcutter          --output /tmp/idx_workspace.md
$ grep -c "No docs found" /tmp/idx_repo.md /tmp/idx_workspace.md
/tmp/idx_repo.md:0
/tmp/idx_workspace.md:9
$ wc -l /tmp/idx_repo.md /tmp/idx_workspace.md
221 /tmp/idx_repo.md
 57 /tmp/idx_workspace.md
```

The 9-section stub is exactly what landed in the repo.

**Why this is worse than a stale artifact.** `No docs found.` is not an error state the
generator reports — it is the ordinary rendering of an empty category, so an empty scan and a
genuinely empty docs tree are indistinguishable in the output and in the exit code. The
destination file is tracked, so the damage is a committable 172-row deletion of the index that
CLAUDE.md points agents at for doc discovery. It was noticed here only because `git status`
was checked immediately after the build; a build run as part of a larger flow would have
carried it into the next commit.

Correcting an earlier misattribution: a dirty `docs/INDEX.md` observed in this workspace on
2026-08-25 was initially blamed on a concurrent agent. It was this build phase.

**Fix direction.** Pass the resolved docs root into the generator rather than the target root —
`generate_index` should take the same `target_root / docs_dir` the writer uses, or accept
`docs_root` and apply it. Independently, the generator should refuse to overwrite a non-empty
index with an all-empty scan: a run that resolves zero documents in every category has almost
certainly resolved the wrong directory, and should exit non-zero saying which directory it
scanned rather than rendering the emptiness as content.

> **Review note, 2026-08-26 — the first half of that fix direction is wrong as written; the
> second half is the one to build.**
>
> "`generate_index` should take the same `target_root / docs_dir`" would reproduce this exact
> bug rather than fix it. Every entry in `_CATEGORIES` (`generate_doc_index.py:64-74`) already
> carries the `docs/` prefix — `("Components", "docs/architecture/components", True)`,
> `("How-To Guides", "docs/how-to", True)`, and so on for all nine. Hand the generator a root
> that already ends in `docs/` and it scans `<root>/docs/docs/architecture/components`, which
> exists nowhere, so every category comes back empty and it writes the identical nine-section
> `No docs found.` stub. The failure would look like no fix had been applied at all. It would
> also break every link the index renders, since those are built from the same prefixed paths.
>
> Whoever picks this up has to choose one of two coherent shapes, not mix them:
>
> 1. **Keep `_CATEGORIES` prefixed and pass the repo root.** The generator's contract stays
>    "give me the root that *contains* `docs/`". The build phase's bug is then simply that it
>    passes `target_root` where it should pass the root implied by `docs_root` — strip the
>    trailing `docs/` from `docs_root` and pass that. Smallest change; the generator is
>    untouched.
> 2. **Strip the `docs/` prefix from all nine `_CATEGORIES` entries and pass the docs root.**
>    Then `target_root / docs_dir` is correct. But this changes the generator's contract and
>    every rendered link path, so the link-rendering code has to be audited in the same commit.
>
> Option 1 is smaller and safer, and it is the one that matches how the generator already
> behaves when invoked directly — the reproduction recorded in this entry passes
> `--repo-root .../leafcutter-ai`, a root *containing* `docs/` rather than a docs root, and
> gets a correct 221-line index. That invocation is the working contract; the build phase is
> what disagrees with it.
>
> The refuse-to-overwrite-on-an-all-empty-scan guard is independently correct and worth landing
> on its own, ahead of either option. It is the part that turns this from a silent 175-line
> deletion into a loud failure, and unlike the path fix it cannot itself be got subtly wrong.

**Pattern:** a resolver that reads one tree and writes another, with the failure rendering as
ordinary output.

---
