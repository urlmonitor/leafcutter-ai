# Build Pipeline Architecture

This document shows how the leafcutter templates are compiled
into a target project by `build.py`.

## Source → Build → Output Flow

*Note: the post-edit verification contract enforced during build is the
`requires_verification` frontmatter rule, validated by
[`registry_validator.py`](../scripts/registry_validator.py).*

```mermaid
graph TD
    A[leafcutter/\ntemplates/] -->|build.py reads| B{build.py}
    C[skills_config.json\nin target project] -->|config values| B
    D[leafcutter/\nconfig/skills_config.schema.json] -->|validation| B

    B -->|compile agents| E[.claude/agents/\n*.md — runtime prompts]
    B -->|copy skills| F[.claude/skills/\n*/SKILL.md]
    B -->|copy workflows| G[.claude/commands/\n*.md]
    B -->|build workflow scripts| build_workflow_scripts[.claude/workflows/\nbuild-epic.js build-ticket.js create-ticket.js]
    B -->|copy rules| H[.agents/rules/\n*.md]
    B -->|scaffold| I[tickets/\n00_inbox/ 01_todo/ 99_done/]
    B -->|copy commit guardian| J[.leafcutter/scripts/commit_guardian/\n*.py *.json]
    B -->|copy doc compliance| K[.leafcutter/scripts/doc_compliance/\n*.py *.json]
    B -->|install shims| L[.git/hooks/\npre-commit shims]
    B -->|compile antigravity instructions| M[.gemini/instructions.md]
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

## Component Registry Tooling

The `scripts/add_component.py` script provides a CLI for appending new entries
to `docs/components.json` with schema validation before the write:

```bash
python scripts/add_component.py \
    --id my_component \
    --name "My Component" \
    --type utility \
    --description "Does something useful for the build pipeline." \
    --primary-code "scripts/my_component.py" \
    --status active \
    [--detail-ref "docs/architecture/components/my_component.md"]
```

The script:
- Validates the new entry against the minimum schema (same rules as the
  `check_components_integrity` pre-commit hook).
- Exits non-zero if the component ID already exists (prevents silent overwrites).
- Writes back with 2-space indentation and sorted component keys.

## Config Resolution

```mermaid
flowchart TD
    A[skills_config.default.json\nin package] -->|base values| M[merged config]
    B[project/.claude/\nskills_config.json] -->|overrides| M
    M --> V[validate against\nskills_config.schema.json]
    V -->|pass| BUILD[run build phases]
    V -->|fail| ERR[exit 1 with errors]
```
