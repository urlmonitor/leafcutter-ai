---
title: "EPIC-ACCodeTraceabilityGraph — AC-to-code traceability in knowledge map (KM-KGS-100)"
date: "2026-06-24"
time: "12:00"
type: epic_completion
components: 
  - knowledge_system
  - research_analysis
  - ac_store
  - testing_quality
summary: "Released AC-to-code traceability for the knowledge map, enabling any requirement to be traced to the exact code and tests that fulfil it."
description: "100 commits spanning the EPIC-ACCodeTraceabilityGraph epic (de03c16..HEAD, merged as PR #132). Key changes: acs surface ingestion in knowledge_query.py (AC YAML files become graph nodes), four new edge types (implemented_by, covered_by, depends_on, component_membership), data-driven surface set from config/paths.json, new build_knowledge_map() / validate_knowledge_map() / validate_edges_integrity() public APIs, phantom/missing-target edge pruning, --list-surfaces CLI flag, rose-coloured acs node rendering in visualise_knowledge_graph.py, two new how-to guides, C4 component + sequence diagrams in knowledge-system.md, and unit test coverage in test_knowledge_query.py and test_ac_edge_relationships.py. ... and 50 more commits covering supporting infrastructure (guardrail fixes, test repairs, AC store scaffolding, build pipeline improvements)."
epic: "EPIC-ACCodeTraceabilityGraph"
pr: 132
diagrams: 
  - docs/architecture/components/knowledge-system.md
commits: 
  - 99669311
  - b732c4fe
  - 5e4f58ad
  - a77bc104
  - 9f6a1ac4
  - 928691b9
  - b5b728c1
  - 28f710a3
  - 92389618
  - 955a4ab7
  - 114b3d34
  - d90f2b7b
  - ad7f8e74
  - e59b1eaf
  - 6ae02d27
  - e76e7fcb
  - 96eed737
  - d90713b1
  - 83737a44
  - 7f6b761a
  - 19840a91
  - aa84cd43
  - 71f08082
  - e6f34ad2
  - 34a55417
  - 305b4f47
  - b9eaab4b
  - a40946dd
  - fd35bd34
  - df24af2a
  - 2f138467
  - 963f9edb
  - db84dfb2
  - dd7838f9
  - cdf263a7
  - c0d9bca4
  - 51ef30ac
  - 36dae57f
  - 19b618c8
  - 51ce20ad
  - 46e288d8
  - 23226662
  - 2197e83f
  - 63df0019
  - da8107f2
  - 1647e7cd
  - f6149249
  - 24f45e79
  - 6d763daa
  - 120036d6
breaking: false
---

## Entry
