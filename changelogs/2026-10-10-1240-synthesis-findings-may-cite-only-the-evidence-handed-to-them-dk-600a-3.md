---
title: "Synthesis findings may cite only the evidence handed to them (DK-600a-3)"
date: "2026-10-10"
time: "12:40"
type: manual
components: 
  - decision_kernel
summary: "When the host synthesizes findings for evidence the kernel handed over, a finding that cites any other evidence id, or cites nothing, is no longer accepted; each refusal is reported as a limitation. A synthesis handed no evidence keeps the old check, which drops an unknown citation and keeps the finding."
description: "Built through the fast lane (decision dec-ea83c3989d1b7199; the user chose the AC's strict rule over its older ticket). The lane's blocking review stopped the first version, whose refusal broke three tests and whose fallback refused every finding when no ids were handed; both were fixed and re-reviewed."
---

## Entry
