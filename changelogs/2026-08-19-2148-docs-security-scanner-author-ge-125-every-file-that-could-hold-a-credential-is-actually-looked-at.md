---
title: "docs(security-scanner): author GE-125 — every file that could hold a credential is actually looked at"
date: "2026-08-19"
time: 2148
type: manual
components: 
  - security_scanner
  - commit_guardian
summary: "Wrote down what the secrets scanner owes you when it decides not to look at a file. Today it skips whole files based on where they sit, including its own source code, and says nothing about it."
description: "Authors the GE-125 acceptance-criteria tree — 34 records, L0 through L3 — for the measured defect recorded as KI-SEC-001. No code changes; every record is work_status: todo awaiting a human approval and priority. ENTROPY_HIGH is the only rule that catches an opaque credential, and it is switched off for WHOLE FILES under four path prefixes matched as bare substrings, so any path containing a tickets, retrospectives, acceptance-criteria or skills segment at any depth loses entropy detection entirely — including templates/skills, which holds executable Python and the scanner's own scan_secrets.py. Four L1s: reduced checking applies where it was intended rather than to every folder sharing a name; code is always checked even where writing is allowed to be looser; one value judged harmless never takes the rest of the file with it; and you can see what the check chose not to look at. The fourth was added by the Product Owner against the brief and is the one that lasts — the exemption is entirely silent, which is what let this survive since the check shipped, and it keeps its value even if every remaining exemption turns out to be correct. Two decisions are recorded as OPEN and deliberately not settled: whether the admitted prose file kinds include .yaml, which decides whether this repository's own acceptance-criteria store is ever scanned for opaque tokens; and where the consolidated documentation passage lives, which decides whether documentation-expert or llm-expert writes it."
breaking: false
---

## Entry
