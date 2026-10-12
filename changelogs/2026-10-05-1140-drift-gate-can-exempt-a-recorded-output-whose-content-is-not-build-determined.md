---
title: "Drift gate can exempt a recorded output whose content is not build-determined"
date: "2026-10-05"
time: "11:40"
type: manual
components: 
  - commit_guardian
summary: "check-output-drift now honours the exemption registry for a manifest-recorded output whose hash drifted, instead of always reporting it as a violation."
description: "Pass 2 of check_output_drift.py consults drift_gate_exemption_registry before recording a hash mismatch as drift. A recorded key with a valid, grounded entry is reported as DIRECT-DRIFT: EXEMPT <key> ground=<g>, counted in the RESULT line exempt field, and no longer blocks the commit. Previously the registry could only excuse an unregistered artifact, so a registered artifact that drifted had no way to be declared not-build-determined. The suppression is scoped to the individual key and requires a non-blank ground, so a groundless entry is rejected and its drift still blocks. Behaviour is unchanged for every current input: no live registry entry names an output_mappings key."
---

## Entry
