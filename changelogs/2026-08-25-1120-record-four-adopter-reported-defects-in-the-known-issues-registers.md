---
title: "Record four adopter-reported defects in the known-issues registers"
date: "2026-08-25"
time: "11:20"
type: manual
components: 
  - build_pipeline
  - commit_guardian
  - documentation_system
summary: "Files a defect report from the DIAGraph adopter repo across three known-issues registers: two new entries, two occurrence bumps, and three further defects found while verifying the report."
description: "DIAGraph (roche-sandbox/dia-graph), running pin 54356a92, reported four defects and deliberately did not patch any of them locally, on the grounds that an adopter-local fix is silently lost the next time the submodule pin advances. Each was verified against the source in this repo before filing. Two are new entries. KI-CG-008: frontmatter_validators.validate_paths guards that related_docs is a list but never that its elements are strings, so the labelled `- genre: path` form raises TypeError rather than producing a validation error -- 33 of 50 documents in the reporting repo use that form, and because the hook crashes rather than fails, the only available response is SKIP=check-doc-frontmatter, which disables about 40 sibling hooks. KI-BP-008: build.py installs .claude/skills as a symlink to .leafcutter/skills, so an adopter's own skills have no location that is both discoverable by Claude Code and outside the generated tree; clean_stale_artifacts follows that symlink and rmtree's any directory absent from templates/skills/, which is every adopter skill. That deletion is a code reading, not an empirical result -- --clean has no dry-run path, so the only way to observe it is to perform it -- and the entry says so. Two are occurrence bumps on existing entries. KI-BP-003 goes from high to blocker: the unreachable config/doc_types.json is not a self-hosting curiosity, it fires in every adopter worktree, which is to say it is broken by the package's own /feature and building-epics workflow. KI-DS-001 gains a correction: the entry said the doc specialists improvise on a missing convention, but reference-author and explanation-author now hard-stop, so the four agents are visibly dead rather than quietly wrong. Three further defects were found while verifying the report and are filed alongside. KI-BP-009: _MANAGED_ARTIFACT_DIRS mixes two path conventions, so clean-mode's workflows entry resolves to .claude/.claude/workflows, never runs, and a real orphan (pause-resume-substrate.js, deployed with no template) survives every --clean while the run reports success. KI-DS-002: the doc conventions the specialists require live in this repo's docs/ tree rather than templates/, so no build phase deploys them and writing the four missing ones would fix this repo while changing nothing for any adopter. And KI-BP-005 gains two more instances of its class, including the observation that .leafcutter/config/doc_types.json in this workspace was hand-placed, is deployed by no build phase, and therefore masks KI-BP-003 locally -- any verdict on that defect taken from this workspace is vacuous. Documentation only; no code changes."
breaking: false
---

## Entry

See the individual register entries for full evidence and fix directions:

- `docs/known-issues/commit-guardian.md` — KI-CG-008
- `docs/known-issues/build-pipeline.md` — KI-BP-008, KI-BP-009, plus KI-BP-003 and KI-BP-005 updates
- `docs/known-issues/documentation-system.md` — KI-DS-002, plus the KI-DS-001 update
