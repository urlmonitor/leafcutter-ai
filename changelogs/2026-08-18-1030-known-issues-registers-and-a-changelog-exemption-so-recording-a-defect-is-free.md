---
title: "Known-issues registers, and a changelog exemption so recording a defect is free"
date: "2026-08-18"
time: "10:30"
type: manual
components: 
  - build_orchestration
  - build_pipeline
summary: "Added a lightweight per-component register for recording known defects, so a bug noticed in passing can be written down in seconds instead of being lost."
description: "Introduces docs/known-issues/<component>.md — a plain markdown register of observed-but-unfixed defects, read before adding new capability to that component. The first register, docs/known-issues/build-orchestration.md, records six defects found while dogfooding the fast-lane build: the lane writes no changelog entry so every fast-lane PR is unmergeable (blocker); mark_done leaves implemented_by empty so ACs are marked done with no provenance; claim/mark_done round-trip AC YAML through yaml.safe_dump, turning a one-field change into a 161-line diff; the gate's reason field serialises as the string 'null'; injection_builders.py is invoked as a CLI but defines no argparse or __main__, so the call is a silent no-op; and fast-lane-build.js is deployed but orphaned. Each entry carries an Occurrences counter so a recurring defect escalates without a duplicate entry, with the explicit rule that occurrences escalate but do not rank. Also exempts docs/known-issues/ from the changelog-presence CI gate: recording a defect ships nothing, and requiring a changelog entry to write one down is the kind of friction that already killed debugging/logs/feedback.jsonl (131 entries, none since 2026-07-20). A changelog entry is still required for the commit that fixes an issue, since that necessarily touches non-exempt code."
commits: 
  - 9e318c34c
  - dc85078a9
breaking: false
---

## Entry
