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
description: "Registers security_scanner in docs/components.json with an architecture doc at docs/architecture/components/security-scanner.md, and adds it to the components list of the 42 ACs whose subject is what the scanner detects, what a suppression may remove, or whether the scanner runs at all. commit_guardian is preserved on every one - components is a membership list, not an ownership claim. Three framework-wide records were deliberately excluded (GE-113c-1, GE-113c-1-iv, GE-118): their subject is a property of every guard, with check-secrets appearing only as the instance that exposed it. The entry declares depends_on: [commit_guardian] rather than a parent key - the registry has no parent field and models no hierarchy, but depends_on is a real validated edge, so that is the honest shape. Only one of the two component axes gains an entry - docs/acceptance-criteria/index.yaml governs AC file placement and id prefixes, so a new namespace there would renumber every existing GE- record; scanner ACs stay in guardrail-engine. Three defects were found while doing this and are filed rather than worked around. KI-CG-007 (new): scripts/add_component.py writes an entry that check-components-integrity rejects, the gate's printed rule is weaker than the contract it enforces so following the error message still fails, all 42 legacy entries are grandfathered out of the new fields so there is no precedent to copy, and nothing in the registry owns the registry. KI-ACS-007 (occurrence 2): the component vocabulary has a THIRD copy, a hand-transcribed enum in config/ac_store_schema.json - check_component_vocab.py reported full-tree success while validate_ac_schema.py rejected all 42 records. KI-CG-001 (occurrence 2): two approved code ACs have never had a test contract and nobody could see it, because the hook only inspects files a commit happens to stage; they are left unlinked rather than silently patched."
breaking: false
---

## Entry
