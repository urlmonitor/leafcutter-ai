---
title: "Infrastructure: submit_feedback names the file each record went to"
date: "2026-10-08"
time: "20:08"
type: manual
components: 
  - infrastructure
  - feedback_collector
summary: "Every successful feedback submission now prints '[submit_feedback] sink: <absolute path>' on stderr, so you can see which feedback.jsonl a record landed in."
description: "Agent feedback has been landing in 18 different feedback.jsonl files, and nothing at the call site said which one, so the split looked like 'agents are not writing feedback'. submit_feedback.py now writes one extra stderr line on success naming the resolved absolute file the record was appended to. The feedback id on stdout is unchanged, and the sidecar id-recovery line on stderr is unchanged and still the only match for the signoff skill's recovery grep. Where the sink resolves is not changed here; one declared sink per install is separate planned work. AC INF-500d-4-ii, known issue KI-FC-001."
commits: [37d492452]
breaking: false
---

## Entry
