---
title: "KI-KM-20260930 — the entry_kind vocabulary has no known-issues member, so defect knowledge is unroutable by every automated path and reaches the registers only by hand"
description: "KI-KM-20260930 — the entry_kind vocabulary has no known-issues member, so defect knowledge is unroutable by every automated path and reaches the registers only by hand"
type: reference
category: reference
status: active
created: '2026-09-30'
last_updated: '2026-09-30'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
---

# KI-KM-20260930 — the entry_kind vocabulary has no known-issues member, so defect knowledge is unroutable by every automated path and reaches the registers only by hand

- **Severity:** high
- **Status:** open
- **Occurrences:** 1 (found while routing five items from the TQ-600a-5 drive; three of
  the five were defect knowledge and all three fell through)
- **Where:** `config/entry_kind_vocabulary.json` (`members`);
  `scripts/knowledge/harvest_learnings.py` (`_KNOWN_ENTRY_KINDS`);
  `templates/skills/route-knowledge/SKILL.md` (Surface Taxonomy table, Steps 0–17)

**Symptom.** Walk `route-knowledge`'s decision tree for a finding of the form "a tool
drops a dependency edge and reports READY" — the single most common kind of knowledge
this repo produces — and all 17 steps miss. Step 17 returns:

```json
{ "target_surface": "unknown", "path": null,
  "rationale": "No surface matched the decision tree. Surface to user for manual routing." }
```

Yet the correct destination is not in doubt. This repo has 14 component known-issues
registers under `docs/known-issues/`, each with a per-issue directory, a documented
filing convention, and hundreds of entries. It is demonstrably where defect knowledge
goes. The classifier simply has no token for it.

**Verified, not inferred.** `config/entry_kind_vocabulary.json` declares 23 members:
`adr`, `agent-frontmatter`, `architecture-doc`, `claude-md`, `claude-md-inline`,
`claude-md-toc`, `code-comment`, `explanation`, `explanation-doc`, `glossary`, `how-to`,
`memory-project`, `memory-reference`, `memory-user`, `per-agent-memory`,
`per-folder-readme`, `reference`, `reference-doc`, `retrospective`, `settings-json`,
`skill-context`, `skills-config`, `ticket-body`. None names a known-issues register.
`harvest_learnings.py`'s `_KNOWN_ENTRY_KINDS` frozenset carries the same member set, and
`tests/knowledge/test_inf_400c_5.py`'s
`test_every_vocabulary_member_has_a_harvester_routing_rule` structurally asserts the two
are equal — so the omission is consistent across the declaration, the router, and the
test that guards them. There is no path by which a defect finding routes automatically.

**Consequence: the automated capture path cannot carry this repo's most common finding.**
An agent that emits a defect discovery through `emit_knowledge.py` gets an `entry_kind`
the harvester does not recognise. Per `INF-400c-2-ii` the event is correctly *retained*
rather than dropped — it stays unprocessed and is counted `skipped_unknown`, to be
retried on a later run. But no later run can ever route it, because the missing member is
a vocabulary gap, not a transient condition. The event accumulates in the sink forever and
the finding reaches a register only if a human happens to put it there. Every entry in
all 14 registers arrived that way.

**Why this is the self-defeating shape.** `docs/known-issues/README.md` states the
register's own reason for existing: "a defect found and then only mentioned in a commit
message is, in practice, lost." The automated knowledge path currently loses defect
findings in exactly that manner — quietly, while reporting a clean `skipped_unknown`
count — inside the machinery built to prevent it. This is the register's own "common
shape": a check that reports success while seeing less than it should.

**Detection.** `grep -c known-issue config/entry_kind_vocabulary.json` returns `0`.
More usefully, the harvester's own
`unroutable_by_kind` report names every kind it refused; if defect findings are being
emitted at all, they are in it.

**Remediation.**

1. Add a `known-issues` member to `config/entry_kind_vocabulary.json` with
   `destination_pattern: "docs/known-issues/<component>/<status>-<severity>-<ki-id>.md"`,
   mirror it into `_KNOWN_ENTRY_KINDS`, and add the row to `route-knowledge`'s Surface
   Taxonomy table plus a decision-tree step ahead of the Step 17 fall-through. The three
   must land together — the structural test asserts declaration/router equality, and the
   skill table is what an LLM caller actually reads.
2. The index row is part of the destination, not an optional extra. A per-issue file with
   no row in `docs/known-issues/<component>.md` is unreachable by anything that reads the
   index — that omission was itself a finding on this drive. Whatever writes the entry
   must write both, or the routing rule has only half a target.
3. Decide how the component is chosen. Every other member has a fixed
   `destination_pattern`; this one needs a component segment, and the registers are keyed
   on `components.json` ids. That is a real design question and the reason to file this
   rather than patch a token in.

**Related.** `KI-KM-010` (the emission event is a receipt with no payload) — that entry
concerns what an event carries; this one concerns whether the event's kind can be routed
at all. `KI-KM-009` (ADR-034's claim that the knowledge loop "has never closed") — this
is one concrete way the loop does not close.

**Pattern:** a declared vocabulary that omits the category its own corpus is mostly made
of, so the omission is invisible to every consistency check between the declaration and
its consumers — they agree perfectly, and are jointly wrong.

---
