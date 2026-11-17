---
title: "An empty config file path now means the feature is off (BP-1500h)"
date: "2026-10-14"
time: "15:00"
type: manual
components: 
  - build_pipeline
summary: "A file-location setting left empty in skills_config.json no longer makes the build read the project folder as a file; it switches that feature off, while a missing key still uses the shipped default and a broken path is warned about and skipped."
description: "New scripts/config_paths.py gives every build step one reading of a file-location setting (changelog_categories_path, precommit_autofix_config_path, reachability_exemptions_path, testing_context.readme_path): an empty value means the feature is off (announced once per build, no read, write, check or scaffold), an absent key means the shipped default from config/skills_config.default.json, and a path to a missing file or to a folder is a [WARNING] broken setting that is skipped with no fallback. The config-scaffold step, the staleness check and the referential-integrity check (which now rejects a folder for a file setting) all use it. changelog-agent's Step 3 is chosen at compile time: built-in categories when the setting is empty, otherwise read and apply the rules file; the silent `2>/dev/null` read is gone. reachability_exemptions_path joins the shipped defaults and the schema. Fixes the 'could not read <project> ... Is a directory' build warning."
breaking: false
---

## Entry
