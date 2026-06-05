<!--
GLOSSARY AUTHORING GUIDE (invisible in rendered docs)

1. Initial population: run `/glossary-bootstrap` once after install or after a
   significant codebase merge to seed this file from the existing codebase.

2. Ongoing additions: the pre-commit hook `check_glossary_coverage.py` detects
   novel jargon in staged .md/.py/.sql files, dispatches the haiku
   `glossary-triage` agent, and automatically appends approved entries here.

3. Do NOT hand-edit to add new entries. Always go through the triage flow so
   the blacklist stays consistent with the glossary. Manual edits are only for
   correcting or refining existing entries.

4. Entry format: each term uses a ### heading followed by a definition paragraph.
   Example:
       ### candle_horizon
       The number of candles in the rolling context window used for pattern matching.
-->
# Glossary

This file is auto-maintained by the glossary-automation system.
Run `/glossary-bootstrap` to populate it after initial install or after a
significant codebase merge.

<!-- Terms are added automatically. Each term uses a ### heading. -->

### Antigravity
An AI IDE/agent runner platform supported by leafcutter-ai, alongside Claude Code. Antigravity uses standard Model Context Protocol (MCP) tool declarations rather than bespoke CLI definitions.

### ticket_frontmatter_guard
A pre-commit hook (`scripts/commit_guardian/check_ticket_frontmatter.py`) that validates every staged ticket file's YAML frontmatter against the required field schema. It enforces the presence of `requires_diagram`, `requires_adr`, `agents`, and `files_touched` fields, and verifies that the `## Sign-offs` section lists exactly those agents whose `agents:` map value is `needed`. Generated tickets (from `generate_ticket_from_ac.py`) must pass this guard before their commit is accepted.
