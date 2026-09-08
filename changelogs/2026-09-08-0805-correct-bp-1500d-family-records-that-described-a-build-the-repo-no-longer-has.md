---
title: "Correct BP-1500d-family records that described a build the repo no longer has"
date: "2026-09-08"
time: 0805
type: manual
components: 
  - ac_store
  - build_pipeline
summary: "Corrected six acceptance-criteria and known-issue records whose descriptions of build behaviour had been overtaken by two already-merged fixes, and added two new records for gaps the correction surfaced."
description: "Records-only change, no code. BP-1500d, BP-1500d-1, BP-1500d-3, and KI-BP-011 described producer/harness behaviour closed by PR #715 and PR #689; each was true when written and false when read. Corrections annotate the original text in place (e.g. BP-1500d's four VERIFIED EVIDENCE points marked \">> FALSE AS OF 2026-09-07\") rather than deleting it, so a fixed defect stays distinguishable from one that was never real. New records BP-1500d-1-ii (relative-\"../\" path escape) and BP-100k-3-ii (drift advice that cannot clear the gap it reports) were split out rather than folded into existing records."
commits: 
  - 6a7f21f7d3e47dcc7e1f4494cd8f063a9ef94e43
breaking: false
---

## Entry
