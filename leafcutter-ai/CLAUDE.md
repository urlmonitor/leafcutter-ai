# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

<!-- glossary-section: leafcutter -->
## Glossary

Project jargon and terminology is tracked at [docs/glossary.md](docs/glossary.md).

Consult it for project-specific terms when reading code or docs.

- **To populate from scratch**: run `/glossary-bootstrap` (once after initial install
  or after a major codebase merge).
- **Ongoing additions**: the `check-glossary-coverage` pre-commit hook detects novel
  terms in staged files and dispatches the `glossary-triage` agent automatically.
- **Do NOT hand-edit to add entries** — always use the triage flow so the blacklist
  stays consistent. Manual edits are only for correcting existing entries.
