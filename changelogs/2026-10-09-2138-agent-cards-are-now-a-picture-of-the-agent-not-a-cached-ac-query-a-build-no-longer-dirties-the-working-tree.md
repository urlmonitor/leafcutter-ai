---
title: "Agent cards are now a picture of the agent, not a cached AC query: a build no longer dirties the working tree"
date: "2026-10-09"
time: "21:38"
type: manual
components: 
  - infrastructure
  - ac_store
  - agent_registry
summary: "Running a build no longer leaves a dirty working tree: agent cards no longer list acceptance criteria, so they only change when an agent changes, and they can be committed again."
description: "Two commits (d78f478e3 tests, cce885645 implementation); behaviour change, not only a spec. Removes the trailing `## AC Assignments` section and the AC-store walk behind it from scripts/generate_agent_cards.py (render_ac_assignments, _scan_ac_assignments, _scan_all_ac_assignments, the ac_assignments= parameter of generate_card). Measured: section was in 17 of 64 cards; 3498 lines deleted and none added across those 17; python-coder.card.md 2809 -> 160 lines; cards over the 300-line limit 3 -> 0; regenerating twice over an unchanged store wrote 17 files then 0. AC store: INF-600b-3 added; INF-600b-2 and TQ-600a-11 plus children -i/-ii/-iii retired."
commits: 
  - d78f478e3
  - cce885645
breaking: false
---

## Entry

The files in `docs/agents/cards/*.card.md` are generated per agent by
`scripts/generate_agent_cards.py` on every `build.py` run. Each card now holds only static
facts about its agent: description, model/tier/priority table, tools, skills and the mermaid
diagram. The trailing `## AC Assignments` section, which listed every acceptance criterion whose
`assigned_agent` matched, is gone, along with the AC-store walk that built it.

**What a user sees.** A build no longer leaves a dirty working tree, and the cards can be
committed again. Unlike the previous changelog entry on this topic, this one changed behaviour:
the loop is closed, not just specified.

**Why it mattered.** The AC store changes constantly, so every build rewrote those cards. The
regeneration then could not be committed: the doc-length ratchet refuses a file that is already
over its limit and grew again, and `python-coder.card.md` stood at 2809 lines against a
300-line limit. It was a refusal nobody could act on, over content nobody wrote. The cards had
also not been regenerated since PR #570, so they drifted further behind the store with every AC
authored. Any consumer that needs the grouping can derive it from `assigned_agent` in the store
at read time.

**Measured.**

- The section was present in 17 of 64 cards.
- 3498 lines deleted and none added across those 17.
- `python-coder.card.md`: 2809 -> 160 lines.
- Cards over the 300-line limit: 3 -> 0.
- Regenerating twice over an unchanged store wrote 17 files, then 0.

**AC store.**

- `INF-600b-3` is new and specifies the property: a card does not move when an AC is added.
- `INF-600b-2` is retired. It required the grouping section, and its `When` offered "the ticket
  body or agent card", but only the card ever existed. It read `work_status: done` for four
  months with `covered_by: []` while only one of its two carriers was ever built.
- `TQ-600a-11` and its three children are retired: their subject was optimising the deleted walk.

**Do not misread: `docs/agents/cards/` stays a set-aside location.** It is still a declared
set-aside in the doc-length configuration even though no card now exceeds the limit. That is
deliberate. Membership there is by kind of document, not by size, so do not tidy it away
because it looks unused.
