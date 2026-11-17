---
title: "Every retention verdict states which clock it measured age from"
date: "2026-10-15"
time: "02:00"
type: manual
components: 
  - knowledge_management
summary: "The knowledge retention evaluation now states, for every generation, the recorded time its age was measured from (retired_at, created_at, or undetermined), and a generation with no recorded time at all is never reported reclaimable."
description: "A generation that was never retired, which includes every failed publication, used to be aged from its creation time without the report saying so. Each verdict now carries age_basis (retired_at when the generation was retired, otherwise created_at, otherwise undetermined), age_seconds measured from that basis, and absent_times naming the missing times when the age cannot be determined. A generation carrying neither time is still reported, with reason age_undetermined, and is never reclaimable; it ranks after every dated generation. The declared count bound and minimum age are unchanged, and an unexpired pinned continuation still outranks the age. The retention reference documents the new fields and the added reason."
---

## Entry
