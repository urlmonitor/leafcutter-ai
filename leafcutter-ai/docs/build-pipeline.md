# Build Pipeline Architecture

This document shows how the leafcutter templates are compiled
into a target project by `build.py`.

## Source → Build → Output Flow

*Note: For the post-edit verification contract enforced during build, see [ADR 021: Agent Post-Edit Verification](../../docs/architecture/adrs/ADR-021-agent-post-edit-verification.md).*

```mermaid
graph TD
    A[leafcutter/\ntemplates/] -->|build.py reads| B{build.py}
    C[skills_config.json\nin target project] -->|config values| B
    D[leafcutter/\nconfig/skills_config.schema.json] -->|validation| B

    B -->|compile agents| E[.claude/agents/\n*.md — runtime prompts]
    B -->|copy skills| F[.claude/skills/\n*/SKILL.md]
    B -->|copy workflows| G[.claude/commands/\n*.md]
    B -->|copy rules| H[.agents/rules/\n*.md]
    B -->|scaffold| I[tickets/\n00_inbox/ 01_todo/ 99_done/]
    B -->|copy commit guardian| J[scripts/commit_guardian/\n*.py *.json]
    B -->|copy doc compliance| K[scripts/doc_compliance/\n*.py *.json]
    B -->|install shims| L[.git/hooks/\npre-commit shims]
```

## Agent Compilation Detail

For each `.md` file in `templates/agents/` (excluding `_*.md` helpers):

```mermaid
flowchart LR
    T[template.md\nYAML frontmatter\n+ body] --> P[parse_frontmatter]
    P -->|frontmatter dict| FM[filter to\nname,description,\nmodel,tools]
    P -->|body text| S[strip_metadata_sections\nremoving ## Configuration\n## Portability etc.]
    S --> I[inject_config\nreplace config.key\nplaceholders]
    I -->|requires_verification:true| VB[append\n_post_edit_verification.md]
    VB -->|signoff:true| SB[append\n_signoff_block.md]
    I -->|signoff:true| SB
    SB --> O[output.md\nclean runtime prompt]
    I -->|signoff:false| O
    FM -->|reconstruct YAML| O
```

## Config Resolution

```mermaid
flowchart TD
    A[skills_config.default.json\nin package] -->|base values| M[merged config]
    B[project/.claude/\nskills_config.json] -->|overrides| M
    M --> V[validate against\nskills_config.schema.json]
    V -->|pass| BUILD[run build phases]
    V -->|fail| ERR[exit 1 with errors]
```
