---
title: "The post-merge hold check fails and says why when it cannot read the run history"
date: "2026-10-12"
time: "10:00"
type: manual
components: 
  - testing_quality
summary: "When the Post-merge suite status check cannot read the workflow or its run history it now fails with \"Post-merge run history could not be read\" and the cause, retries a temporary failure once, and never lets a failed side read or write change the verdict."
description: "A check that could not look must not look like a check that found nothing. When the hold cannot read the post-merge workflow's state or its run history - refused, not found, rate-limited, a server error, a timeout, a dropped connection, or a reply in an unexpected shape - it now fails with \"Post-merge run history could not be read\" and names the cause. Rate limits, server errors, timeouts and dropped connections are retried once after a short delay (honouring Retry-After, capped); refusals, not-found, certificate errors and malformed replies are not. Every request has a bounded, configurable timeout of about ten seconds. Reads and writes on the held path - the run's job results, the notice issue, the fix proof, the pull-request comment and the exemption record - never change the verdict: a held pull request stays held, a failed proof read grants no exemption, and the output notes what could not be read or written. If the run's job results cannot be read, the run is reported as not completed with an unknown stage, and a proven fix can still be exempted. A pull request from a fork gets exactly the same verdict."
---

## Entry
