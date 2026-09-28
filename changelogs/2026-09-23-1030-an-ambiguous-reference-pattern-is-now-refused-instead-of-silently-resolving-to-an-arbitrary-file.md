---
title: An ambiguous reference_pattern is now refused instead of silently resolving to an arbitrary file
date: "2026-09-23"
time: "10:30"
type: manual
components: 
  - ac_store
summary: "_resolve_reference_patterns expanded an AC reference_pattern glob and, on two or more matches, silently took matches[0] with no length check. glob returns os.scandir order, so the file written into the generated ticket was arbitrary and non-deterministic while looking authoritative. It now raises ValueError naming the AC id, the pattern, and every match. The docstring already claimed exactly one match is required; the code now matches its own documentation."
description: "In scripts/ac_store/_gtfa_files_touched.py a len(matches) > 1 branch is added immediately after the existing zero-match branch, in the same shape, raising ValueError: AC <id>: reference_pattern <pattern> is ambiguous - it resolves to N files: [...]. Narrow the pattern in the AC so it names exactly one file. The docstring of _resolve_reference_patterns and of its caller _gtfa_body._build_implementation_notes_section are corrected: both previously documented only the zero-match raise. This closes the unmet clause of BO-2000c-3-i, filed twice before as pr-reviewer M-1 and M-3 on tickets/99_done/EPIC-BOPhantomDoneRemediation/05_bo2000_reference_pattern_resolution.md and independently predicted by an it-po amendment. Tests: unit_tests/prompt_assembly/test_reference_pattern_resolution.py adds five tests carrying covers tags for BO-2000c-3 and BO-2000c-3-i - the ambiguous-pattern raise asserting AC id, pattern and both matches; a single-match guard against over-correction; the real-artifact check that the resolved path reaches the ticket through the production generator CLI as a subprocess; and non-emission of any ## Implementation Notes section on both the zero-match and multi-match failure paths, which the pre-existing tests did not assert. Behavioural verification ran the production CLI in a fresh process against real on-disk AC records for all three match cases: single-match still resolves at exit 0, zero-match is unchanged, multi-match now refuses naming both matches where it previously emitted refmod_alpha.py. unit_tests/prompt_assembly is 153 passed, 142 subtests passed; ruff clean; validate_ac_schema reports all 1094 build-orchestration records valid."
breaking: false
---

## Entry
