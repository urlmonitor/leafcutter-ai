---
title: "Known issues — commit-guardian"
description: "Open, observed defects in the commit-guardian component: the pre-commit hook family that gates commits, and in particular the AC-store hooks whose scope is the git index rather than the store. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-09-23
components:
  - commit_guardian
related_docs:
  - docs/architecture/components/commit-guardian.md
  - docs/architecture/components/phantom-done-prevention.md
---


# Known issues — commit-guardian

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-CG-YYYYMMDD-short-slug` section — the UTC date you
filed it plus a few words naming the defect. Nothing here is generated — edit it by hand. Fill
in what you actually know; an issue recorded with a thin `Evidence` line is far better than one
not recorded.

**Why a date-and-slug id and not the next free number.** Sequential ids collide whenever two
sessions file at once, and this register is the reason the convention changed: on 2026-08-26
two different defects both landed as `KI-CG-012`, and a changelog ended up describing
`KI-CG-012` using what became `KI-CG-013`'s text. Renumbering is worse than it sounds — inbound
references do not disambiguate, so a rename can silently repoint a citation at the wrong
defect. Existing `KI-CG-NNN` entries keep their ids; **do not renumber them.**

A few entries here use `KI-CG-YYYYMMDD-HHMM` instead. Both forms are collision-free and both
sort and grep identically on the `KI-CG-` prefix; the slug form is written above because it is
what the large majority of this register's entries already use. Do not renumber the timestamped
ones to match — see `KI-KM-20260826-id-convention-diverged-across-registers`, which measured the
inbound references that would break.

This instruction was itself stale until 2026-09-07: it kept prescribing next-free-number for
twelve days after the convention changed, in the very register whose collision prompted the
change.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`commit-guardian/`](commit-guardian/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/commit-guardian/open-blocker-*   # anything critical open?
ls docs/known-issues/commit-guardian/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`commit-guardian/resolved/`](commit-guardian/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 69** (5 blocker, 26 high, 38 low) · **Resolved: 8**

## Open

| Severity | Issue | File |
|---|---|---|
| `blocker` | KI-CG-008 — `check-doc-frontmatter` crashes with a `TypeError` on any non-string entry in `related_docs`, making the labelled-list form uncommittable | [open-blocker-ki-cg-008.md](commit-guardian/open-blocker-ki-cg-008.md) |
| `blocker` | KI-CG-021 — The whole-collection uniqueness pass is registered in no hook config and no CI workflow, and has never run | [open-blocker-ki-cg-021.md](commit-guardian/open-blocker-ki-cg-021.md) |
| `blocker` | KI-CG-20260831-0713 — PARTIALLY fixed by BP-100k-4-ii; the adopter still cannot commit, for a different reason | [open-blocker-ki-cg-20260831-0713.md](commit-guardian/open-blocker-ki-cg-20260831-0713.md) |
| `blocker` | KI-CG-20260909-gate-complexity — `check-complexity` judges every function absolutely, so registering it refuses 49 existing files including the two most-edited in the repo | [open-blocker-ki-cg-20260909-gate-complexity.md](commit-guardian/open-blocker-ki-cg-20260909-gate-complexity.md) |
| `blocker` | KI-CG-20260909-gate-root-files — `check-root-files` refuses 5 legitimate root files and matches `M`, so registering it makes `ruff.toml` and `LEAFCUTTER_VERSION` permanently uneditable | [open-blocker-ki-cg-20260909-gate-root-files.md](commit-guardian/open-blocker-ki-cg-20260909-gate-root-files.md) |
| `high` | KI-CG-001 — AC hooks are scoped to the git index, so parent-level drift is unreachable | [open-high-ki-cg-001.md](commit-guardian/open-high-ki-cg-001.md) |
| `high` | KI-CG-006 — The pre-commit proof-of-done gate and the CI backstop disagree on what a valid tag is, in both directions | [open-high-ki-cg-006.md](commit-guardian/open-high-ki-cg-006.md) |
| `high` | KI-CG-007 — The sanctioned way to add a component produces an entry the required gate rejects, and the gate's stated rule is weaker than the one it enforces | [open-high-ki-cg-007.md](commit-guardian/open-high-ki-cg-007.md) |
| `high` | KI-CG-009 — `check-components-integrity` resolves the repo root to the main checkout instead of the worktree, so a branch-only `detail_ref` doc is reported missing | [open-high-ki-cg-009.md](commit-guardian/open-high-ki-cg-009.md) |
| `high` | KI-CG-010 — `check-roadmap-schema` never validates the roadmap, and two other guardrails require content the schema forbids | [open-high-ki-cg-010.md](commit-guardian/open-high-ki-cg-010.md) |
| `high` | KI-CG-012 — The hooks' test seams disagree on both variable name and separator, so verifying a hook the wrong way exits 0 having checked nothing | [open-high-ki-cg-012-the-hooks-test-seams-disagree-on.md](commit-guardian/open-high-ki-cg-012-the-hooks-test-seams-disagree-on.md) |
| `high` | KI-CG-012 — `check-ac-schema` reports a clean pass on a file it never validated, because Phase 1 fails open on an empty staged set | [open-high-ki-cg-012-check-ac-schema-reports-a-clean-pass-on.md](commit-guardian/open-high-ki-cg-012-check-ac-schema-reports-a-clean-pass-on.md) |
| `high` | KI-CG-014 — `declares_side_effect` derivation is negation-blind, so an AC asserting that nothing is written is forced to declare that something is | [open-high-ki-cg-014.md](commit-guardian/open-high-ki-cg-014.md) |
| `high` | KI-CG-017 — `check-build-drift` is filtered on the consumer layout path, so it has never run on this repo's own template changes | [open-high-ki-cg-017.md](commit-guardian/open-high-ki-cg-017.md) |
| `high` | KI-CG-018 — `check_ac_governance` exits 0 without inspecting anything, and its own "did I look?" diagnostic cannot fire on the paths where it did not | [open-high-ki-cg-018.md](commit-guardian/open-high-ki-cg-018.md) |
| `high` | KI-CG-20260914-ac-hooks-resolve-root-from-cwd — all six AC gates take their project root AND their file set from the current directory, so from the wrong cwd they validate zero files and exit 0 | [open-high-ki-cg-20260914-ac-hooks-resolve-root-from-cwd.md](commit-guardian/open-high-ki-cg-20260914-ac-hooks-resolve-root-from-cwd.md) |
| `high` | KI-CG-022 — `check_adr_collision.py` exists but is registered nowhere, and the branch that registers it also makes it fail closed without `origin/main` | [open-high-ki-cg-022.md](commit-guardian/open-high-ki-cg-022.md) |
| `high` | KI-CG-035 — `check-proof-promise-claim` is a done-time gate that fires at creation time, so no generated epic scaffold can be committed | [open-high-ki-cg-035.md](commit-guardian/open-high-ki-cg-035.md) |
| `high` | KI-CG-20260826-1612 — Every AC guardian filters the index on `--diff-filter=AM`, so a *renamed* AC record is invisible to all six — and renaming is exactly what a tree split requires | [open-high-ki-cg-20260826-1612.md](commit-guardian/open-high-ki-cg-20260826-1612.md) |
| `high` | KI-CG-20260831-1933 — `check-predone-scope` compares the whole branch diff against one ticket's `files_touched`, so it can never pass on a multi-ticket epic branch | [open-high-ki-cg-20260831-1933.md](commit-guardian/open-high-ki-cg-20260831-1933.md) |
| `high` | KI-CG-20260831-glossary-coverage-detector-path-unreachable — `check-glossary-coverage` has never run in this repo: it loads its detector from a path no leafcutter layout has, and its own "detector not found" message is dead code | [open-high-ki-cg-20260831-glossary-coverage-detector-path-unreachable.md](commit-guardian/open-high-ki-cg-20260831-glossary-coverage-detector-path-unreachable.md) |
| `high` | KI-CG-20260831-hook-scripts-never-invoked — 24 hook scripts are named by no `entry:` line, and the guard that exists to find unreachable hooks iterates only the registered ones | [open-high-ki-cg-20260831-hook-scripts-never-invoked.md](commit-guardian/open-high-ki-cg-20260831-hook-scripts-never-invoked.md) |
| `high` | KI-CG-20260831-manifest-shadowing — `check-build-drift` takes the first `.build_manifest.json` it finds, and an obsolete one at a higher-priority root makes it report every template in the repository as unregistered | [open-high-ki-cg-20260831-manifest-shadowing.md](commit-guardian/open-high-ki-cg-20260831-manifest-shadowing.md) |
| `high` | KI-CG-20260907-0745 — `enforce_commit_delegation` and `inline_work_guard` locate themselves by testing for the *directory* `.claude/hooks`, so a partial one shadows the real set and blocks every Bash, Edit and Write call | [open-high-ki-cg-20260907-0745.md](commit-guardian/open-high-ki-cg-20260907-0745.md) |
| `high` | KI-CG-20260907-ac-hooks-are-blind-to-renames-and-disagree-on-their-test-seam — KI-CG-20260907-ac-hooks-are-blind-to-renames-and-disagree-on-their-test-seam | [open-high-ki-cg-20260907-ac-hooks-are-blind-to-renames-and-disagree-on-their-test-seam.md](commit-guardian/open-high-ki-cg-20260907-ac-hooks-are-blind-to-renames-and-disagree-on-their-test-seam.md) |
| `high` | KI-CG-20260907-commit-delegation-is-a-password-not-an-identity — the hook that enforces "only the commit agent may commit" is satisfied by typing a string | [open-high-ki-cg-20260907-commit-delegation-is-a-password-not-an-identity.md](commit-guardian/open-high-ki-cg-20260907-commit-delegation-is-a-password-not-an-identity.md) |
| `high` | KI-CG-20260909-gate-test-ac-tags — `check-test-ac-tags` is one absent config key away from refusing 5,566 test functions | [open-high-ki-cg-20260909-gate-test-ac-tags.md](commit-guardian/open-high-ki-cg-20260909-gate-test-ac-tags.md) |
| `high` | KI-CG-20260909-gate-ticket-test-requirements — registered as configured, `check-ticket-test-requirements` would inspect nothing; wired correctly it fails 252 tickets | [open-high-ki-cg-20260909-gate-ticket-test-requirements.md](commit-guardian/open-high-ki-cg-20260909-gate-ticket-test-requirements.md) |
| `high` | KI-CG-20260914-contract-guard-crashes-on-diff-bytes — the contract-shrinking guard decodes the staged diff in the console code page, crashes on the first non-cp1252 byte, and blocks the commit instead of failing open | [open-high-ki-cg-20260914-contract-guard-crashes-on-diff-bytes.md](commit-guardian/open-high-ki-cg-20260914-contract-guard-crashes-on-diff-bytes.md) |
| `high` | KI-CG-20260914-ratchet-freezes-central-registries — a per-file ratchet makes any manifest or registry unmaintainable once it crosses its limit, because complying with the rule on one file forces violating it on another | [open-high-ki-cg-20260914-ratchet-freezes-central-registries.md](commit-guardian/open-high-ki-cg-20260914-ratchet-freezes-central-registries.md) |
| `high` | KI-CG-20260914-ratchet-max-baseline-refuses-union-merges — `check-file-size`'s merge baseline is the MAXIMUM across parents, but a clean merge holds BOTH parents' additions, so a union that authored no new content still exceeds the permitted length and the gate refuses it | [open-high-ki-cg-20260914-ratchet-max-baseline-refuses-union-merges.md](commit-guardian/open-high-ki-cg-20260914-ratchet-max-baseline-refuses-union-merges.md) |
| `low` | KI-CG-002 — The diagram-type guard silently swaps its enum source when its declaring file is unreachable | [open-low-ki-cg-002.md](commit-guardian/open-low-ki-cg-002.md) |
| `low` | KI-CG-011 — The roadmap mirror strips its own `description` frontmatter and backdates `created` to today | [open-low-ki-cg-011.md](commit-guardian/open-low-ki-cg-011.md) |
| `low` | KI-CG-013 — The schema hook and the done-proof oracle disagree about what a leaf is, so one AC can be required to satisfy both branches | [open-low-ki-cg-013.md](commit-guardian/open-low-ki-cg-013.md) |
| `low` | KI-CG-015 — `declares_side_effect` is authored by the IT-PO pass and derived by the schema check, and on records about writing files the two systematically disagree | [open-low-ki-cg-015.md](commit-guardian/open-low-ki-cg-015.md) |
| `low` | KI-CG-016 — `enforce_commit_delegation` matches the phrase anywhere in the command string, so read-only commands that merely mention committing are blocked | [open-low-ki-cg-016.md](commit-guardian/open-low-ki-cg-016.md) |
| `low` | KI-CG-019 — the `templates/` copy of `check_ac_parent_covered_by` fail-opens on an import it can never satisfy, so verifying from `templates/` always passes | [open-low-ki-cg-019.md](commit-guardian/open-low-ki-cg-019.md) |
| `low` | KI-CG-020 — hook registration has a fourth leg nobody documents: a hook absent from `blocking_hook_ids` is skipped by the autofix loop | [open-low-ki-cg-020.md](commit-guardian/open-low-ki-cg-020.md) |
| `low` | KI-CG-023 — `check-predone-scope` cannot distinguish a ticket's subject from its driver, and reconciles branch-wide rather than commit-wide | [open-low-ki-cg-023.md](commit-guardian/open-low-ki-cg-023.md) |
| `low` | KI-CG-024 — `check_ticket_signoff_parity.py` silently skips check #6 because its default registry path does not exist in this layout | [open-low-ki-cg-024.md](commit-guardian/open-low-ki-cg-024.md) |
| `low` | KI-CG-025 — `check_ticket_state_integrity.py` retains an always-exit-0 contract that a coder cannot unilaterally retire | [open-low-ki-cg-025.md](commit-guardian/open-low-ki-cg-025.md) |
| `low` | KI-CG-026 — The unattributed-collision count is computed and then discarded by `pre-commit` | [open-low-ki-cg-026.md](commit-guardian/open-low-ki-cg-026.md) |
| `low` | KI-CG-027 — `main()` derives the project root from `Path.cwd()` while the canonical resolver sits unused beside it | [open-low-ki-cg-027.md](commit-guardian/open-low-ki-cg-027.md) |
| `low` | KI-CG-028 — The diagrams root is hardcoded while its sibling architecture roots are configurable | [open-low-ki-cg-028.md](commit-guardian/open-low-ki-cg-028.md) |
| `low` | KI-CG-029 — `repair_work_item_duplicates.py` has no CLI, so a destructive repair can only be invoked from a test | [open-low-ki-cg-029.md](commit-guardian/open-low-ki-cg-029.md) |
| `low` | KI-CG-030 — Staged paths with non-ASCII characters are silently unattributed | [open-low-ki-cg-030.md](commit-guardian/open-low-ki-cg-030.md) |
| `low` | KI-CG-031 — `scan_decisions` and `scan_diagrams` fail silently while their sibling scanner logs | [open-low-ki-cg-031.md](commit-guardian/open-low-ki-cg-031.md) |
| `low` | KI-CG-032 — The uniqueness pass's YAML fast path fabricates an id claim for records a full parse rejects | [open-low-ki-cg-032.md](commit-guardian/open-low-ki-cg-032.md) |
| `low` | KI-CG-033 — Placeholder marker detection flags markdown emphasis as a list bullet, and its false-positive cost was measured on one marker and claimed for all six | [open-low-ki-cg-033.md](commit-guardian/open-low-ki-cg-033.md) |
| `low` | KI-CG-036 — Criteria wrap onto lines beginning with a lowercase Gherkin keyword, making any line-anchored clause matcher ambiguous | [open-low-ki-cg-036.md](commit-guardian/open-low-ki-cg-036.md) |
| `low` | KI-CG-20260831-fictional-config-schema-fragment — two approved acceptance criteria declare a package-surface config key that was never created, and the validator that demanded the declaration cannot tell | [open-low-ki-cg-20260831-fictional-config-schema-fragment.md](commit-guardian/open-low-ki-cg-20260831-fictional-config-schema-fragment.md) |
| `low` | KI-CG-20260831-hook-parity-legs-alias-and-fail-open — `check_hook_parity`'s two parity legs alias to one directory in a worktree, it compares another branch's build against your templates, and it fail-opens when its roots do not resolve | [open-low-ki-cg-20260831-hook-parity-legs-alias-and-fail-open.md](commit-guardian/open-low-ki-cg-20260831-hook-parity-legs-alias-and-fail-open.md) |
| `low` | KI-CG-20260831-test-ac-tags-dead-three-ways — the test-to-AC traceability gate is registered nowhere, defaults to warn-only, and the config key that would escalate it is absent from the shipped config | [open-low-ki-cg-20260831-test-ac-tags-dead-three-ways.md](commit-guardian/open-low-ki-cg-20260831-test-ac-tags-dead-three-ways.md) |
| `low` | KI-CG-20260901-authoring-hook-scans-the-whole-collection-on-every-edit — every Edit/Write pays a full four-namespace numbering scan, whatever file was touched | [open-low-ki-cg-20260901-authoring-hook-scans-the-whole-collection-on-every-edit.md](commit-guardian/open-low-ki-cg-20260901-authoring-hook-scans-the-whole-collection-on-every-edit.md) |
| `low` | KI-CG-20260901-covers-regex-truncates-suffixed-ids — `check_ac_coverage`'s tag pattern collapses every suffixed AC id to its L0 root and cannot see `//` tags at all | [open-low-ki-cg-20260901-covers-regex-truncates-suffixed-ids.md](commit-guardian/open-low-ki-cg-20260901-covers-regex-truncates-suffixed-ids.md) |
| `low` | KI-CG-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message — `check-feedback-id`'s documented `[NO-FEEDBACK-CHECK]` bypass cannot work with `git commit -m`, and the message it does read is the last successful commit's | [open-low-ki-cg-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message.md](commit-guardian/open-low-ki-cg-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message.md) |
| `low` | KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look — KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look | [open-low-ki-cg-20260901-precommit-probe-reports-false-where-it-means-could-not-look.md](commit-guardian/open-low-ki-cg-20260901-precommit-probe-reports-false-where-it-means-could-not-look.md) |
| `low` | KI-CG-20260908-covers-tag-must-be-inside-a-test-function — the pre-commit done-proof gate accepts a Python `# covers:` tag anywhere in the file while CI's oracle counts it only inside a test function, so a tag can pass locally and fail the required check with two different accounts of the same file | [open-low-ki-cg-20260908-covers-tag-must-be-inside-a-test-function.md](commit-guardian/open-low-ki-cg-20260908-covers-tag-must-be-inside-a-test-function.md) |
| `low` | KI-CG-20260909-dormant-gate-registration-census — twelve commit-guardian scripts have never been registered, and a census of what each would actually do finds only one that both enforces and passes; four are non-enforcing because a config key is absent, one inspects nothing because of its `pass_filenames` wiring, and two would deadlock ordinary work | [open-low-ki-cg-20260909-dormant-gate-registration-census.md](commit-guardian/open-low-ki-cg-20260909-dormant-gate-registration-census.md) |
| `low` | KI-CG-20260909-gate-ac-done-on-merge — the only gate of the twelve that writes, never run here, and registration points it at 354 tickets | [open-low-ki-cg-20260909-gate-ac-done-on-merge.md](commit-guardian/open-low-ki-cg-20260909-gate-ac-done-on-merge.md) |
| `low` | KI-CG-20260909-gate-doc-links — `check-doc-links` returns 0 unconditionally, so registering it adds a gate that cannot fail | [open-low-ki-cg-20260909-gate-doc-links.md](commit-guardian/open-low-ki-cg-20260909-gate-doc-links.md) |
| `low` | KI-CG-20260909-gate-folder-density — `check-folder-density`'s grandfather compares `git ls-files`, which already includes staged additions, so its blocking branch is unreachable | [open-low-ki-cg-20260909-gate-folder-density.md](commit-guardian/open-low-ki-cg-20260909-gate-folder-density.md) |
| `low` | KI-CG-20260909-gate-test-fixture-bloat — `check-test-fixture-bloat` is disabled by an absent config section, hiding 499 violations, and only one of its three axes ratchets cleanly | [open-low-ki-cg-20260909-gate-test-fixture-bloat.md](commit-guardian/open-low-ki-cg-20260909-gate-test-fixture-bloat.md) |
| `low` | KI-CG-20260909-gate-ticket-ac-limits-and-the-three-inert — the one gate ready to register today, and three whose population is empty here | [open-low-ki-cg-20260909-gate-ticket-ac-limits-and-the-three-inert.md](commit-guardian/open-low-ki-cg-20260909-gate-ticket-ac-limits-and-the-three-inert.md) |
| `low` | KI-CG-20260914-done-proof-precommit-ignores-test-required — the pre-commit done-proof gate demands a covers tag from an AC that declares it needs no test, while the CI gate it stands in for exempts that AC | [open-low-ki-cg-20260914-done-proof-precommit-ignores-test-required.md](commit-guardian/open-low-ki-cg-20260914-done-proof-precommit-ignores-test-required.md) |
| `low` | KI-CG-20260914-exception-hook-blocks-silently — the PostToolUse exception-handling hook fails every Python write with an empty error when `ruff` is importable but not on PATH | [open-low-ki-cg-20260914-exception-hook-blocks-silently.md](commit-guardian/open-low-ki-cg-20260914-exception-hook-blocks-silently.md) |
| `low` | KI-CG-20260914-post-merge-stage-registers-but-installs-no-shim — a hook on the post-merge stage is registered, renders into the config, and still never fires in any checkout that did not create a ticket worktree | [open-low-ki-cg-20260914-post-merge-stage-registers-but-installs-no-shim.md](commit-guardian/open-low-ki-cg-20260914-post-merge-stage-registers-but-installs-no-shim.md) |
| `low` | KI-CG-20260923-contract-shrinking-guard-rename-blind — `check-contract-shrinking` correlates deleted test names against added test names, so a renamed test reads as a deleted one | [open-low-ki-cg-20260923-contract-shrinking-guard-rename-blind.md](commit-guardian/open-low-ki-cg-20260923-contract-shrinking-guard-rename-blind.md) |
| `low` | KI-CG-20260923-no-gate-validates-doc-to-doc-markdown-links — no hook resolves a markdown link between two docs; `check-doc-links` covers code-to-doc only, by design, so a doc split that leaves two dead links and an orphaned anchor passes every gate | [open-low-ki-cg-20260923-no-gate-validates-doc-to-doc-markdown-links.md](commit-guardian/open-low-ki-cg-20260923-no-gate-validates-doc-to-doc-markdown-links.md) |

## Resolved

| Severity | Issue | File |
|---|---|---|
| `low` | KI-CG-004 — moved to `security-scanner` | [resolved-low-ki-cg-004.md](commit-guardian/resolved/resolved-low-ki-cg-004.md) |
| `blocker` | KI-CG-005 — `check-product-truth-validate` / `check-product-truth-generate` hard-fail on an absent, explicitly optional product-truth store, gating every AC YAML commit — RESOLVED: EPIC-TruthfulProjectRecord's write-if-absent empty-record scaffold + fail-open "nothing-examined" outcome mean the described scenario now exits 0 | [resolved-blocker-ki-cg-005.md](commit-guardian/resolved/resolved-blocker-ki-cg-005.md) |
| `high` | KI-CG-034 — `check_output_drift` examines every output file and compares none of them: the scanner and the installer key paths in two namespaces that never intersect | [resolved-high-ki-cg-034.md](commit-guardian/resolved/resolved-high-ki-cg-034.md) |
| `low` | KI-CG-20260826-1334 — RETRACTED: "a missing schema makes `check-ac-schema` fail open" — tested and disproved; the real cause is the `KI-CG-012` at line 800 | [resolved-low-ki-cg-20260826-1334.md](commit-guardian/resolved/resolved-low-ki-cg-20260826-1334.md) |
| `high` | KI-CG-20260826-package-surface-refuses-merge-commits — merging `origin/main` into a branch is refused as if the branch had added every registry entry landed upstream since it forked | [resolved-high-ki-cg-20260826-package-surface-refuses-merge-commits.md](commit-guardian/resolved/resolved-high-ki-cg-20260826-package-surface-refuses-merge-commits.md) |
| `low` | KI-CG-20260908-file-size-refusal-advises-a-dead-command — the only remediation the live file-size gate offers points at a slash command whose own first step runs a script that does not exist | [resolved-low-ki-cg-20260908-file-size-refusal-advises-a-dead-command.md](commit-guardian/resolved/resolved-low-ki-cg-20260908-file-size-refusal-advises-a-dead-command.md) |
| `low` | KI-CG-20260914-doc-length-blocks-registers — RETRACTED: "check-doc-length tests absolute size and refuses any register edit" — tested and disproved; it ratchets on growth | [resolved-low-ki-cg-20260914-doc-length-blocks-registers.md](commit-guardian/resolved/resolved-low-ki-cg-20260914-doc-length-blocks-registers.md) |
| `high` | KI-CG-20260908-ratchet-reads-pre-merge-head — `check-file-size`'s ratchet resolves a file's previous length from `HEAD`, which during a merge is the branch's pre-merge tip, so a file long-standing on `origin/main` but absent from the branch is judged against the absolute limit and can refuse a merge for content the merge did not author | [resolved-high-ki-cg-20260908-ratchet-reads-pre-merge-head.md](commit-guardian/resolved/resolved-high-ki-cg-20260908-ratchet-reads-pre-merge-head.md) |
