---
title: "A project gets a product-truth record on install, and a check that says what it actually checked"
date: "2026-09-09"
time: "20:14"
type: manual
components: 
  - ux_prototyping
  - build_pipeline
  - precommit_hooks
summary: "Installing leafcutter now creates the product-truth record itself, the checker reports what it examined instead of staying silent, and each journey is described once."
description: "Nine acceptance criteria from EPIC-TruthfulProjectRecord, all in service of one property: a green product-truth check should mean the record was actually checked. INSTALL — build.py now scaffolds docs/product-truth/ into every install: flows/, mock-data/ and mockups/, an index declaring zero artifacts with every derived lookup present and empty, the checker's classifier/eval.jsonl start-up input, and a written introduction naming each artifact type and the first thing to author. Write-if-absent, so an already-populated record is never overwritten. The build now also verifies by name that every file the checker opens before checking begins was really installed, and fails naming the missing one rather than finishing green having deployed a checker that cannot start. REPORTING — the run states how many AC pointers it resolved (zero included), names which artifact types held zero records, names every journey it skipped as unreadable, and prints all of it as one machine-readable stdout line. A malformed journey is skipped and named rather than crashing the read; a check whose input was never installed now blocks, while one whose input simply has not been authored yet stays open. DESCRIPTION — each journey's index summary is derived from the journey's own summary on every run instead of being separately hand-typed beside it (14 were), and a stored copy that diverges is reported naming the journey and both texts. Journey summaries also gain a 120-character bound tied to a new optional shape_version, so a journey declaring version 2 or later is held to it while everything written before is warned about and not blocked. SEPARATION — mock product truth stays addressable by name but is never counted in the host project's own record: product_ownership.py reports own_record_count and set_aside_count over a store, keying ownership on the product root rather than the journey's component field, which in the real store names the architecture component a journey documents and would have filed all three fern-and-fig journeys into leafcutter's own record. Two contradictions between approved ACs were found along the way; one is resolved and documented, the other is filed as KI-ACD-20260909-2130 and needs a product decision."
commits: 
breaking: false
---

## Entry
