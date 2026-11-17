---
title: "A finished parent is no longer refused because one of its parts was superseded (KI-ACS-016)"
date: "2026-10-14"
time: "17:30"
type: manual
components: 
  - ac_store
summary: "The done-proof check no longer refuses a finished parent just because one of its parts was superseded; a parent whose parts are all superseded is still refused."
description: "One commit (5f0c328). done-proof now skips superseded parts (superseded_by set, or req_status superseded) on both the commit-time and CI paths; a parent with no live part left, or with a live part not done, is still refused. KI-ACS-016 moved to resolved. Links to the resolved KI-FC-001 record corrected in INF-500d-4 and six child records. The reachability-gate code moved verbatim from done_proof.py into _done_proof_reachability_gate.py (done_proof.py re-exports the names), added to the deploy map."
commits: 
  - 5f0c3287c3b787e8e91b5406ac7090d3e3bc0da3
breaking: false
---

## Entry
