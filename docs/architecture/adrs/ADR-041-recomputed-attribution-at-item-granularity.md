---
title: "ADR-041: Ownership in an Installed Tree Is Decided by Recomputed Attribution at Item Granularity"
description: "The build decides what it may remove by positively attributing each path to itself from data it recomputes on that run, at item rather than container granularity, and refuses when its removal set and its claim set disagree. Maintained path lists cannot express ownership of a tree the package shares with its adopter."
type: "adr"
status: "active"
created: "2026-09-08"
last_updated: "2026-09-08"
deciders:
  - BrainCandy
components:
  - build_pipeline
  - infrastructure
related_docs:
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/adrs/ADR-004-consolidated-output-root.md
  - docs/known-issues/build-pipeline.md
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-i.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-ii.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-2.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-3.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500b-4.yaml
related_code:
  - scripts/build.py
  - scripts/build_helpers.py
  - scripts/build_phases.py
---

# ADR-041: Ownership in an Installed Tree Is Decided by Recomputed Attribution at Item Granularity

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-08 |
| Deciders | BrainCandy |
| Author | Recorded during the BP-1500g ownership-boundary pass of 2026-09-08 |
| Supersedes | None |
| Context ADRs | [ADR-001](ADR-001-self-hosting-boundary.md) establishes the shared occupancy this decision governs; [ADR-004](ADR-004-consolidated-output-root.md) introduced the shim layer whose link-ness is rejected here as an ownership signal. Neither is superseded. |
| Specification served | [`BP-1500g`](../../acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g.yaml) and its children `BP-1500g-1`, `BP-1500g-1-i`, `BP-1500g-1-ii`, `BP-1500g-2`, `BP-1500g-3` |

## Context

[ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) drew the line between
package source and build output, and in doing so accepted that build outputs land at the
project root "since that's where Claude Code expects them". That acceptance is what produces
**shared occupancy**: the installed tree is simultaneously the package's output tree and the
adopter's own project. ADR-001 named the boundary; it did not give the build a way to *decide*
which side of that boundary any given path falls on at run time. This ADR supplies that
decision procedure. It does not amend ADR-001 and does not move the boundary — it makes the
boundary computable.

The cost of not deciding is already being paid, and it is not hypothetical. An ordinary
no-flag `python scripts/build.py` destroys adopter content today. That is
**[KI-BP-009](../../known-issues/build-pipeline.md)** (severity high, status open), whose
`RE-VERIFIED 2026-08-25` block records the empirical run: an adopter replaced the
`.claude/skills` shim with a real directory holding their own skills, ran a build with no
flags, and got `✓ removed stale: .claude/skills` followed by
`shim: .claude/skills -> skills (symlink)`. Their work was gone, and the run reported success.
The identical shape has since been recorded one path over for a *file* rather than a
directory, in `KI-BP-20260907-0722`, where a consumer's repo-root `.pre-commit-config.yaml`
carrying project-local hooks is removed and re-shimmed with the same green checkmark. A fix
addressing only the directory case leaves the file case live.

### What the code actually does

Five readers act on the same information, and they do not agree.

1. **`_cleanup_stale_paths` in `scripts/build.py`** iterates the fixed constant
   `_PRE_CONSOLIDATION_PATHS` (11 entries). Its **only** ownership test is: if the path is a
   symlink whose resolved target starts with the output root, keep it; otherwise `unlink()` or
   `shutil.rmtree()` it. The polarity is inverted with respect to the adopter's interest. A
   *symlink into the output root* means "ours, keep"; a **real directory means "stale,
   destroy"**. The adopter's natural workaround — replace the shim with a real directory
   holding their own work — is precisely the shape that triggers the deletion.

2. **This runs unconditionally on the default path.** `_cleanup_stale_paths` is called from
   the main build flow with no flag guarding it, immediately before the shim-install step. The
   reproduction in KI-BP-009 used no flags at all.

3. **`install_shims` in `scripts/build_helpers.py` is, by contrast, polite.** When its `force`
   argument is false it records `"skipped (exists)"` and leaves the path alone. `install_shims`
   *alone* would destroy nothing. **The harm is the pair**: cleanup removes the adopter's
   directory, and the shim install then fills the vacancy it created. Neither function is
   informative read alone, which is why the defect survived months of successful builds in the
   reporting repository.

   **But that politeness is a property of the call site, not of the function.**
   `install_shims`' signature is `force: bool = True` — the *default is destructive*. It
   behaves politely only because `build.py`'s single call site passes
   `force=effective_force`, itself derived from `--no-overwrite`. Any new caller that takes
   the default overwrites whatever occupies the canonical path. An implementer reading point 3
   as "install_shims is safe" would be reading a fact about one caller as a fact about the
   function.

4. **Three independently-maintained tables disagree about who owns the same paths — not two.**

   | Table | Location | Entries | Role |
   |---|---|---|---|
   | `_PRE_CONSOLIDATION_PATHS` | `scripts/build.py`, module constant | 11 | the removal set |
   | `shim_map` | `scripts/build_helpers.py`, module level | 9 | the directory claim set |
   | `file_shims` | `scripts/build_helpers.py`, **local variable inside `install_shims`** | 2 | the file claim set |

   `file_shims` holds `.pre-commit-config.yaml` and `.claude/settings.json`. Because it is a
   function-local variable it is **not importable**, so it cannot be reconciled against
   anything and cannot be tested against anything. Ten of the eleven removal-list entries are
   claimed by one of the two claim tables; only `scripts/sync_platforms` is genuinely
   removal-only. `.claude/workflows` is claimed by `shim_map` but absent from the removal list
   — **safe by omission, not by design**. Nothing in the test suite asserts any relationship
   between these tables.

5. **A fifth reader prints the same list as advice.** `_run_migration_report` in
   `scripts/build.py` iterates the same constant and prints `rm -rf <path>` to the adopter. It
   deletes nothing. It is therefore the surviving artefact if the other four points are
   repaired and it is not.

### The capability the fix needs already exists, fenced off

`_build_source_manifests` in `scripts/build.py` **already** computes, from the template
directories, the set of artifacts a build pass would produce — recomputed per run, not
maintained. It is reachable only from `clean_stale_artifacts` (`scripts/build_phases.py`),
which is gated behind `if args.clean:`, a `store_true` flag defaulting to false. The
recomputed-derivation capability this decision requires is present in the codebase and unused
on the path where the damage happens.

This ADR serves [`BP-1500g`](../../acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g.yaml)
("Your own work in your own project survives every build") and its children
[`BP-1500g-1`](../../acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1.yaml),
[`BP-1500g-1-i`](../../acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-i.yaml),
[`BP-1500g-1-ii`](../../acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-ii.yaml),
[`BP-1500g-2`](../../acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-2.yaml)
and [`BP-1500g-3`](../../acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-3.yaml).
Their criteria are not restated here; this record fixes the mechanism those criteria are
satisfied by.

## Decision

### 1. Attribution is recomputed, not listed

Before any removal, the build MUST positively attribute the path to itself from data it
**recomputes on that run** — the current template set plus its own provenance record. Every
path considered for removal MUST resolve to exactly one of three verdicts:

| Verdict | Meaning | Permitted action |
|---|---|---|
| `package_produced` | the current run's own recomputed derivation accounts for this item | MAY be replaced or removed |
| `adopter_owned` | positively attributed to the adopter | MUST NOT be removed, emptied, or overwritten |
| `unattributable` | attribution did not resolve | MUST be kept; MAY be reported; MUST NOT be removed |

**Non-attribution means keep.** The build MUST NOT remove anything it cannot positively
attribute to itself.

This replaces `is_symlink() and resolves into output_root` as the ownership signal. That
signal is not merely weak — it is **meaningless under `shim_strategy: copy`**, where a
package-produced item is a real file and not a link at all, so the very test that is supposed
to identify package output identifies none of it.

### 2. Item granularity, never container granularity

A **co-claimed container** — a path claimed by both the removal set and a claim set, such as
`.claude/skills`, `.claude/agents`, `.claude/commands`, `.claude/hooks`, `.gemini`,
`scripts/commit_guardian`, `scripts/doc_compliance`, `scripts/feedback` — MUST NOT be removed
wholesale. Only individually-attributed items **inside** it MUST be removed, each on its own
§1 verdict. The container itself is never the unit of removal.

This is what gives adopter-authored content a location that is **both** discoverable by the
consuming tool **and** safe from the build — the two properties KI-BP-009 shows an adopter
currently cannot have simultaneously. It is KI-BP-009's own fix direction, generalised beyond
skills to every co-claimed container.

### 3. Removal and claim are reconciled every run, and disagreement fails loudly

A path that is simultaneously scheduled for removal **and** scheduled to be claimed is a
contradiction the build can detect from its own data, at the cost of one set intersection,
without knowing anything about the adopter. The build MUST perform that reconciliation on
every run, MUST surface any such contradiction, and MUST refuse rather than resolve it
silently.

The claim set MUST be assembled from **all three** tables named in Context §4. This requires
promoting `file_shims` from a function-local variable inside `install_shims` to module scope
in `scripts/build_helpers.py`, so that it is importable, reconcilable, and testable.

A developer keeping the three tables in step by hand MUST NOT be treated as the enforcement
point. It is the absence of one, and it is the state that produced this defect.

### 4. The printed advice is bound by the same verdict

`_run_migration_report` in `scripts/build.py` MUST NOT name an `adopter_owned` or
`unattributable` path in its printed `rm -rf` / `rm` advice. It MUST derive what it names from
the same §1 attribution the removal path uses.

## Consequences

### Positive

- **The default path stops destroying adopter content**, which is the whole of BP-1500g's
  plain-language promise and the open state of KI-BP-009.
- **Adopter content gains a home that is both discoverable and safe.** Under §2 an adopter can
  place their own skill inside `.claude/skills` — the only directory Claude Code discovers
  project skills from — without the container being the unit of removal.
- **A whole class of defect becomes mechanically detectable.** §3's intersection catches the
  removal/claim contradiction for paths nobody has thought about yet, including ones added
  after the check was written.
- **`.claude/workflows`' current safety stops being accidental.** It is safe today only
  because someone did not add it to the removal list; under §1 and §3 its safety follows from
  the rule.

### Negative

- **Behaviour change: paths the build previously removed will now be kept.** §1 makes
  non-attribution mean keep, so the change is in the safe direction — but it MUST be
  **visible** in run output at an appropriate severity. Silence is exactly what let this defect
  survive months of successful builds in the reporting repository; a build that quietly keeps
  more than it used to is a build whose behaviour nobody can audit. Kept-but-unattributable
  items MUST be reported, not merely spared.
- **Genuine orphans will survive longer.** A package-produced artifact whose provenance record
  is missing or damaged attributes as `unattributable` and is therefore kept. This is the
  accepted cost of the safe direction, and it is the boundary the orphan sweep negotiates
  (below).
- **`file_shims` moves from local to module scope.** This is a small refactor with a
  testability purpose, not a cosmetic one: §3's reconciliation cannot be written, and cannot be
  tested, against a variable that is not importable. It should not be reviewed as incidental
  tidying.

### Operational

- **Cost is set membership over a tree the build already walks.** The reconciliation in §3 is
  one set intersection over three small tables. The attribution in §1 is a membership test per
  candidate item. Anything in an implementation that scales worse than the installed tree
  itself SHOULD be questioned in review.
- **Boundary with the future orphan sweep.**
  [`BP-1500b-4`](../../acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500b-4.yaml)
  governs what a per-file provenance sweep may remove. Its rule MUST NOT contradict the §1
  attribution verdict: a path this ADR attributes as `adopter_owned` or `unattributable` is not
  available to the sweep for removal. The relationship is noted here; BP-1500b-4's own rules
  are not restated.
- **The printed advice is part of the repair, not a follow-up.** Without §4, the repair ships
  four fixed code paths and one page of prose still telling the adopter to delete their own
  work by hand.
- **`--clean` still has no dry-run path.** KI-BP-009 records that the only way to observe
  clean-mode's behaviour is to perform it. This ADR does not fix that, and does not depend on
  it being fixed; it is named so it is not mistaken for having been addressed here.

## Alternatives

- **Delete `.claude/skills` (or any other single entry) from `_PRE_CONSOLIDATION_PATHS`.**
  Rejected. It addresses one of the ten co-claimed paths and leaves the mechanism intact for
  the other nine. It is also disproved by time: the constant is by construction a *growing
  register of historical locations*, so a repair that consists of editing its contents is
  re-broken by the next version that adds an entry.

- **A protected-names allowlist.** Rejected. An allowlist cannot contain a name that did not
  exist when it was written. The AC set encodes exactly this as a control test —
  [`BP-1500g-1`](../../acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1.yaml)
  plants adopter content under a directory name containing a `uuid4` hex **minted inside the
  test body at run time**, so no committed list can pre-satisfy it. This is KI-BP-009's own
  smaller fallback, and it passes every other entry in that contract and fails this one.

- **`config/skill_registry.json`'s `portable: false` shape as the ownership record.** Rejected
  on two independent grounds. It is a *maintained declaration*, so it inherits the allowlist's
  failure mode above; and it covers only skills, not the other nine co-claimed containers.

- **Per-item symlinks alone, as KI-BP-009 literally proposes.** **Partially adopted**, and the
  split matters. The **item granularity is correct and is adopted** as Decision §2. The
  **provenance signal is not adopted**: inferring ownership from link-ness breaks under
  `shim_strategy: copy`, where package-produced items are real files. Keep the granularity;
  replace the signal with the recomputed attribution of Decision §1.

## References

- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) — establishes the shared
  occupancy that makes ownership a run-time question. Cited, not paraphrased: this ADR adds a
  decision procedure ADR-001 does not contain.
- [ADR-004 — Consolidated Output Root](ADR-004-consolidated-output-root.md) — introduced the
  `.leafcutter/` output root and the shim layer whose link-ness Decision §1 rejects as an
  ownership signal.
- [`docs/known-issues/build-pipeline.md`](../../known-issues/build-pipeline.md) — **KI-BP-009**
  (the directory-shaped case, with the 2026-08-25 empirical reproduction and the per-skill
  symlink fix direction); **KI-BP-20260907-0722** (the file-shaped case at
  `.pre-commit-config.yaml`); **KI-BP-010** and **KI-BP-20260907-0940** for the adjacent
  clean-mode and orphan-sweep defects.
- `scripts/build.py` — `_PRE_CONSOLIDATION_PATHS`, `_cleanup_stale_paths`,
  `_run_migration_report`, `_build_source_manifests`.
- `scripts/build_helpers.py` — `shim_map`, `install_shims`, and the `file_shims` local that
  Decision §3 promotes to module scope.
- `scripts/build_phases.py` — `clean_stale_artifacts`, the only current consumer of
  `_build_source_manifests`.

> **A note on citation form.** This ADR names functions and constants and gives no line
> numbers. Four different line numbers for `_PRE_CONSOLIDATION_PATHS` exist across this
> repository's own records — KI-BP-009 cites `build.py:1189`, KI-BP-20260907-0722 cites
> `:1586-1592`, BP-1500b-2's enrichment note cites `:1784` for `_build_source_manifests`, and
> the constant sits elsewhere again on this branch. Every one of those was right about some
> tree. Names are stable; numbers are not.
