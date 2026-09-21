---
title: "KI-BP-20260909-standards-declare-no-applicability — only one of four configured guardrails says which kinds of file it governs; for the rest it lives in the script's filename"
description: "medium — nothing is broken today, because three of the four never run. It is filed because it is a **precondition** for `INF-1200`: a generic \"tell every owner of a file type its standards\" mechanism cannot be built over this config, and th"
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

# KI-BP-20260909-standards-declare-no-applicability — only one of four configured guardrails says which kinds of file it governs; for the rest it lives in the script's filename

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — nothing is broken today, because three of the four never run. It is filed because it is a **precondition** for `INF-1200`: a generic "tell every owner of a file type its standards" mechanism cannot be built over this config, and that is not obvious from reading any one section.
- **Status:** open — no AC of its own. Promoted into `INF-1200d-1`'s `it_requirements` as a measured constraint on that record's implementation.
- **Occurrences:** 1 (structural)
- **First seen:** 2026-09-09, found while enriching `INF-1200` · **Last seen:** 2026-09-09
- **Where:** `templates/scripts/commit_guardian/commit_guardian.json` — `file_size` (has `checked_extensions`), `complexity:25` (`max_score: 15`), `sql_complexity:33` (`max_score: 75`), `folder_density:141` (`max_files_per_folder: 15`)

**Symptom.** `file_size` declares `checked_extensions: ['.py', '.sql']` and per-extension `line_limits`. The other three declare a threshold and an `excluded_dirs` list and nothing else. There is no field anywhere saying that `complexity` governs Python, or that `sql_complexity` governs SQL. That fact exists only in the scripts' filenames and in each script's own hardcoded extension check.

**Why it matters beyond tidiness.** `INF-1200` is about joining two registries: `agent_registry.json`'s `owns_file_extensions` (which agent owns which file type) against the declared standards (which standard applies to which file type). The first side of that join exists. The second side exists for exactly one of four standards. So a walk that tried to derive "who must be told what" would today produce a correct answer for `file_size` and an empty answer for the other three — not an error, an *empty result*, which is the failure mode this repo has repeatedly found hardest to see.

**Interaction with the registration gap, which is the part that makes this easy to misread.** `complexity`, `sql_complexity` and `folder_density` also have no `hooks_manifest` entry, so they never run (that is `BP-1600a-2`'s census, not this entry). It is tempting to conclude the missing applicability does not matter because the guards are inert. It matters more, not less: when one of them is registered, it starts refusing commits for a standard no agent was ever told about, because there was no way to tell them.

**Fix direction.** Give every standards section the same shape `file_size` already has — an explicit statement of the kinds of file it governs — before anything tries to walk them. Do NOT infer applicability from the script filename: that is the same lexical-inference mistake catalogued two entries above, and it silently breaks the moment a script is renamed or a section governs two kinds of file. This is cheap now and expensive after a generic consumer exists.

**Related.**
- `INF-1200d-1` — carries this as a measured constraint; the tree cannot be implemented without it.
- `BP-1600a-2` — owns whether these three are registered. Different question, same three sections; do not conflate the two fixes.

**Pattern:** a registry where one entry carries the field a future consumer needs and its siblings carry it implicitly, in their names.

---
