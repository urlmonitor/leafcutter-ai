---
title: "The graph sync job is given enough time to finish writing"
date: "2026-10-09"
time: "17:40"
type: manual
components: 
  - knowledge_management
summary: "The job that publishes the knowledge graph was running every database write under a three-second limit meant for quick reads, so a publication could never finish. It now gets the same allowance every other writer already had."
description: "Publishing the knowledge graph writes roughly nine thousand eight hundred records and twenty-six thousand connections, spread over about a hundred and sixty-five separate database transactions, and then stamps every one of them again when the new version is made current. All of that was running under a three-second-per-transaction limit, which is a sensible allowance for answering a single question and far too short for writing a whole version. The database said so directly once its error was no longer being discarded: the transaction was terminated for exceeding the timeout the client set, with the suggestion to retry using a longer one. Every other writer in the system had already raised that allowance to thirty seconds; this one, the only writer that had never completed a publication, had been left at the default. It now uses the same thirty seconds, which is also the highest the connection layer permits, recorded as a named value next to the reason it exists rather than as a bare number."
---

## Entry
