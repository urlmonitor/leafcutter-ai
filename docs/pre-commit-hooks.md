# Pre-Commit Hooks

This document describes the pre-commit hooks enforced on every commit and
their relationship to build-drift detection.

## Hook Execution Sequence

```mermaid
flowchart TD
    GC[git commit] --> PC[pre-commit\nhook runner]

    PC --> H1[check-root-clutter\nno output files in project root]
    PC --> H2[check-doc-frontmatter\nall docs have valid frontmatter]
    PC --> H3[check-doc-length\ndocs under line limits]
    PC --> H4[check-python-complexity\nno functions above threshold]
    PC --> H5[check-python-docstrings\nmodule + function docstrings]
    PC --> H6[check-ticket-signoff-parity\nfrontmatter agents == Sign-offs]
    PC --> H7[apply-sql-changes\nauto-apply SQL to local DB]
    PC --> H8[run-unit-tests\nfast test suite]
    PC --> H9[check-structural-change\narchitecture docs required\nfor structural changes]
    PC --> H10[build-drift-check\ntemplates match generated output]
    PC --> H11[check-mermaid-complexity\nmermaid diagrams under complexity limits]

    H1 -->|pass| COMMIT[commit proceeds]
    H2 -->|pass| COMMIT
    H3 -->|pass| COMMIT
    H4 -->|pass| COMMIT
    H5 -->|pass| COMMIT
    H6 -->|pass| COMMIT
    H7 -->|pass| COMMIT
    H8 -->|pass| COMMIT
    H9 -->|pass| COMMIT
    H10 -->|pass| COMMIT
    H11 -->|pass| COMMIT

    H1 -->|fail| FIX[precommit-autofix\nskill routes to haiku/sonnet]
    H4 -->|fail| FIX
    H5 -->|fail| FIX
    H6 -->|fail| FIX
    H8 -->|fail| FIX
    H10 -->|fail| FIX
    H11 -->|fail| FIX
    FIX --> GC
```

## Build-Drift Check

The build-drift hook (`check-build-drift`) fires when any file under
`leafcutter/templates/` is staged. It runs `build.py --dry-run`
and checks whether the generated output matches the files currently in
`.claude/agents/`, `.claude/skills/`, etc.

```mermaid
flowchart LR
    T[template changed] --> D[build.py --dry-run]
    D -->|output matches| PASS[hook passes\ncommit proceeds]
    D -->|output differs| FAIL[hook fails\nrun build.py to regenerate\nthen re-stage]
```

## Hook Configuration

All hooks are configured in `.pre-commit-config.yaml`. The commit guardian
manages a subset via `scripts/commit_guardian/commit_guardian.json`.
See `scripts/commit_guardian/INTEGRATION.md` for setup instructions.
