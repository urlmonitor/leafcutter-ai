---
title: "A requirement can declare the files its work changes"
date: "2026-09-28"
time: "18:00"
type: manual
components:
  - ac_driven_dev
  - ac_store
summary: "An acceptance criterion can now carry an optional declared_files list naming the files its work changes, each marked existing or to_be_created. That list is the single answer to which files a piece of work touches; documentation links never count. The commit hook and the store validator both check it through one shared module: a path that is neither present nor marked to be created is refused, as is an empty list, an absolute or escaping path, a backslash path, a copy the build regenerates, or any non-canonical spelling. A record without the list stays valid and is reported as not evaluated. A finished record whose declared file was later deleted is reported store-wide, never refused."
description: "Covers ACD-1600c-4, -4-i, -4-ii, -4-iii and -4-iv. New modules scripts/ac_store/declared_files.py (the read seam, with a store-wide report CLI) and scripts/ac_store/_declared_files_path_form.py (path-form rules; regenerated roots read from the build's own shim map, falling back to its .gitignore block), both added to the AC-store deploy map. The check-ac-schema hook calls the seam through a new _declared_files_bridge.py in both its jsonschema and manual-fallback branches, and fails open with a warning if the seam cannot be imported. config/ac_store_schema.json declares the optional field. No existing record changes: the field is optional and absence is never a violation (ADR-026). A review finding (leading './', doubled slashes, trailing '/', or different case slipping past the regenerated-copy rule) was fixed test-first before merge."
commits:
breaking: false
---

## Entry

Until now the files a piece of work would change were guessed from an
acceptance criterion's documentation links, which also pick up files that
only describe the work (KI-ACS-002). A criterion can now say it directly with
`declared_files`, and every check that needs "which files does this work
change" reads that one list.

Existing criteria are untouched: the field is optional, and a criterion
without it is reported as "not evaluated: no declared files" rather than
passed or refused. The checks that depend on this list (the ACD-2500 file-aware
steps and the ticket generator, TKT-600a-3) can now be built.
