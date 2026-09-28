---
title: "How to work with transform hooks in leafcutter's pre-commit pipeline"
description: "The transform tier of pre-commit hooks: what it is, the two shipped transform hooks, how silent auto-fix and re-staging works, hook ordering relative to validators, and fail-open behavior."
type: how_to
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - build_pipeline
related_docs:
  - docs/how-to/managing-pre-commit-hooks.md
  - docs/architecture/components/commit-guardian.md
---

> **Parent document:** [managing-pre-commit-hooks.md](managing-pre-commit-hooks.md)

# How to work with transform hooks in leafcutter's pre-commit pipeline

Pre-commit hooks in leafcutter fall into two tiers, recorded in the `tier`
field of each entry in the `hooks_manifest.hooks` array inside
`commit_guardian.json`:

| Tier | Behavior | Exit code |
|------|----------|-----------|
| `judgment` | Inspects staged files and **blocks** the commit when a policy is violated. | Non-zero on failure |
| `transform` | Edits staged files in place to fill missing data, re-stages them, and always exits 0. | Always 0 |

You can inspect the tier of any hook by looking at its entry in
`scripts/commit_guardian/commit_guardian.json` (or
`templates/scripts/commit_guardian/commit_guardian.json` in the package source).

## The two transform hooks

Two transform hooks shipped with EPIC-PrecommitSafetyNet (ticket 02):

### `transform-doc-frontmatter`

**Script:** `scripts/commit_guardian/transform_doc_frontmatter.py`

Fills missing YAML frontmatter fields in staged `docs/*.md` files before
the `check-doc-frontmatter` judgment hook runs. Specifically, it fills:

- `created` — set to today's ISO date when absent.
- `last_updated` — set to today's ISO date when absent.
- `type` — set to the first value in `doc_frontmatter.allowed_types`
  (default: `how-to`) when absent.
- `status` — set to the first value in `doc_frontmatter.allowed_statuses`
  (default: `draft`) when absent.

These defaults are read from the `doc_frontmatter` section of
`commit_guardian.json` at runtime.

The hook **never overwrites a field that already has a value**. If a field
is present (even if blank), the hook leaves it untouched.

### `transform-description-field`

**Script:** `scripts/commit_guardian/transform_description_field.py`

Fills a missing `description` field in staged `docs/*.md` files before the
`check-description-field` judgment hook runs. When `description` is absent
and a `title` field is present, it writes a stub description derived from
the title: `"Overview of <title>."`.

If `description` is already present, or if there is no `title` to derive
from, the hook makes no edit and exits 0 immediately.

## How transform hooks work (silent auto-fix and re-stage)

When a transform hook fills a missing field, it:

1. Edits the file on disk in place.
2. Re-stages the file with `git add` so the corrected content is included in
   the commit — no manual `git add` required.
3. Prints a brief informational message to stderr (e.g.
   `[transform-doc-frontmatter] docs/foo.md: filled 2 missing frontmatter field(s)`).
4. Exits 0.

The result: the commit proceeds with the corrected file. No user action is
needed, and the commit is not blocked. If you run `git show HEAD` after the
commit, you will see the filled fields in the staged content as if you had
added them yourself.

## Hook ordering: transforms run before validators

Within a single pre-commit run, transform hooks execute **before** their
matching judgment (validator) hooks. In `commit_guardian.json` the order is:

1. `transform-doc-frontmatter` (`tier: transform`)
2. `transform-description-field` (`tier: transform`)
3. `check-description-field` (`tier: judgment`)

This ensures that by the time the validator runs, the transform hook has
already filled any deterministically-derivable missing field. The validator
then sees a complete file and passes cleanly.

> **Note:** `check-doc-frontmatter` runs earlier in the pipeline than the
> two transform hooks above; see the full ordered list in `commit_guardian.json`.
> The transform hooks cover only the fields they are responsible for.

## Fail-open and absent-docs-layout no-op behavior

Both transform hooks are **fail-open**: if anything goes wrong during
parsing or writing, the hook logs a warning to stderr and exits 0. A commit
is **never blocked** by a transform hook.

Specific fail-open cases:

- **No YAML frontmatter block** — the file does not start with `---`:
  the hook skips the file and exits 0.
- **YAML parse failure** — the frontmatter block exists but cannot be
  parsed (e.g. invalid YAML): the hook skips the file and exits 0.
- **`pyyaml` not installed** — the hook skips all files and exits 0.
- **No staged docs files** — no `.md` files under the configured `docs_dir`
  are staged: the hook exits 0 immediately.
- **`docs/` layout absent** — if the project does not have a `docs/`
  directory (or uses a non-default `docs_dir` that does not exist), no
  files will match the git-diff filter and the hook exits 0 silently.

This means adopters in projects without a `docs/` layout — or with a
`docs_dir` override that points elsewhere — are completely unaffected by
these hooks. The hooks stay silent and never interfere with unrelated
projects.

## See also

- [managing-pre-commit-hooks.md](managing-pre-commit-hooks.md) — the parent
  guide: hook CRUD lifecycle, verification, troubleshooting, and the
  record's checker's automatic trigger scope.
