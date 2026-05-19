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
