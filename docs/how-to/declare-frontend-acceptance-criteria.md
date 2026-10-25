---
title: "How to Declare the Acceptance Criteria a Frontend Component Serves"
description: "Add an @ac declaration to a frontend component's leading comment and check what the shared declaration reader records for it before you commit."
type: how-to
status: active
created: 2026-10-23
last_updated: 2026-10-23
components:
  - commit_guardian
  - frontend_coding
related_docs:
  - docs/architecture/components/commit-guardian.md
  - docs/acceptance-criteria/guardrail-engine/GE-124-frontend-declares-what-it-renders/GE-124a.yaml
  - docs/product-truth/mock-data/guardrails/frontend-ac-declarations.mock.json
related_code:
  - templates/scripts/commit_guardian/_frontend_declaration_reader.py
---

# How to Declare the Acceptance Criteria a Frontend Component Serves

Name the acceptance criteria a screen component serves in its leading comment, so the declaration reader records them as an ordered list (GE-124a-1).

## Prerequisites

- A frontend component file with one of these extensions: `.tsx`, `.jsx`, `.ts`, `.js`, `.vue`, `.svelte`.
- The ids of the acceptance criteria the component serves, for example `UXP-607` and `UXP-607-1`.
- A git repository where the component file can be staged.
- Background on why one reader serves both enforcement tiers: [How the Reader Works](#how-the-reader-works) below.

## Steps

### Step 1 — Put an `@ac` line in the file's leading comment

The declaration must sit in the first comment block of the file, either a `/* ... */` block or a run of `//` lines. Comments further down the file are not read.

```tsx
/**
 * Requirement list screen.
 * @ac UXP-607, UXP-607-1
 */
export function RequirementList() {
  return null;
}
```

### Step 2 — List the ids in the order you want a reviewer to read them

Separate ids with commas, whitespace, or both. These three lines record the identical list `["UXP-607", "UXP-607-1"]`:

```text
@ac UXP-607, UXP-607-1
@ac UXP-607 UXP-607-1
@ac UXP-607,UXP-607-1
```

A single id, such as `@ac UXP-100d-2`, records a one-item list `["UXP-100d-2"]`. The reader keeps the order you wrote and never sorts or de-duplicates.

### Step 3 — Stage the file

The reader reads the staged blob from the git index, not the working-tree file. A declaration that is typed but not staged does not count.

```bash
git add src/screens/RequirementList.tsx
```

### Step 4 — Run the reader on the staged file

Run it from the repository root.

```bash
python3 scripts/commit_guardian/_frontend_declaration_reader.py --staged src/screens/RequirementList.tsx
```

The output is a JSON list with one record per path.

## Verification

Run the command from Step 4. Expected output, formatted here for reading (the real output is one line):

```json
[
  {
    "path": "src/screens/RequirementList.tsx",
    "framework": "react-tsx",
    "role": "component",
    "declaration_block": "/**\n * Requirement list screen.\n * @ac UXP-607, UXP-607-1\n */",
    "declares": ["UXP-607", "UXP-607-1"],
    "verdict": "declared"
  }
]
```

Check three things: `declares` holds your ids in your order, `verdict` is `declared`, and `declaration_block` is the comment text exactly as you wrote it.

The reader treats ids as opaque strings. It does not check that an id exists in the acceptance-criteria store; that check belongs to a later guardrail (GE-124c-2).

## Troubleshooting

1. **`verdict` is `missing` and `declares` is empty.** The leading comment has no `@ac` line, or the `@ac` line is in a later comment. Move it into the first comment block of the file, then stage the file again.
2. **`verdict` is `unreadable`.** Git could not read the path from the index, usually because the file is not staged or the path is wrong relative to the repository root. Stage the file, run the command from the repository root, and check the stderr line starting `[frontend-declaration-reader]`.
3. **The record shows an older declaration than the file on disk.** You edited the file after staging it. Run `git add` on it again.
4. **`ModuleNotFoundError` or a missing `scripts/commit_guardian/_frontend_declaration_reader.py`.** The deployed copy is stale. Rebuild with `build.py` so the module is copied from `templates/scripts/commit_guardian/`.

## How the Reader Works

- **One parser for every tier.** `_frontend_declaration_reader.py` is the **single** parser of the `@ac` grammar. The commit-tier check (GE-124c), the CI-tier gate (GE-124e) and the escape mechanisms (GE-124d) import it rather than re-parsing, because two parsers of one comment grammar drift and one tier then accepts what the other rejects.
- **Record.** One record per file with the fields `path`, `framework`, `role`, `declaration_block`, `declares` and `verdict`. `declaration_block` is the literal comment text, so a reviewer sees what was typed and not only what was parsed.
- **Verdict.** `declared` when at least one id is found, `missing` when the leading comment declares none, `unreadable` when the staged blob could not be read.
- **Staged content only.** `read_staged_declarations` reads each blob through the git index (`git show :<path>`). The `--staged <path>...` CLI prints the records as a JSON list.
- **Pure text scan.** No JavaScript or TypeScript AST dependency, so the whole staged set is read within the pre-commit latency budget.
- **Deployment.** The module deploys with the rest of `templates/scripts/commit_guardian/`, which is copied wholesale, so no deploy-manifest entry is needed.

## See Also

- [Commit guardian component](../architecture/components/commit-guardian.md) — the pre-commit hook system the reader belongs to.
- [GE-124a acceptance criterion](../acceptance-criteria/guardrail-engine/GE-124-frontend-declares-what-it-renders/GE-124a.yaml) — the parent criterion.
- [Frontend AC declarations mock data](../product-truth/mock-data/guardrails/frontend-ac-declarations.mock.json) — example declaration records.
- [Documentation Index](../INDEX.md)
