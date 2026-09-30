---
title: "KI-AR-004 — no agent is chartered for workflow-JS bodies, and 32 acceptance criteria assign that work to one that declines it"
description: "templates/workflows-js/*.js has no owner in the registry. llm-expert's scope names templates/workflows/*.md -- a different directory whose name differs by a suffix -- and a 2026-07-20 amendment retargeted a cohort of ACs across that distinction. Both llm-expert and workflow-architect decline the work on charter grounds; python-coder accepts only because the registry assigns it .js by an expedient the registry itself calls provisional. 32 records carry the wrong assigned_agent, and fewer than two-thirds of them are reachable by a path-string sweep."
type: reference
category: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - agent_registry
related_docs:
  - docs/known-issues/agent-registry.md
  - docs/known-issues/README.md
---

# KI-AR-004 — no agent is chartered for workflow-JS bodies

> One known issue in the agent-registry register.
> Index: [agent-registry.md](../agent-registry.md).
> Filename severity is the three-level index bucket (`high`); the original
> grading is the `**Severity:**` line below.

- **Severity:** high. Work cannot be dispatched to an owner because there is none, and
  32 acceptance criteria name an agent that refuses. It is not merely cosmetic: two
  dispatches were declined in sequence before the work could proceed, and the ACs that
  mis-route are the specification the next implementer reads.
- **Status:** open — no AC.
- **Occurrences:** 1 (2026-09-30, implementing `BO-2300e-2`).
- **First seen:** 2026-09-30 · **Last seen:** 2026-09-30
- **Where:** `config/agent_registry.json` — `llm-expert.selection_criteria`,
  `python-coder.owns_file_extensions`, and the absence of any entry claiming
  `templates/workflows-js/`.

**Symptom.** Dispatching the implementation of `BO-2300e-2` — a change to
`templates/workflows-js/plan-feature.js` — was declined twice before it could proceed:

- `llm-expert`, the `assigned_agent` on the record, refused: its scope is
  `templates/agents/*.md`, `templates/skills/*/SKILL.md` and `templates/workflows/*.md`.
- `workflow-architect`, which it nominated, also refused, and confirmed that no agent in
  the package is chartered for workflow-JS bodies.

`python-coder` accepted, because `owns_file_extensions` gives it `.py` and `.js`.

**Mechanism — a one-suffix directory collision.** Two directories exist and are distinct:

- `templates/workflows/` — 23 command-prompt `.md` files (`build-ac.md`, `commit.md`,
  `plan.md`, …) and zero `.js`. This is `llm-expert`'s declared surface.
- `templates/workflows-js/` — the executable workflow bodies, including
  `plan-feature.js`.

A 2026-07-20 amendment retargeted a cohort of acceptance criteria "to the E2 workflow
ENGINE… `assigned_agent` python-coder -> llm-expert". Every record in that cohort edits
`templates/workflows-js/`, which `llm-expert` does not own. The amendment appears to have
read the two directory names as the same surface.

**The registry already knows the ownership is wrong.** `python-coder`'s
`owns_file_extensions_rationale` says so directly:

> "'.js' is an EXPEDIENT, not a judgement that a Python agent is the right owner of
> JavaScript… The proper fix is a dedicated workflow-author agent, with ownership driven
> by per-consumer configuration rather than a hardcoded list; ACs for that are being
> authored. Revisit this entry when they land."

Those ACs have not landed. Two further details sharpen it: before that entry existed no
agent claimed `.js` at all — the convention was held together by imitation — and the
entry is advisory only, since the hooks that read `owns_file_extensions`
(`check_complexity.py`, `check_exception_handling.py`) both look up `.py` explicitly. So
nothing mechanical routes on `.js` in either direction.

**Blast radius — 32, and a path sweep finds 18 of them.** Measured 2026-09-30 across the
whole AC store:

- **14** records carry the verbatim 2026-07-20 retarget, still `assigned_agent:
  llm-expert`, still naming `templates/workflows-js/` in `it_requirements`:
  `BO-2300a-1`, `-1-i`, `BO-2300a-2`, `BO-2300b-1`, `BO-2300b-2`, `-2-i`, `BO-2300c-1`,
  `BO-2300d-1`, `-1-i`, `-1-ii`, `BO-2300e-1`, `-1-i`, `-1-ii`, `-1-iii`.
- **18** total name the directory path (the 14 plus `ACD-300b-3`, `BO-2200b-6`,
  `BO-2500d-1`, `BP-300e-6`, which arrived by other routes).
- **32** is the real figure. A further **15** name a workflow-JS body by FILENAME ONLY and
  are invisible to any `templates/workflows-js/` grep: `fast-lane-ship.js` ×5,
  `build-ticket.js` ×3, `finalize-feature.js` ×2, `build-epic.js` ×2, `plan-feature.js`
  ×2, `feedback-router.js` ×1.

The three `BO-2300e-3` records corrected on 2026-09-30 were themselves in that blind spot
— so a sweep written the obvious way would have reported them clean.

**Fix direction.** Two separable pieces:

1. **Charter the surface.** Either land the dedicated workflow-author agent the registry's
   own rationale calls for, or add `templates/workflows-js/` explicitly to an existing
   agent's declared surface. Leaving `.js` on `python-coder` as an unstated expedient is
   what makes every dispatch a judgement call.
2. **Sweep the 32.** Correct `assigned_agent`, and check `delivers_to`, `expects_from` and
   `doc_links` on each — the five records fixed on 2026-09-30 all carried at least one
   further pointer at `llm-expert` beyond `assigned_agent`. **The sweep must not be written
   as a path-string match**, or it will silently miss 15 of them.

**Pattern:** `assigned_agent` read as ownership. The field names a relationship; the
charter decides. The same shape as `permits_shell` read as "may run THIS command"
(`KI-ACD-20260928`) — a field that answers one question taken to settle another, with the
authoritative source never consulted.
