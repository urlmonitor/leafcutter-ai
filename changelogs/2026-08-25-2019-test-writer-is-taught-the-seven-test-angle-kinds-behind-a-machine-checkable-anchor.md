---
title: "test-writer is taught the seven test-angle kinds, behind a machine-checkable anchor"
date: "2026-08-25"
time: "20:19"
type: manual
components:
  - build_pipeline
  - testing_quality
  - llm_authoring
summary: "The planning side could emit any of seven proof kinds; the agent that writes the tests contained the word 'angle' zero times. templates/agents/test-writer.md now carries all seven behind a TAUGHT-TEST-ANGLES anchor, and a cross-source set-equality test fails the moment either side drifts."
description: "BP-1100g-1. The AC store schema's test_spec[].angle enum lets the planning side request a proof by any of seven names -- criterion, reachability, seam, real_artifact, deployed, boundary, failure -- and generate_ticket_from_ac.py passes the requested name straight through onto the ticket. templates/agents/test-writer.md, the agent that then has to write that test, contained the word 'angle' zero times. An instruction the doer cannot parse is not an instruction: the emitted set was seven, the taught set was empty, and nothing compared them. This is EPIC-ComputedQualityGates FP-1 layer 3 recurring one floor up -- a hook's allow-list and the config it mirrored being disjoint vocabularies, each tested against its own copy, with no cross-source contract between them. The fix writes the seven names into templates/agents/test-writer.md behind a single stable <!-- TAUGHT-TEST-ANGLES:START/END --> anchor, one entry per angle, each carrying a DECIDABLE distinguishing rule rather than a description. The rules are written to say what does NOT satisfy the angle, which is what makes them actionable: reachability is not satisfied by importing the module, asserting a symbol exists, or asserting a value was merely passed as an argument; seam is not satisfied by calling an extended function directly with the new argument, because every real caller may still use the old signature; real_artifact is not satisfied by a hand-typed literal or by importlib.reload(), which re-executes in an already-populated namespace and masks cold-import errors. The comparison itself is the deliverable, not a doc: unit_tests/prompt_assembly/test_bp_1100g_1.py reads the emittable set from config/ac_store_schema.json and the taught set from the template, both from their REAL on-disk locations, and asserts set equality. It deliberately does not read the _TEST_ANGLES frozenset in generate_ticket_from_ac.py -- comparing against a convenience copy reproduces exactly the defect the test exists to catch. A one-sided-drift control adds a name to each side in turn and asserts the report names the specific angle AND the side that lacks it, because 'the sets differ' is unactionable. A reachability test runs build.py into a temp target and reads the DEPLOYED .claude/agents/test-writer.md that the agent runtime actually loads, so a template edit that does not survive deployment is caught -- and, symmetrically, editing only the deployed copy fails on the very next build. docs/testing/test-angles.md's now-stale 'test-writer contains the word angle zero times' callout is corrected to describe the anchor. Deliberately NOT covered by a test: the AC's second Then clause asks that each rule be actionable 'without further interpretation', which is a judgement about prose quality. Grepping the template for keywords would assert presence, not actionability, and is the Neverfail Test smell; that clause is routed to pr-reviewer against the llm-expert Prompt-Quality Checklist instead of being proxy-tested. What this does NOT claim: the writer has been told the words, not that it acts on them. BP-1100g-2 (resolving an entry point when none is named) and BP-1100g-3 (making the writer state which kind each test answers) remain todo."
breaking: false
---

## Entry

The angle taxonomy was produced by the generator, forbidden by the schema, validated by nobody, and unknown to the agent that writes the tests. This closes the last link: the writer now knows the vocabulary, and a test fails if the two sides ever disagree.

**The anchor** — `templates/agents/test-writer.md`, seven entries, each keyed by angle name with a one-sentence rule stating what does *not* satisfy it:

| angle | the disqualifier, in short |
|---|---|
| `criterion` | the floor angle — the "behaviour alone" proof every other angle is checked against |
| `reachability` | importing the module or asserting a symbol exists does not count |
| `seam` | calling the extended function directly does not count — real callers may still use the old signature |
| `real_artifact` | a hand-typed literal does not count, and `importlib.reload()` masks cold-import errors |
| `deployed` | a source-tree read is structurally blind to a deploy-manifest gap |
| `boundary` | the populated middle case is already `criterion`'s job |
| `failure` | asserting the happy path succeeds does not count |

**Why an anchor and not prose.** "The template mentions the vocabulary" is satisfied by pasting a paragraph, and it decays silently the first time a name is added on the emitting side. A parseable block makes the taught set a *set*, so it can be compared.

**The test reads both sides from where they really live** (`config/ac_store_schema.json` and the template) — never the `_TEST_ANGLES` frozenset copy in the generator. A comparison against a convenience copy reproduces the defect it is checking for.

**Red baseline**, captured before any template edit:

```
emittable: [boundary, criterion, deployed, failure, reachability, real_artifact, seam]
taught:    []
```

**Not claimed.** Set-equality proves the writer has been *told* the words, not that it acts on them. `BP-1100g-2` (resolve an entry point when none is named) and `BP-1100g-3` (make the writer state which kind each test answers) are still `todo`.
