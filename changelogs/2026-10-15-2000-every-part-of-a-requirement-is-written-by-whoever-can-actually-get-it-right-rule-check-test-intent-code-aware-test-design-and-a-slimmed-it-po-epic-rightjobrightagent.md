---
title: "Every part of a requirement is written by whoever can actually get it right: rule check, test intent, code-aware test design and a slimmed IT PO (EPIC-RightJobRightAgent)"
date: "2026-10-15"
time: "20:00"
type: manual
components: 
  - ac_driven_dev
  - ac_store
  - agent_registry
  - build_pipeline
summary: "/plan-feature now checks every authoring stage with a deterministic requirement rule check, the IT PO records only per-clause test intent, a new Sonnet test-designer writes the test design and file findings from the code before the approval gate, and the IT PO prompt keeps only its own job."
description: "G1: an implementation-readiness gate with one closed hold-reason list, the one surface-to-specialist map (config/surface_craft_map.yaml), and generated tickets whose files_touched comes from the AC's declared_files (ADR-010 amendment). G2: scripts/ac_store/requirement_rule_check.py runs after every /plan-feature authoring stage, finds the stage's records from git, repairs back-links, components and readiness through one guarded writer, reports contract symmetry, documentation triggers, specialist versus surface and declared files versus modifies links, fails closed, and a rewrite that passes pauses again for approval. G3: test_intent (ADR-071) replaces planner-written test contracts; intent without a design is held as 'test design pending' at approval (approve_acs.py --json), the readiness gate, the ticket generator and the commit check; legacy designs are kept. G4: the test-designer agent (ADR-072) runs as a new stage after the IT PO: a deterministic design pre-pass, one dispatch for the test design (proves_clause, authorship mark, reachability entries) and file findings, a hold report, and up to two hand-back rounds of undecided findings to the IT PO; new rule families check design grounding and file findings. G5: it-po.md drops the duties the rule check, the map and the test-designer now own, gains a pointer to the rule check, sets the 'reference file pending' marker, and its profile says it produces requirement_records; an advisory build check flags write-capable agents that claim to change nothing. plan-feature.js shrank from 2,819 to 2,646 measured lines by moving rationale comments verbatim into docs/reference/plan-feature-workflow-rationale*.md."
breaking: true
migration_steps: 
  - Rebuild every install (python scripts/build.py) so the new agent (test-designer), the slimmed it-po prompt, the rule-check scripts and the plan-feature workflow are deployed.
  - Re-run any /plan-feature run that was paused at the old IT-PO final gate: the final gate now belongs to the test-design stage, so such a pause cannot be resumed.
  - New approved leaf code requirements need a test design from the test-designer; a record with test_intent and no test_spec is held as 'test design pending' until the design stage runs. Existing records with a planner-written test_spec are kept as legacy designs and need no change.
  - Agent registries that validate produces against the closed list must accept the new value requirement_records.
---

## Entry
