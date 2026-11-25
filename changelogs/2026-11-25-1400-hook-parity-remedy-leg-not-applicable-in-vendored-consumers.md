---
title: "check-hook-parity no longer blocks consumers that vendor the package with could_not_check"
date: "2026-11-25"
time: "14:00"
type: manual
components:
  - commit_guardian
summary: "check-hook-parity's remedy-declaration leg treated any project whose configured canonical manifest existed as the package checkout. A consumer that vendors the package (DIAGraph points hook_parity.manifests.canonical at leafcutter/templates/scripts/commit_guardian/commit_guardian.json) has that file, so every commit touching scripts/commit_guardian/ there ended in could_not_check (exit 2) on templates/scripts/precommit-autofix.json, a package-only file the consumer does not track. Twice the commit had to be made with SKIP=check-hook-parity. The leg now applies only where templates/scripts/commit_guardian/commit_guardian.json exists under the project root, which is GE-132a-4's own definition of a package checkout. Anywhere else it prints a not-applicable line naming both paths. Script, manifest and deployed parity still run in consumers and still refuse. In the package checkout an absent or invalid committed table is still could_not_check."
description: "GE-132a-5 (new L2 under GE-132a). templates/scripts/commit_guardian/_remedy_registration_parity.py: new PACKAGE_MANIFEST_REL and _not_applicable_reason(canonical_manifest, root), which check_remedy_declarations consults before reading anything. The existing absent-manifest note is unchanged and there is a new vendored-copy note. Added a module docstring APPLICABILITY paragraph and a DECISION HISTORY block. Rejected alternative: reading the vendored or deployed table in consumers, because GE-132a-4 forbids the deployed fallback and a consumer cannot fix package content. New unit_tests/commit_guardian/test_ge_132a_5_consumer_installs.py runs check_hook_parity.py as a process in a DIAGraph-shaped consumer (not applicable, exit 0; deployed drift still exit 1) and in a package-shaped root (absent or invalid table exits 2, the real table exits 0). docs/reference/remedy-declarations.md updated."
commits:
breaking: false
---

## Entry

Projects that keep leafcutter in a subfolder could not commit changes to their guardian scripts
without skipping check-hook-parity. The hook went looking for a package-only file they do not have
and reported "could not check". It now says plainly that this part of the check only applies inside
the leafcutter repository itself. The parity checks that matter for those projects keep running.
Inside leafcutter a missing or broken declaration table still blocks the commit.
