---
title: "Fast-lane AC edits stop reformatting the store, and the red-baseline reason stops lying"
date: "2026-08-18"
time: "19:30"
type: manual
components: 
  - build_orchestration
summary: "Marking an acceptance criterion claimed or done now changes one line of its file instead of rewriting the whole record, so review diffs show the actual change."
description: "Fixes KI-BO-003 and KI-BO-004, and adds the acceptance criteria for the fast lane's missing review step. KI-BO-003: _update_ac_work_status round-tripped every AC YAML file through yaml.safe_load then yaml.safe_dump to change one field, which alphabetised all top-level keys, reflowed hand-authored 'criteria: |' and 'notes: |' block scalars into escaped folded strings, and dropped comments; TKT-600a-1.yaml changed 161 lines for what was semantically 'work_status: todo to done'. It now performs a targeted edit of the single column-0 work_status line, anchored at column 0 so the literal string work_status appearing inside indented block-scalar prose is never mistaken for the key. Verified against every one of the 3155 real AC files in the store: worst-case two changed lines, TKT-600a-1.yaml included. An AC with no work_status line gains one rather than raising, because 143 of those 3155 records genuinely have no such key and the previous round-trip added it silently; refusing them would have crashed the lane on 4.7 percent of the store. Two or more column-0 matches still raise, since which line is the real key is then genuinely ambiguous. KI-BO-004: TEST_WRITER_SCHEMA declared reason as string-only while verify_red_baseline returns None on a passing gate, so the agent coerced it and the journal recorded the four-character string 'null' - truthy, and matching no named halt reason. The schema now accepts null, pinned by a test that calls _red_baseline_verdict and asserts the None survives, so the JS declaration cannot drift from what Python emits. Also adds BO-2400f-11, which requires the lane to submit its working diff to the existing pr-reviewer agent before the commit step rather than after, blocking only on findings pr-reviewer itself classifies high-confidence so reviewer noise cannot halt a green run, and treating an unobtainable verdict as no review rather than a clean one."
commits: []
breaking: false
---

## Entry
