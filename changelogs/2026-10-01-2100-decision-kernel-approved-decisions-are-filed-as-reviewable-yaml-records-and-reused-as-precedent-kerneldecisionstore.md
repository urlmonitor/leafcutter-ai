---
title: "Decision kernel: approved decisions are filed as reviewable YAML records and reused as precedent (#KernelDecisionStore)"
date: "2026-10-01"
time: "21:00"
type: feature
components: 
  - decision_kernel
summary: "A decision a human approves is staged as a YAML record in the run, published into docs/decisions/ by an explicit command for normal git review, and offered to later runs as precedent: Jev judges whether it applies, an applicable one becomes evidence, and a strong match asks the human to reuse it or decide anew. Nothing a model wrote can become a record and the kernel never writes the repository during a run."
description: "The first real learning loop of the Decision Kernel, in the format the kernel itself chose (decision dec-ef8ddcb79d668a67, Kernel-contract YAML per decision, approved by the user). Store: ADR-059 (reviewable YAML records now, a graph later, behind a ColonyMemory port; a deliberate departure from the colony concept's Neo4j-first plan), ADR-060 (Git is canonical, only a human approval creates a record, no self-authorization, precedent is evidence not authority) and ADR-061 (existing ids stay, kernel-minted dec-<16hex> for decisions, key repository_id, kind, id); config/decision_record.schema.json; the kernel/memory package (port, null and file backends, record model, builder, validation, generated index, publication); python -m kernel decisions validate, index and publish (with an explicit --correct for append-only corrections) and the first record, dec-ef8ddcb79d668a67 (the knowledge map reads the records through the existing docs surface; a dedicated decisions surface is deferred because a new config/paths.json entry needs an acceptance criterion with package_surface true). Validation rides the normal test suite and CI, not a new pre-commit hook. Learning loop: a resolved decision a human approved stages a record in the run root with full provenance (run, trace, repository revision, versions); when a decision starts the kernel looks up matching records, one literal Jev question per precedent judges whether it applies (one call before any basis exists, inside the assess batch otherwise), an applicable precedent becomes prior_decisions evidence with its approver, and a strong match for a decision without options of its own asks the human once to reuse it or decide anew; reuse resolves with the precedent's choice approved by the current human and a new record that cites it, deciding anew keeps the precedent as evidence and never edits the older record. Offline proof through the real service: run 1 decides and publishes a record, run 2 (same goal) reuses it with 2 Jev calls instead of 12 and no host work or research, run 3 (unrelated, or judged not applicable) runs the normal flow. Live: the decision-records goal against this checkout finds dec-ef8ddcb79d668a67 and reaches the reuse question in 2 Jev calls and 4 seconds with no host operation. Round-8 defects fixed: a human-added option cites the evidence its claims were researched against, the decision report carries trace_refs, report.md has a readable Decision section, limitations are deduplicated with one retrieval-cut summary per need, each criterion assessment cites the evidence relevant to it instead of all of it, and a contract or class an option names is also fetched by path::Symbol. The retrieval benchmark now scores a pinned commit's files (corpus_commit, fetched at depth 1 in CI) instead of the live checkout, so new on-topic documents such as the decision store's own can no longer move its ratchets; its values are unchanged. Two defects found by running the kernel on its own next-step question are fixed: a goal that names its options no longer ends blocked (the host-only named_options rule had also been applied to the kernel's own verified payload, on main since V0), and an applicable precedent no longer stands in for option-grounding research."
---

## Entry

### Added

- `docs/architecture/adrs/ADR-059`, `ADR-060`, `ADR-061` — the decision store, source of truth and
  approval authority, and identity decisions.
- `kernel/memory/` — the `ColonyMemory` port, the null and file backends, the decision record
  model, the builder (refuses anything a human did not approve), validation, the generated index,
  publication, precedent handling, staging and the `decisions` CLI; `kernel/config_memory.py`.
- `config/decision_record.schema.json` and `docs/decisions/dec-ef8ddcb79d668a67.yaml` (the first
  record) with its generated `index.json`.
- `kernel/capabilities/criterion_evidence.py`, `research/limitations.py`, `kernel/intent/decision_text.py`
  — per-criterion evidence, limitation tidying and the report's Decision section.
- `docs/how-to/file-and-reuse-decisions-with-the-kernel.md`; "As built (decision store)" notes in
  design parts 2 to 5.
- `tests/kernel/memory/` — models, builder, store, validation, publication and CLI, the committed
  store, precedent rules, the decision graph with precedent, the six round-8 defects and the offline
  three-run learning loop.

### Changed

- `kernel/capabilities/decision/` — a `precedent` node; precedent questions ride the assess batch;
  a resolved decision a human approved is staged; `Decision.approved_at` and `precedent_ids`.
- `kernel/capabilities/research/` — bundle `need_evidence` and `need_limitations`; `path::Symbol`
  locators for a named contract or class.
- `kernel/scheduler/nodes_lifecycle.py`, `kernel/service_envelope.py`, `kernel/intent/report_text.py`
  — the decision report carries `trace_refs`; report.md has a Decision section.
- `config/capability_registry.json` — the `decision` capability's side effect is `run_artifacts`.
- `config/kernel_config.default.json` and its schema — the `memory` section.
- `kernel/adapters/claude_code/SKILL.md` — the skill may announce a staged record and never runs
  `decisions publish`.
- `tests/kernel/retrieval/benchmark_cases.json` — three cases re-baselined (corpus drift, noted in
  the fixture): the checkout now holds the decision store, which answers those goals.
