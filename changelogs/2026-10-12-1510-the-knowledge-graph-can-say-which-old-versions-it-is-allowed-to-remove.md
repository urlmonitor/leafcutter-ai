---
title: "The knowledge graph can say which old versions it is allowed to remove"
date: "2026-10-12"
time: "15:10"
type: manual
components: 
  - knowledge_management
summary: "A retention limit is now something you state rather than something buried in the code, and a new command reports which stored versions that limit permits removing, and why each of the others is kept."
description: "The knowledge graph keeps a complete copy of the project every time it is published, and until now the rule for how many copies to keep was a single hidden value inside the code that nobody could see or set. There is now a stated limit with two parts, a maximum number of versions to keep and a minimum age before one may be removed, and both must be given together. Leaving either out is refused by name, and nothing falls back to a built-in number. A new command reports the limit it read, where it read it from, and a verdict for every stored version with the reason behind it: it is the one in use, it is within the number you said to keep, it is younger than the age you set, or something is still reading it. Everything else is reported as removable. The report only reports. It removes nothing, moves nothing and expires nothing, and the separate removal command now also requires you to state the age it should judge against. Two limits of this first step are written into the documentation rather than left to be discovered. The reason that protects a version something is still reading cannot yet fire against a real database, because the value it reads is not written anywhere yet, so a reading in progress does not protect a version today. And the report only considers versions that published successfully. The copies that twice filled the database to the point where it stopped accepting writes came from publications that failed, and those are not yet in view, so this step does not on its own prevent that happening again."
---

## Entry
