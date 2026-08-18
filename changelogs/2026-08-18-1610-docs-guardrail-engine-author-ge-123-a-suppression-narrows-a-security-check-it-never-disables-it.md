---
title: "docs(guardrail-engine): author GE-123 — a suppression narrows a security check, it never disables it"
date: "2026-08-18"
time: 1610
type: manual
components: 
  - commit_guardian
  - ac_driven_dev
  - ac_store
summary: "Wrote down what the secrets scanner is supposed to guarantee, after finding three separate ways a single line can switch it off without anyone noticing. Also opened defect registers for three components, recording six problems found while using the tooling to do it."
description: "Authors the GE-123 acceptance-criteria tree (32 records, L0-L3) for the secrets scanner. No code changes; every record is readiness: reviewed, work_status: todo, awaiting a human approval and priority. Three routes to a disabled scanner were measured end-to-end through scan_files, the entry point the pre-commit check imports: one well-formed wildcard allowlist line takes three files holding 15 real credential findings to zero, silently (GE-113c-3-v closed the malformed spelling of this and deliberately preserved the literal wildcard, so the correctly-typed form survives); an env-named file short-circuits to a single filename finding without its contents ever being read, so suppressing that one finding takes five such files holding an AWS key, a private-key header, a password and a high-entropy token to zero findings and a clean exit; and an allowlist entry with a trailing inline comment parses successfully, can never match, and never warns. The tree is four L1s - a file is judged on its contents not its name; no suppression may take a file's coverage to zero; an entry that cannot match says so; documenting a risk is not committing one. The second was added against the request, because the env-file collapse is an instance of an unstated invariant and without it this becomes a fifth point-patch in an area that has had four. Also opens known-issues registers: commit-guardian gains KI-CG-004, recording that the prose exemption disables entropy detection for whole files and matches its path prefixes unanchored, so any path containing a tickets, retrospectives, acceptance-criteria or skills segment at any depth loses entropy detection - including the scanner's own source; ac-driven-dev gains KI-ACD-004 through 008 and ac-store gains KI-ACS-003, all found by running /plan-feature to author this tree."
pr: 483
breaking: false
---

## Entry
