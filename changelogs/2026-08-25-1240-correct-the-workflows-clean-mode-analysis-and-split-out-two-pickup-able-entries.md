---
title: "Correct the workflows clean-mode analysis and split out two pickup-able entries"
date: "2026-08-25"
time: "12:40"
type: manual
components: 
  - build_pipeline
  - documentation_system
summary: "Retracts a wrong claim #520 landed inside KI-BP-009, files the workflows clean-mode defect as KI-BP-010 with the verified analysis, and files the adopter-delivery gap as KI-DS-002."
description: "This is the delta remaining after #520 landed the same in-flight known-issues batch concurrently. Most of that work is already on main and is not touched here. Three things were not, and one of them is a correction. The correction: #520's KI-BP-009 states that _build_source_manifests returns no workflows key, that expected_names would therefore be empty, and that repairing the doubled path segment in _MANAGED_ARTIFACT_DIRS would delete every deployed workflow on the first --clean. The key exists -- scripts/build.py:1246-1258 populates it from templates/workflows-js/*.js -- so the manifest side is correct, the entry is simply never consulted, and repairing the path is safe. That error came from an early draft of this same finding and was caught before this branch was authored, but reached main by the other route. It is wrong in the expensive direction, because it recommends leaving a broken cleanup step alone; the paragraph now carries an explicit retraction pointing at the corrected entry. New entries: KI-BP-010 records the clean-mode workflows defect on its own so it can be picked up independently, with the verified manifest analysis and concrete evidence -- .leafcutter/workflows/ holds ten files against nine templates, and the extra one, pause-resume-substrate.js, is a real orphan that survives every --clean while the run reports success. It is cross-linked with KI-BP-008 in both directions, since that entry is the deploy-side counterpart for the same directory: between them workflows have neither a reliable writer nor a working reaper, and both failure modes print success. KI-DS-002 records that the doc conventions the Diataxis specialists require live in this repo's docs/ tree rather than templates/, so no build phase deploys them and closing KI-DS-001 would fix this repo while leaving every adopter install exactly as broken; the inline fix direction #520 put in KI-DS-001 is replaced by a pointer so there is one home for it. Finally KI-BP-005 gains two more instances of its class -- the workflows orphan above, and the observation that .leafcutter/config/doc_types.json in the self-hosted workspace was hand-placed as a KI-BP-003 workaround, is deployed by no build phase, and therefore masks the defect it was working around, making any local verdict on KI-BP-003 taken from that workspace vacuous. Documentation only; no code changes."
breaking: false
---

## Entry

Follows `#520`, which landed the bulk of this batch concurrently. Scope here:

- `docs/known-issues/build-pipeline.md` — retraction inside KI-BP-009; new KI-BP-010; two instances added to KI-BP-005; KI-BP-008 cross-link
- `docs/known-issues/documentation-system.md` — new KI-DS-002; KI-DS-001 fix direction replaced by a pointer
