---
title: "The package-surface validator now checks directories and no longer passes a run that checked nothing"
date: "2026-09-25"
time: "16:02"
type: manual
components:
  - ac_store
summary: "scripts/ac_store/validate_ac.py now walks a directory argument recursively (skipping index.yaml) and exits non-zero when its arguments resolve to zero files. Before, a directory was dropped silently and the run printed 'No YAML files to validate.' and exited 0."
description: "Covers ACS-100i-7-ii. Closes the KI-ACS-001 no-op that was fixed in validate_ac_schema.py but survived in its sibling validate_ac.py, which it-po.md tells agents to run (KI-ACS-20260925-validate-ac-bare-directory-exits-0). File arguments behave as before."
commits: [8bbb2b4b]
breaking: false
---

## Entry

`validate_ac.py` checks that records declaring a package surface carry a structured
implementation spec. Given a directory, it used to skip it without a word and report
success, so a component-wide check could pass while examining no records. It now
walks the directory the same way `validate_ac_schema.py` does, and any run that
examines zero records fails with an explicit "this is NOT a pass" message.
