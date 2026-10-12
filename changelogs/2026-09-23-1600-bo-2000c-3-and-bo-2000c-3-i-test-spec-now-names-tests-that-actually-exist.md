---
title: "BO-2000c-3 and BO-2000c-3-i test_spec now names tests that actually exist"
date: "2026-09-23"
time: "16:00"
type: manual
components: 
  - build_orchestration
summary: "Both records described a test contract pointing at unit_tests/ac_store/ with descriptor names matching no test anywhere in the suite. Corrected to the seven real, passing tests in unit_tests/prompt_assembly/ that carry the matching covers tags."
description: "The test_spec on BO-2000c-3 and BO-2000c-3-i was authored on 2026-09-22 and had gone stale in two ways. Every descriptor targeted unit_tests/ac_store/ while the covering tests live in unit_tests/prompt_assembly/ - that directory does exist, so the wrong target read as plausible. And a grep of all eight descriptor names across unit_tests/ returned nothing: only one of the eight, test_pattern_matching_more_than_one_file_raises_an_authoring_error, named a real test. Both records are work_status done against tests that genuinely pass, so the concrete harm was that the next agent to read the spec literally would author eight new tests in a second directory, duplicating seven that already pass. BO-2000c-3 now names three tests and BO-2000c-3-i four, matching their covered_by lists exactly. Three descriptors were removed rather than renamed because their behaviour is covered under a differently-shaped test: the raw-glob-absence Then and the resolution-ordering seam are both asserted as assertNotIn inside the surviving tests, and the error-names-ac-id-and-pattern check is asserted inline by both failure tests. One descriptor was split in two, the non-emission clause being proven separately for the zero-match and multi-match paths, and retyped from unit to integration since both drive the generator CLI as a subprocess. No name was invented for an untested behaviour. framework, type and angle values were checked identical in config/ac_store_schema.json and config/test_requirements.schema.json. All seven named tests were run and pass; validate_ac_schema.py reports OK on all 1101 files in the directory. criteria, work_status, readiness, priority, implemented_by and covered_by untouched on both records; no test file was written or moved."
breaking: false
---

## Entry
