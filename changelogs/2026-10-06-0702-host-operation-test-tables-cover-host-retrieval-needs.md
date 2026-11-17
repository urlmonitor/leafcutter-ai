---
title: "Host-operation test tables cover host.retrieval_needs"
date: "2026-10-06"
time: "07:02"
type: manual
components:
  - decision_kernel
  - testing_quality
summary: "The kernel's host-operation test tables now include the experiment-only host.retrieval_needs operation, so test_every_host_capability_of_the_design_has_an_operation passes on main again."
description: "host.retrieval_needs was added to OPERATIONS in #1009 without the matching test-support rows. The tables (host_support.py, host_rigs.py) gain its request, schema and rig rows; it stays out of config/capability_registry.json, so the registry-binding test skips the experiment-only set while the OPERATIONS == SCHEMAS assertion is unchanged. Removes baseline failure row 1 before DK-400c-1 extends this file (decision dec-9925ebf1895222f4)."
---

Test-support change only; no runtime code changed.
