---
title: "Fix AC schema validator drift, worktree check-secrets crash, and build-drift no-op (ACS-200e, GE-118a-1, GE-118b)"
date: "2026-08-13"
time: "23:28"
type: manual
components: 
  - ac_store
  - commit_guardian
  - build_pipeline
summary: "Fixed three guardrail tooling bugs so the standalone AC validator, the secret scanner, and the build-drift checks actually run and agree with the real commit-time gates instead of silently passing or crashing."
description: "Three unrelated bug fixes staged on split/code-fixes, not yet committed. (1) ACS-200e: scripts/ac_store/validate_ac_schema.py claimed to validate against config/ac_store_schema.json but never loaded it, running hand-rolled field checks only; AC files could print OK: valid and then be hard-rejected by the commit-time check-ac-schema hook. It now loads and applies the same schema the hook uses, and reports explicitly (instead of claiming success) when jsonschema or the schema file is unavailable. (2) GE-118a-1: templates/scripts/commit_guardian/check_secrets.py (plus config.py and commit_guardian.json) resolved its scanner directory from a hardcoded .claude/skills path that does not exist in a git worktree (only .leafcutter is deployed there), so the import raised ModuleNotFoundError and the hook crashed, blocking every commit; the standing workaround was SKIP=check-secrets, meaning the secrets gate was not running at all. Resolution is now layout-aware, checking the deployed-relative path first and the configured path as fallback, and fails closed with the list of paths tried instead of a raw traceback. (3) GE-118b: templates/scripts/commit_guardian/check_output_drift.py and check_build_drift.py computed the build manifest path using a hardcoded leafcutter/ package-directory segment, but the real package directory is leafcutter-ai, so the path never existed and both drift gates silently no-opped in every checkout, worktree or not. They now search for the manifest wherever build.py actually wrote it (git toplevel, derived workspace root, and subdirectories) with no package-name assumption, and report every path tried when the manifest is not found. Also present on this branch but already covered by a separate pre-existing changelog entry (PR #424): docs/components.json registration fixes, docs/architecture/components/epic-retrospective.md, and tests/test_build_artifact_parity.py."
breaking: false
---

## Entry
