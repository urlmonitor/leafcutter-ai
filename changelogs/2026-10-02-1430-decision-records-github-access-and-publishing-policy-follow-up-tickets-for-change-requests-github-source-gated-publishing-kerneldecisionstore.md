---
title: "Decision records: GitHub access and publishing policy; follow-up tickets for change requests, GitHub source, gated publishing (#KernelDecisionStore)"
date: "2026-10-02"
time: "14:30"
type: manual
components: 
  - decision_kernel
summary: "Publishes two decisions the user approved through the kernel (dec-4673055ef54113d5: a native read-only GitHub source for the facts decisions rest on, non-read actions stay host work; dec-acdfd972fcaca478: publish approved decisions directly when the gates pass and the decision is not risky, through a PR flow copied from finalize-feature, which needs an ADR-060 amendment) and files the follow-up tickets."
description: "Tickets: KernelChangeRequestsWithProcessMining (change requests are recorded against missing-process gaps and handed to the host, then a process-mining step records the host's decisions and steps), KernelGitHubSource, KernelGatedDirectPublish (ADR-060 amendment plus a publish PR flow derived from finalize-feature.js) and KernelWallClockScanTest (a scan-cost test asserting wall-clock seconds). decisions validate: 6 records."
---

## Entry
