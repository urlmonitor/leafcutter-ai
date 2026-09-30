---
title: "No database address ships with leafcutter, and a check keeps it that way"
date: "2026-09-28"
time: "12:00"
type: manual
components:
  - infrastructure
  - testing_quality
summary: "The test-writer and test-runner agents and the test workflow no longer carry an adopter's database address: database tests read the project's own setting through the shared resolver and stop with a named error when it is missing, and the runner's pre-flight uses the db_check checker. Leafcutter's reference and testing docs describe the setting as having no default. A new CI check fails if a real-looking database address ever appears in what the package ships."
description: "INF-1100d-2, -3, -4, -4-i and -5 (manually orchestrated). templates/agents/test-writer.md Step 2b resolves the address with db_check.checker.resolve_test_db_address(Path.cwd()) and lets the not-configured error surface; templates/agents/test-runner.md runs `checker.py --target-dir .` and relays its five statuses without credentials; templates/workflows/test.md drops the port-5403 note. docs/reference/skills-config-fields.md, docs/testing/README.md and docs/agents/utility/test-runner.md use the placeholder form. New scripts/portability/check_shipped_addresses.py scans templates/ and config/ (or a built tree) with no exclusion list, allows placeholders and env references, fails a zero-file scan, and runs as the blocking CI job shipped-address-check; tests prove it fails on the four files that carried the address at e919a24f. INF-1100d-4's pre-fix count corrected from five to four. INF-1100d and all its children are done."
commits:
breaking: false
---

## Entry

Leafcutter used to ship one adopter's local database address in its agent instructions and
defaults. It no longer does anywhere: agents read the address from the project's own settings
and say clearly when none is set. A new check runs in CI and fails if a real database
address ever shows up again in the files leafcutter installs.
