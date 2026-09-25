---
title: "Requirements for routing each IT-PO duty to the agent or script that can do it well"
date: "2026-09-25"
time: "15:30"
type: manual
components:
  - ac_driven_dev
  - testing_quality
summary: "Specifies (ACD-2500, 46 records) how the IT PO's duties are redistributed: deterministic rule checks move to a fail-closed post-write validator, the IT PO records only test intent, a new code-aware test-designer agent (Sonnet) writes the test design and checks the declared files before approval, and the IT PO's own profile stops claiming it changes nothing. Adds the 2026-09-25 analysis of why test writers prove a test can fail once but not that it discriminates, and amends six existing ACs the split invalidates. Specification only; no code changes."
description: "Covers ACD-2500 (L0) and L1s ACD-2500a-e, plus in-place amendments to ACD-1600c-1/-1-i/-3, ACD-200b-1, BO-2000d-1, BO-2000d-3 and ACS-100i-6-i, each with an amended_by record. Renumbered from ACD-2400 because PR #882 already claims that id. Four ACs (ACD-2500a-3, c-1-i, d-1, d-5-i) are held at reviewed until a declared-files schema AC is authored. Must land before the discrimination/must_catch work described in docs/analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md."
commits:
  - 4082fa27
  - 50c53aa3
  - 5ca9c163
  - b0644d23
  - 9e796a16
breaking: false
---

## Entry

The IT PO wrote the test contract for every code requirement while being barred
from reading source or tests, and spent much of its 1,014-line prompt on checks a
script can do the same way every time. ACD-2500 specifies the split: judgment calls
(routing, splitting, technical requirements, contracts) stay with the IT PO; rule
checks become a validator that fails closed; and the test design and file-surface
checks move to a new code-aware step that runs before approval.

The accompanying analysis explains why this has to come first: stating which wrong
implementations a test must catch can only be done by something that has read the
code.
