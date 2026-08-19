---
title: "feat(components): register security_scanner and link the 42 ACs that govern it"
date: "2026-08-19"
time: 1042
type: manual
components: 
  - security_scanner
  - commit_guardian
  - ac_store
summary: "Secrets scanning is now a named component you can ask questions about, with its own architecture doc, and the 42 acceptance criteria that govern what it detects are attached to it."
description: "Registers security_scanner in docs/components.json with an architecture doc at docs/architecture/components/security-scanner.md, and adds it to the components list of the 42 ACs whose subject is what the scanner detects, what a suppression may remove, or whether the scanner runs at all. commit_guardian is preserved on every one - components is a membership list, not an ownership claim. Three framework-wide records were deliberately excluded (GE-113c-1, GE-113c-1-iv, GE-118): their subject is a property of every guard, with check-secrets appearing only as the instance that exposed it. Registered as a SIBLING of commit_guardian rather than a child: docs/components.json is flat, has no parent field, and none of its 42 existing entries declare one, so the containment is recorded in the architecture doc rather than modelled by adding a key nothing validates. Only one of the two component axes gains an entry - docs/acceptance-criteria/index.yaml governs AC file placement and id prefixes, so a new namespace there would renumber every existing GE- record; scanner ACs stay in guardrail-engine. Adding the component also required editing a SECOND, hardcoded copy of the vocabulary in config/ac_store_schema.json: check_component_vocab.py reads components.json and passed immediately, while validate_ac_schema.py validates against its own enum and failed on all 42 files - a live instance of the two-vocabularies drift recorded as KI-ACS-007."
breaking: false
---

## Entry
