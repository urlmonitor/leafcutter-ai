---
title: "Finished L0, L1 and docs-only composites that the done gate proves leave the untagged-done count, under a ground that says tests were not run"
date: "2026-11-16"
time: "17:00"
type: manual
components:
  - ac_store
  - knowledge_management
summary: "KM-ADM-005-3. The untagged-done ratchet counted a composite as untested although the done gate proves it through its children. It now leaves 47 such composites out under a fourth ground, 'proved through its children (tags read, tests not run)'. The mark drops from 209 to 162."
description: >-
  scripts/ac_store/untagged_done_count.py gains the ground GROUND_PROVED on
  PUBLISHED_GROUNDS and the bucket order tagged, superseded, waived, proved
  through its children, untagged. A finished record with no tag of its own
  leaves the count under the new ground only when (a) the done gate's own
  _done_proof_composite._unproven_composite_children, looked up when the ratchet
  runs and given the ids found by the gate's COVERS_TAG_RE, finds no unproven
  child; (b) its covered_by lists every live record on disk whose parent field or
  id-derived parent is the record; (c) it is level L0 or L1, or its change_target
  is docs. Code, schema, pipeline, config and prompt L2 composites stay counted,
  so the ratchet is stricter than the gate there by design. The ground says the
  children's tags were read and their tests were not run. The measurement carries
  the excluded ids, sorted, and the ratchet prints them beside the ground's count
  on every run, with the number of records related to a parent only through the
  parent field. The store is read once per run and the gate rule resolves
  children from an index, so the live ratchet runs in about 13 s. Measured
  2026-11-16 on 32e6aa89f: 1859 finished, 1613 tagged, 162 untagged, 84 excluded
  (3 superseded, 34 waived, 47 proved through children). HIGH_WATER_MARK 209 -> 162.
  The done gate (check_done_proof.py, done_proof.py, mark_ac_done.py,
  _done_proof_composite.py) is not changed.
breaking: false
---

## Entry
