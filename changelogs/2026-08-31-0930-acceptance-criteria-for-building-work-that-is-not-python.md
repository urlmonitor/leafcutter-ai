---
title: Acceptance criteria for building work that is not Python
date: "2026-08-31"
time: "09:30"
type: manual
components: 
  - build_orchestration
  - ac_driven_dev
summary: "A new BO-3500 tree for making the automation able to produce every kind of deliverable, and two amendments that stop a fourth artifact vocabulary being minted."
description: "The fast lane builds only work assigned to python-coder or test-writer; everything else gets a clean pre-work refusal. That refusal is correct and stays. 660 not-yet-done criteria declare a producer outside that roster, and because build sets are resolved rather than chosen, one such child takes its whole subtree. BO-3500 (L0 + 4 L1 + 14 L2 + 11 L3) owns making the refusal rare. Separately, ACD-1800a-1 proposed a five-value kind enum that would have been the fourth overlapping artifact vocabulary in the repo; it and ACD-1800a-3 are amended to reuse the existing change_target vocabulary plus one new value, and to drop tests as a deliverable kind."
---

## Entry

`BO-2400f` already promises what an operator wants: *"One command, one AC id — a PR back, or an up-front reason why not."* What it deliberately does not promise is that the first ending is the common one. A 2026-08-24 amendment replaced a false promise with two honest endings, and `BO-2400f-12` shipped the refusal. Nothing owned making the refusal rare.

Measured: **660 not-yet-done criteria declare a producer the roster does not contain** — prompts 463, pages 152, diagrams 119, screens 80, and a tail. Because build sets are *resolved* rather than chosen, one such child anywhere takes its whole subtree with it, so the share of refused starting points is higher than the share of unbuildable records.

`BO-3500` is a new sibling L0 rather than a child of `BO-2400`, because both candidate parents are at their hard cap and both say in writing that the next child must force a split rather than another override bump. No `child_limit_override` was added anywhere in this tree.

### The vocabulary decision, which was the harder half

`ACD-1800a-1` proposed a deliverable checklist whose `kind` was one of `{code, tests, docs, diagram, config}`. Two independent reviews converged on the same objection: that would be the **fourth** overlapping artifact vocabulary in this repository, and the two that are supposed to be identical — `change_target` as shipped in the schema, and `change_target` as documented in ADR-017 — already disagree.

The repo has paid for this exact failure before. EPIC-ComputedQualityGates FP-1 was a hook's `ALLOWED_CHANGE_TARGETS` and `guardrail_gates.yaml`'s keys being **disjoint** vocabularies, each tested against its own copy.

So: reuse `change_target`. It already carries `ui`, `prompt` and `schema`, and it is already on **3,381 of 3,694 records** — live counts include prompt 449, docs 260, config 90, schema 73, ui 10. Add `diagram`, the one value genuinely missing. Drop `tests`.

**Dropping `tests` is not tidying.** It is a proof, not an artifact — the lane's red-baseline check already *is* the differential applied to a code deliverable. And with `ACD-1800b-1a`'s independent per-deliverable sign-off slots, a `tests` kind lets one record hold a signed-off code deliverable beside an unstarted tests deliverable: a code deliverable declared finished with its own proof unwritten. That is the phantom-done shape, encoded in the very field meant to prevent it.

`ACD-1800a-3` was the more dangerous carrier and is amended too: its criteria had the reference documentation *define* the list, and its technical fields designated that section as the **single normative definition the schema and the signoff skill both mirror**. The wrong list would have propagated, and every copy would then have been correct-by-construction against it. It now defines no list — it points at the vocabulary the store already uses.

The anti-drift mechanism is a test rather than a convention: resolve the checklist's kind enum and `change_target` through their `$ref`s and assert the first set **equals** the second union `{diagram}`; then add a value to the shared definition in memory and assert **both** references reflect it. A duplicated literal fails; a `$ref` passes.

### Diagrams move to structured source, which makes their proof cheaper

`diagram` earns its place for a reason that also settles how it is proved: diagrams are moving to a JSON foundation. A structured source is schema-validatable, so the proof needs **no renderer** — it is a valid source plus every named element resolving against the parts, crafts and skills registers.

That matters practically: there is no `mmdc` binary and no root `package.json`, and a portable package installed into arbitrary repos cannot assume node. It is also an extension of something already running — `check_agent_spawn_consistency.py` parses the spawn diagram in the agent cards and compares its edges against the registry in both directions, for one diagram family.

`diagram` is therefore a distinct authoring **kind** but not a distinct **instrument**: the same reading-class check, parameterised by a per-file-type reference extractor.

### The receipt, which is the load-bearing idea

The obvious failure of "prove each deliverable appropriately" is that a lazy implementation gives everything the cheapest proof. An exhortation does not stop that. A **shape** does.

Proof is recorded as a receipt whose structure discriminates by class. A comparing proof carries both conditions and the observed difference; a reading proof carries **none of those fields at all**. A comparing receipt whose two conditions are equal is rejected at write time, and so is a reading receipt that carries a second condition. There is no `class` field to set — the class is derived from where the deliverable lives and which registry claims it, so a reader tells the class from the shape and an author cannot choose it.

Both rejections are pure shape checks over a candidate record: no run, no fixture, no environment. They are the cheapest real tests in the tree.

### Two corrections to earlier assumptions, both verified

**The screen proof is affordable today.** An earlier draft said it needed a running surface. It does not: `vitest`, `jsdom` and `@testing-library/react` are installed, real component tests exist, and `done_proof.py` already scans `.tsx` for `// covers:` tags. What is genuinely unaffordable is anything requiring a live HTTP server — `live_surface_testing` is disabled by default, deliberately, because a portable package must not require consumers to run servers.

**The prompt proof is the expensive one, not the screen.** 463 records declare `llm-expert`; three of sixty agents have eval sets. A separate measurement puts 165–225 of the not-done records in the model-only bucket — but they land on roughly **33 prompt files**, not 225 individual sets, and about 78 of them share one harness shape the repo has already built twice.

### Left open, deliberately

The page-reachability clause was corrected off `docs/INDEX.md`, which `build.py` regenerates in the same run — the proof and the thing proved would have shared a producer.

Twenty-four records name `finalize-feature-workflow` or `create-ticket` as their craft; neither is a registered agent, so all twenty-four will fail the craft-resolution rule the moment it is enforced. Reclassifying them is a product decision and is not done here.

Everything in this tree is `readiness: draft`. Nothing is approved, and no implementation is authorised by it.
