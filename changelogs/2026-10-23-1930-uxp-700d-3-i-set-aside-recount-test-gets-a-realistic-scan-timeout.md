---
title: "UXP-700d-3-i set-aside recount test gets a realistic scan timeout"
date: "2026-10-23"
time: "19:30"
type: manual
components: 
  - ux_prototyping
summary: "test_uxp_700d_3_i gives its whole-store scan_ac_store.py run 300 s instead of 30 s, so the required pytest check stops failing on a slow runner."
description: "The test runs scan_ac_store.py --json over the whole AC store (about 5,300 records). On 2026-10-23 it timed out at 30 s on CI shard 7 on main (run 39998207313) and on every PR run checked that day (#1297, #1317, #1322, #1333), blocking merges; the scan measures 44-58 s locally. Timeout raised to 300 s, matching the BP-100k-4-iii build-timeout fix (#1331). Tracked as KI-UXP-20261022."
---

## Entry
