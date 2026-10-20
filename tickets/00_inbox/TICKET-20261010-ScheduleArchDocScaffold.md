---
title: "Schedule INF-1300: build the architecture-doc scaffold the diagram skill requires"
status: todo
components:
  - infrastructure
created: 2026-10-10
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - architecture-docs
  - scaffold
  - write-c4-diagram
last_updated: 2026-10-10
---

# Schedule INF-1300: build the architecture-doc scaffold the diagram skill requires

## Actor / Goal

The write-c4-diagram skill tells every diagram author to start from `scripts/scaffold/new_arch_doc.py`, and to
stop when it is missing. The script has never existed in this repository, so every diagram ticket stops or
works around the rule. We need to build the scaffold INF-1300 already specifies, so that diagram agents can follow
the skill as written and the standing scaffold-free pass in decision dec-b10271ebb40b9eaa can end.

## Context

- **Where the rule came from:** section 4 of `templates/skills/write-c4-diagram/SKILL.md`, including step 5 ("If
  scripts/scaffold/new_arch_doc.py is unavailable or fails, surface to the user and DO NOT improvise a hand-authored
  frontmatter/legend"), arrived with the Bybit-Trader extract (11dbd26b7, 2026-05-19). Bybit-Trader has the script;
  this repository never did.
- **Requirements exist, nothing builds them:** INF-1300 ("Writing an architecture document costs you the thinking,
  not the conventions") is approved, with 32 AC records, 31 of them todo. It is under
  `docs/acceptance-criteria/infrastructure/INF-1300-architecture-docs-by-construction/`. No ticket or epic builds
  it, and `docs/roadmap.json` does not mention it.
- **What it blocks today:** DK-400c-4 (E1 ticket 17), DK-400c-5, DK-400d-5, DK-400e-5 and BO-1800f-3. Decision
  dec-b10271ebb40b9eaa (2026-10-10) authorised a recorded scaffold-free pass for those until a scaffold ships, and
  required this ticket so the scaffold actually gets scheduled.
- **Known facts the build must respect:**
  - INF-1300b-2: there is no canonical Legend. The key is derived from the notation each diagram kind uses.
  - INF-1300b-4: step 5's prohibition text must survive.
  - The skill and the agent template cite ADR-015 as the Legend source. In this repository ADR-015 is about
    exception handling, and INF-1300 records those citations as false.
  - `scripts/build_propagation_audit.py` allowlists the missing script with a note that a separate authoring
    ticket is required.

## Acceptance Criteria

- [ ] AC-1: An epic that builds INF-1300's open ACs exists (generated from the INF-1300 tree with the project's
  epic generator) and has a place in `docs/roadmap.json` or the current phase's ticket list.
- [ ] AC-2: The epic's Master_Plan names decision dec-b10271ebb40b9eaa and says that the standing scaffold-free
  pass ends when the scaffold ships.
- [ ] AC-3: The tickets blocked today (DK-400c-5, DK-400d-5, DK-400e-5 and BO-1800f-3) are listed in the
  Master_Plan, so whoever builds them knows whether the scaffold exists yet.

## Comments

## Risk & Safety

- **Touches money?** No.
- **Touches data?** No. This is planning only; the scaffold itself is built by the epic this ticket schedules.
- **Reversibility:** full. The epic can be re-planned or dropped.
