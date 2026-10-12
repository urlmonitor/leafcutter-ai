---
title: "ADR-066: The Kernel Resolves Named Terms by Research and Finds Its Own Repository Root"
description: "When a goal or a human answer names something the kernel cannot resolve (such as \"Atlas\"), the kernel researches it before ranking, reports an option with no evidence as unresearched instead of scoring it, finds its own git repository root from the topmost folder, and records every request it cannot serve as a countable request in one central store. On 2026-10-02 a wrong root and a missing term together produced a `completed` run that ranked the owner's option last with no evidence."
type: "adr"
status: "active"
created: "2026-10-02"
last_updated: "2026-10-02"
deciders:
  - BrainCandy
components:
  - decision_kernel
  - atlas_frontend
related_docs:
  - docs/architecture/adrs/ADR-025-first-class-flow-decisions.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/architecture/components/decision-kernel.md
  - docs/architecture/components/atlas-frontend.md
  - docs/glossary.md
related_code:
  - config/kernel_config.default.json
  - kernel/contracts/task.py
  - kernel/contracts/run.py
  - kernel/capabilities/retrieval/repository.py
  - kernel/capabilities/decision/assess.py
  - kernel/capabilities/decision/ranking.py
  - kernel/intent/roots.py
  - kernel/persistence/gap_store.py
---

# ADR-066: The Kernel Resolves Named Terms by Research and Finds Its Own Repository Root

## Status

| Field | Value |
|---|---|
| Status | Accepted (owner confirmed the added rules §1.2, §2.4, §3.4, §3.5, §5.4 on 2026-10-02) |
| Date | 2026-10-02 |
| Deciders | Project owner (BrainCandy) |
| Author | Claude Code (adr-author), recording the owner's decisions of 2026-10-02 |
| Supersedes | None |

## Context

### What happened

On 2026-10-02 the [decision kernel](../components/decision-kernel.md) ran a decision in which the
owner named the project's frontend, **Atlas**. Two failures stacked up.

**1. The wrong repository root, and the run still finished `completed`.** In run
`run-49c4f5e97f2d41d6` the host set `scope.repository_root` to `C:/Users/Hendrik/Code/leafcutter`.
That folder is not a git repository. It is a wrapper around the `leafcutter-ai` repository. The
kernel did not check the root. It recorded these limitations:

- "source revision unavailable (git not usable)"
- "root not searched: kernel / docs/architecture: root does not exist"

It still finished `completed`. Its only evidence was `scripts/langfuse/fetch_trace.py`.

**2. A named term the kernel could not resolve, ranked anyway.** The human added the option
"A page in Atlas, which is already our frontend". The kernel opened a research need
(`need.claim.opt.added.1`). No evidence item reached the 0.7 relevance bar. Jev still scored the
option on every criterion, with no evidence cited. The option ranked last. It was scored blind.
[ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md) §3 sends missing evidence
to research and back to Jev, and §8 says a `needs_*` outcome MUST NOT collapse into a guessed
result. A blind score is that guess.

### Why the kernel could not find Atlas

- **Retrieval has no discovery.** It searches a hand-written list of source roots relative to
  `repository_root`: `sources` in
  [`config/kernel_config.default.json`](../../../config/kernel_config.default.json). For example,
  `repo.patterns` covers `kernel`, `scripts` and `docs/architecture`. `repo.docs` covers
  `README.md`, `docs/how-to`, `docs/reference`, `docs/glossary.md`, `docs/INDEX.md` and more.
  `repo.components` covers `docs/architecture/components`. `repo.registries` covers
  `docs/components.json`. `leafcutter-web/`, where Atlas lives, is in no source.
- **The caller must pass the root.** The task contract
  ([`kernel/contracts/task.py`](../../../kernel/contracts/task.py)) requires the caller to pass
  `repository_root`. Nothing detects it.
- **The content did not exist.** Atlas is the Leafcutter frontend: a Next.js app in
  `leafcutter-web/`, run on http://localhost:4319. Before 2026-10-02 it had no glossary entry and
  no component. Commit `e1c329d` on this branch added the glossary entry "Atlas", the component
  `atlas_frontend` in `docs/components.json`, and the component doc
  [atlas-frontend.md](../components/atlas-frontend.md).

### The re-run with the right root

Run `run-57d16125a4a94de0` used the correct root. When the human added the Atlas option, native
kernel retrieval found it without host help. It found the glossary entry, the `docs/components.json`
entry, the new component doc, and
[ADR-025](ADR-025-first-class-flow-decisions.md). ADR-025 already described the Atlas flow-graph
renderer, but under the wrong root it could not be reached. The answer judgement for that need was
still 0.31: the evidence matched the topic but did not answer the claim. Finding a term and
answering a question about it are different steps.

### The owner's decisions

The owner gave three decisions, quoted verbatim:

1. > "So basically I mention that there is atlas, this MUST trigger proper research and then make
   > sure we update our content so it is findable from now on."
2. > "And why do you point it to a folder? It should do that by itself - starting always from the
   > topmost folder."
3. > "And it should file it as a request, so we have measures for later on this (or does analytics
   > not work yet?)"

   Requests the kernel cannot serve must be recorded, so demand can be measured later.

A fourth idea was considered and not decided. It is listed under
[Alternatives](#considered-not-decided--a-folder-and-readme-index-for-discovery).

### Measures today (decision 3)

Counting exists. Blocked run `run-eeb595361b1d4d38` recorded gap `gap-84c6e9a230a1bf12`
(`gap_type` `permission`, `occurrence_count` 1, `proposal` null). But four things stop those counts
from measuring demand:

- **(a)** The analysis docs state that a `change` request is blocked with `out_of_scope_write` and
  is "never a build opportunity". It never becomes demand.
- **(b)** The dedup key `normalized_need` is a bag of words. For the owner's request it was
  "always atlas basically by content findable folder from i it itself make". Rephrasings will not
  group.
- **(c)** Gap records are stored per kernel run root
  ([`kernel/persistence/gap_store.py`](../../../kernel/persistence/gap_store.py) writes
  `<run_root>/gaps/observations.jsonl`). Runs often use scratch run roots, so counts are scattered.
- **(d)** The cross-run learning layer
  ([ADR-056](ADR-056-colony-memory-evidence-reinforcement.md), colony memory) is deferred.

### Cost of not deciding

A run with the wrong root and no evidence reports `completed`. An option a human added is ranked
last on no evidence, and the ranking looks like a judgement. A thing the owner names stays
unfindable for the next run. A request the kernel cannot serve leaves no countable trace.

The kernel is read-only. It cannot file the Atlas findability request or write the missing
content itself. This ADR is that request, written by hand. Implementation tickets follow.

## Decision

### 1. An unresolved named term triggers resolution research before ranking

A **named term** is a name that the goal or a human answer uses for a specific thing in the
project. "Atlas" in the added option "A page in Atlas, which is already our frontend" is one. A term
is **resolved** when the glossary (`docs/glossary.md`), the component registry
(`docs/components.json`), or an evidence item that reaches the research relevance bar names it.

1. When a named term in the goal or in a human answer is unresolved, the kernel MUST run a
   resolution research step for that term before it ranks any option.
2. The resolution step MUST search the whole repository root found under §3, not only the roots in
   `sources` of `config/kernel_config.default.json`. It MUST keep the `retrieval.deny_globs`
   exclusions.
3. A term added by a human answer MUST be handled exactly like a term in the goal.
4. A term that is still unresolved after the step MUST be named in the run's limitations. Every
   option that rests on it falls under §2.

### 2. An option with no relevant evidence is reported as unresearched, not scored

1. An option with zero evidence items at or above the relevance bar MUST be reported as
   **unresearched**.
2. Jev MUST NOT assess an unresearched option on any criterion. The option MUST NOT get a score or
   a rank position.
3. The decision report MUST list each unresearched option on its own, with its open research need
   (for example `need.claim.opt.added.1`).
4. A decision with an unresearched option MUST NOT be reported as `resolved`. The run MUST end
   `partial` with an open question that names the option. This applies ADR-053 §8: a `needs_*`
   outcome MUST NOT be collapsed into a guessed result.

### 3. The kernel finds its own repository root

1. The kernel MUST discover the repository root itself. Discovery MUST start at the topmost folder
   of the workspace (here `C:/Users/Hendrik/Code/leafcutter`) and walk down from there. The caller
   MUST NOT have to name the repository.
2. A `repository_root` passed by the caller (`kernel/contracts/task.py`) MUST be treated as the
   starting folder for discovery, not as the root.
3. Duplicate checkouts MUST be skipped. A git worktree of a repository already found (same git
   common directory), such as the about 10 copies under `worktrees/`, MUST count as the same
   repository. Its tree MUST NOT be searched as extra evidence.
4. When the kernel's launch directory lies inside one checkout of the found repository, that
   checkout MUST be the root. Otherwise the main checkout MUST be the root.
5. When discovery finds more than one distinct repository and rule 4 does not pick one, the run
   MUST end `waiting_human` with a question that lists the candidates. The kernel MUST NOT guess.
6. The chosen root MUST be a git repository in which git is usable. When discovery finds no such
   repository, the run MUST end `blocked` with a limitation that names the starting folder. It
   MUST NOT end `completed`.
7. The run MUST record the root it chose, so a reader can see which checkout was searched.

### 4. A term found only by research is filed as a findability request

1. When §1's resolution step finds a term that ordinary retrieval over the configured `sources`
   did not find, the kernel MUST file a **findability request**. A term that stays unresolved MUST
   also be filed, marked unresolved.
2. The request MUST name the term, the paths where research found it (if any), and the content that
   would let ordinary retrieval find it next time. That content is one of: a glossary entry in
   `docs/glossary.md`, a component in `docs/components.json` with its component doc, or a doc
   inside a root that `sources` searches.
3. The kernel is read-only and MUST NOT write that content itself. It MUST record the request in the
   store of §5. A human, or a host working on a ticket, adds the content.

For "Atlas", this ADR is the filed request, and commit `e1c329d` is the content fix.

### 5. Every request the kernel cannot serve is recorded as countable demand

1. Every request the kernel cannot serve MUST be recorded as a request record. This covers `change`
   requests declined with `out_of_scope_write`, `out_of_domain` requests, `no_match` routing,
   permission declines, and the findability requests of §4.
2. Recording a request as demand MUST NOT turn it into a capability-build draft.
   [ADR-056](ADR-056-colony-memory-evidence-reinforcement.md) §6 is unchanged: only `unsupported`
   and `host_only` gaps create build pressure. A recorded `change` request is demand for the owner
   to read. It is still never a build opportunity.
3. Each record MUST carry a stable, meaningful key built from the request kind and the subject it
   names (a term, a component id, a path or a capability). The key MUST NOT be the sorted goal
   tokens that `normalized_need` holds today (`kernel/contracts/run.py`). Two rephrasings that
   name the same kind and subject MUST get the same key.
4. Records MUST go to one central store per repository, independent of the run root. A run under a
   scratch run root MUST still write to it, so the counts for one key add up across runs. Gap
   observations MUST be counted in the same store. The file location is set by the implementation
   ticket.
5. Each record MUST carry an occurrence count and example run ids, as gap records do today.
6. This is a recording prerequisite in the sense of ADR-056 §9, Stage 1 item 3 ("Gap records that
   can be counted"). It adds counting only. It adds no reinforcement and no routing change. The
   ADR-056 cross-run learning layer stays deferred.

## Consequences

### Positive

- A name the owner uses, such as Atlas, is researched before options are ranked. A human's option
  is no longer ranked last on no evidence.
- A run with a wrong or non-git root stops reporting `completed` with almost no evidence. The host
  no longer chooses the repository.
- Each term found only by research leaves a request for content behind. Once the content exists,
  ordinary retrieval finds the term, as the re-run `run-57d16125a4a94de0` showed for Atlas.
- Requests the kernel cannot serve, including `change` requests, become countable across runs and
  rephrasings. The owner gets the demand measure asked for in decision 3.

### Negative

- Each unresolved term costs an extra research step. A search of the whole repository tree is
  slower than a search of the listed `sources`.
- Discovery walks the topmost folder. It must recognise and skip the about 10 worktree copies
  under `worktrees/`. A wrong same-repository check would either search duplicates or miss a
  checkout.
- Runs that used to report `completed` will now end `partial`, `blocked` or `waiting_human`. The
  kernel will look less finished, because it is more honest about what it did not know.
- Named-term detection can misfire. A common word taken for a named term causes a needless research
  step and a needless findability request.
- Resolving a term does not answer the question about it. In the re-run, the answer judgement for
  the Atlas need was still 0.31. This ADR does not change that.
- The central request store is new persistent state. It needs a schema, a location and a
  retention rule.
- Counting `change` requests as demand sits next to the statement that they are "never a build
  opportunity". The two stay compatible only if §5.2 is kept: demand is not build pressure.

### Operational

- The content fix for Atlas has landed on this branch (commit `e1c329d`): the glossary entry, the
  component `atlas_frontend`, and [atlas-frontend.md](../components/atlas-frontend.md).
- The kernel is read-only, so this ADR is the filed request. Implementation tickets follow for
  §1 to §5.
- Code and config these decisions bind: `sources` in `config/kernel_config.default.json`;
  `repository_root` in `kernel/contracts/task.py`; retrieval in
  `kernel/capabilities/retrieval/repository.py`; option assessment and ranking in
  `kernel/capabilities/decision/assess.py` and `kernel/capabilities/decision/ranking.py`; the
  declines in `kernel/intent/roots.py`; the gap key and store in `kernel/contracts/run.py` and
  `kernel/persistence/gap_store.py`.
- Related kernel defects seen in the same runs. They are follow-ups, not decisions of this ADR:
  - Synthesis findings are not passed to the `generate_options` request (`findings: []`). This is
    reproducible.
  - The run store resolves from the current directory's git repository, so resuming from another
    worktree fails with `run_not_found`.
  - The printed `decisions publish` command does not run as shown (bare `python`, no
    `PYTHONPATH`).
  - Evidence relevant to an option is not routed into that option's per-criterion scoring.

## Alternatives

- **Keep the caller-supplied `repository_root` as the root (status quo).** Rejected. In
  `run-49c4f5e97f2d41d6` the host passed a non-git wrapper folder, and the kernel completed with one
  piece of evidence. Trusting the caller is the failure, and the owner rejected it ("why do you
  point it to a folder?").
- **Validate the root, but leave choosing it to the caller.** Rejected. Refusing a non-git root
  stops the silent `completed`, but the host still has to find the repository. The owner's decision
  is that the kernel does this itself, starting from the topmost folder.
- **Add `leafcutter-web/` to the `sources` list.** Rejected as the mechanism. It fixes Atlas only.
  The next folder that no source lists fails the same way, because the list has no discovery.
- **Score an unresearched option with low confidence.** Rejected. This is what happened: the Atlas
  option was scored on every criterion with no evidence and ranked last. ADR-053 §8 forbids
  collapsing a `needs_*` outcome into a guessed result.
- **Drop an option that has no evidence.** Rejected. The option came from a human answer. Hiding it
  loses the human's input and hides the research gap.
- **Use the existing gap store as the demand measure.** Rejected. It cannot measure demand for the
  four reasons in Context: `change` requests never become demand, the bag-of-words key does not
  group rephrasings, records are scattered across run roots, and the cross-run layer is deferred.

### Considered, not decided — a folder-and-README index for discovery

The owner asked, and said "do not build this - just asking":

> "If [each folder has a readme with a summary] we should use a script that provides folders and
> their readme so that it can decide where to look by itself."

This ADR neither adopts nor rejects it. The facts on 2026-10-02:

- Only 29 of 98 folders (depth up to 2) of `leafcutter-ai` have a `README.md`. An index built
  today would describe fewer than a third of the folders.
- `scripts/commit_guardian/check_documentation.py` requires a `README.md` beside changed `.py` and
  `.sql` files. It checks existence only. The sections Purpose, Key Files, Critical Context and
  Maintenance appear only in its error hint.
- That check is not enforced. It is withheld as a broken gate (KI-CG-20260831-0713: argparse
  rejects positional filenames). Nothing raises README coverage today.

## References

- [ADR-025: Decisions Are First-Class Flow Entities](ADR-025-first-class-flow-decisions.md): already
  described the Atlas flow-graph renderer; found once the root was right.
- [ADR-053: Intelligence Selection](ADR-053-intelligence-selection-deterministic-jev-llm-human.md):
  §3 escalation path and §8 outcome mapping, applied in §2.
- [ADR-056: Colony Memory](ADR-056-colony-memory-evidence-reinforcement.md): §6 build-pressure
  rule (unchanged) and §9 Stage 1 recording prerequisites, extended in §5.
- [Decision kernel component doc](../components/decision-kernel.md)
- [Atlas component doc](../components/atlas-frontend.md)
- [Glossary](../../glossary.md): entry "Atlas"
- Runs: `run-49c4f5e97f2d41d6` (wrong root), `run-57d16125a4a94de0` (re-run with the right root),
  `run-eeb595361b1d4d38` (gap `gap-84c6e9a230a1bf12`)
- Commit `e1c329d`: docs(glossary,components): make the Atlas frontend findable
