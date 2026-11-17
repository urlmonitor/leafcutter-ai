---
title: "The knowledge retrieval command no longer reports a false unavailable and now honours its deadline (KM-400d-4)"
date: "2026-10-23"
time: "12:00"
type: manual
components: 
  - knowledge_management
summary: "The knowledge retrieval command now answers on its first call from WSL2 machines instead of falsely reporting the graph store unavailable, stops waiting when its deadline passes, and reports where its time went."
description: "KM-400d-4-i: the graph database adapter asks for IPv4 first for its own name lookups and falls back to the normal lookup; other programs are unchanged; opt out with LEAFCUTTER_NEO4J_ADDRESS_FAMILY=any. This fixes the false unavailable on WSL2 with DNS tunneling and a corporate DNS suffix list. Measured against the live graph store on 2026-10-23: a fresh call finished in 0.96 s, where it previously failed after the 10 s deadline (about 20 s of name lookup). KM-400d-4-ii: when deadline_ms passes, the command prints its answer and exits within about a second, even if a name lookup, connect or close is stuck. Measured with the opt-out set: 10.5 s total for a 10 s deadline, where it previously took 32 s. KM-400d-4-iii: results report stats.resolve_ms, connect_ms, query_ms and resolve_from_memory separately, and stats.deadline_step names the step a deadline miss happened in. KM-400d-4 is done again: its deadline clause is now true on the real command."
breaking: false
---

## Entry
