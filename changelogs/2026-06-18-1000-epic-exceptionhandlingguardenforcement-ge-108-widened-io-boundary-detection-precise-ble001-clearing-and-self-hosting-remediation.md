---
title: "EPIC-ExceptionHandlingGuardEnforcement (GE-108) - Widened IO boundary detection, precise BLE001 clearing, and self-hosting remediation"
date: "2026-06-18"
time: "10:00"
type: epic_completion
components: 
  - commit_guardian
  - precommit_hooks
summary: "Hardened the exception-handling pre-commit guard to detect unwrapped subprocess calls as mandatory I/O boundaries, enforce genuine WARNING+ logging as the only valid BLE001 clear, and render full multi-type except tuples in violation messages; 11 previously-unwrapped subprocess calls in 6 production scripts were remediated so the guard produces no false positives on its own codebase."
description: "PR #104 (squash-merge commit 2b086f6), 4 sub-tickets. GE-108a: subprocess.run/Popen/call/check_call/check_output/getoutput added to io_boundary_calls in commit_guardian.json and to the IO-001 detection set in check_exception_handling.py (Rule 1 parity). GE-108b: BLE001 clearing tightened from name-coincidence to AST attribute resolution - only WARNING/ERROR/CRITICAL/EXCEPTION calls on a real logger object clear the violation; replaced _LOG_CALL_NAMES with _WARNING_LOG_METHODS (Rule 3 precision). GE-108c: violation messages for multi-type except clauses now render the full tuple e.g. (ValueError, Exception) instead of collapsing to Exception. Self-hosting: 11 subprocess calls across 6 production scripts wrapped to eliminate IO-001 noise on leafcutter own code. ADR-014 documents the enforcement scope decision."
epic: "EPIC-ExceptionHandlingGuardEnforcement"
pr: 104
adrs: 
  - ADR-014
commits: 
  - 2b086f6
breaking: false
---

## Entry
