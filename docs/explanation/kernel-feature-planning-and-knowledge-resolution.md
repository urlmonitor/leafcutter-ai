---
title: "Kernel Feature Planning and Knowledge Resolution"
description: "Draft design discussion: persona prerequisites, context selection at scale, and uncertainty resolution for kernel-native feature planning."
type: explanation
status: draft
created: 2026-10-02
last_updated: 2026-10-02
components:
  - persona_management
  - knowledge_management
  - knowledge_system
  - research_analysis
related_docs:
  - docs/architecture/components/persona-management.md
  - docs/architecture/components/knowledge-management.md
  - docs/architecture/agent_knowledge_plane.md
  - docs/architecture/agent_knowledge_system.md
  - docs/explanation/traceability-guardrails.md
---

# Kernel Feature Planning and Knowledge Resolution

## Why It Exists

Feature planning depends on inputs an initial request rarely settles: who
benefits, which constraints apply, what behaviour is required, and what would
demonstrate success. A convincing plan can conceal those gaps.

The design direction is a repeated **knowledge-resolution loop**: identify
each consequential decision's prerequisites, obtain missing knowledge, and
assess whether the result is sufficient.

> [!IMPORTANT]
> This is a **draft design discussion captured on 2026-10-02**. It preserves user
> directions and assistant proposals; it is not an approved architecture, ADR,
> implementation specification, or description of a complete existing planner.

## Background and Verified Baseline

- The subject is kernel-native planning, rather than the legacy JavaScript
  workflow or a skill acting as planner.
- The kernel scheduler manages work and handoffs; JEV performs bounded
  assessments; registered capabilities perform work.
- The registry contains decision, research, repository retrieval, and four host
  operations: option generation, synthesis, bounded research, and question
  formulation. It has no complete feature-planning capability.
- Generated options and criteria enter approval tracks. Precedents are evidence;
  reusing an earlier choice requires human confirmation.
- [Persona Management](../architecture/components/persona-management.md) defines
  the component's scope, while implementation entry points remain future work.
  Existing agent knowledge injection and capture are adjacent concepts, not
  evidence that this proposed kernel loop is implemented.

These observations were checked on **2026-10-02** against checkout
`C:/Users/Hendrik/Code/leafcutter/worktrees/kernel-codex`, commit
`b0cfe86dada2dfbea84947c21a2a0ecaa4e7a4a7`.

| Source within that checkout and revision | Relevant baseline |
|---|---|
| `config/capability_registry.json` | Registered building blocks and execution modes |
| `docs/architecture/components/decision-kernel.md` | Scheduler, JEV, capabilities, handoffs |
| `kernel/contracts/decision.py` | Confidence, evidence, approval, missing knowledge, criterion kinds |
| `kernel/capabilities/decision/option_context.py` | Pattern-based extraction of files and symbols |
| `kernel/capabilities/retrieval/knowledge_map.py` | Indexed term matching, bounds, unavailable-source reporting |
| `docs/how-to/file-and-reuse-decisions-with-the-kernel.md` | Precedent filters, applicability, human reuse |

These are source locators in the named kernel checkout, not local links.
Reference extraction and indexed retrieval are foundations; they do not
establish general entity linking, hierarchical retrieval, or planning gates.

## User Directions Preserved from the Discussion

| User direction | Consequence |
|---|---|
| Deciding who benefits requires personas; absent personas must trigger their creation first. | The beneficiary decision has a persona prerequisite. |
| Each context type needs its own JEV judgment. Large decision collections need category selection and progressive drilldown. | Coverage must remain inspectable when five decisions become 10,000. |
| Inject knowledge automatically or make retrieval easy. Unclear words should trigger a clarity flow and focused research; recognizers should identify glossary terms, content types, and components. | Knowledge gaps need reusable detection and resolution mechanisms. |

The following refinements are **assistant proposals**, not accepted
implementation choices. Batching judgments, assessing phrases instead of every
word, and selecting multiple retrieval branches remain suggestions.

## Personas as Prerequisites

**Proposed refinement:** check existence, applicability, and adequacy separately.
An existing persona may describe another population or omit relevant goals and
constraints. Planning would reuse a suitable record, refine an inadequate one,
or request a new one.

Authoring becomes a prerequisite work item. The beneficiary decision waits;
independent work, such as examining an existing interface, can continue.

Creating a document does not establish knowledge about users. Generated
personas can organize facts and propose hypotheses, but must distinguish sourced
observations, owner-supplied knowledge, and unvalidated assumptions. Adequacy
means the evidence supports the pending decision, not that every field is filled.
The required evidence, assumption-approval authority, and authoring capability
remain to be decided.

## Context Selection from Five Decisions to 10,000

**Proposed refinement:** separate two judgments:

1. **Context need:** which kinds of knowledge could change this decision?
2. **Record applicability:** which retrieved records of those kinds apply here?

Candidate types include product constraints, architecture decisions, interface
contracts, operational requirements, and historical outcomes. The taxonomy is
unsettled. A logical JEV judgment for each type need not require a separate
provider call: independent judgments could be batched while preserving separate
outcomes and evidence references.

An illustrative retrieval route is:

**Repository or workspace -> relevant domains -> components or topics ->
candidate decisions -> relevant excerpts.**

An index narrows candidates; JEV assesses bounded choices. Exact identifiers,
explicit references, and scope filters can use deterministic lookup. Assessing
all 10,000 full records together would increase cost and obscure omissions.

Category trees can miss cross-cutting constraints. Authentication may affect
several components, while a repository-wide rule may sit outside the first
selected branch. The proposed policy therefore includes:

- Multiple relevant branches and direct references that bypass category selection.
- Explicitly applicable global constraints regardless of the selected branch.
- Broader or alternative retrieval when coverage is weak.
- Separate outcomes for unavailable sources and searches with no matches.

Included records would retain their inclusion reason, scope, authority, status,
provenance, and freshness or revision. Similar wording does not prove
applicability; a precedent is different from a binding constraint.
[Knowledge Management](../architecture/components/knowledge-management.md)
provides related indexing concepts. The drilldown strategy still needs evidence
that it finds the necessary context at the intended scale.

## Uncertainty Beyond Unclear Words

**Proposed refinement:** assess terms, phrases, entities, and claims in context,
rather than every word unconditionally. "Order" could mean a purchase, a trading
instruction, or a sequence; surrounding context helps establish the meaning.

**Entity recognition** detects a possible concept or object.
**Entity linking** connects that mention to a particular registered record.
Recognition alone should not inject a candidate definition as settled fact.
Exact glossary terms, content-type identifiers, and component IDs may support
direct lookup; ambiguous mentions require assessment or clarification.

Automatic injection would supply concise, attributable knowledge for established
matches. Retrieval would expand it when needed. Both preserve source identity
and uncertainty instead of silently converting suggestions into facts.

| Gap | Proposed response |
|---|---|
| Known term or unambiguous entity | Retrieve its definition and relevant relationships |
| Ambiguous mention or phrase | Assess meanings; ask a focused question if unresolved |
| Missing factual knowledge | Research a bounded question |
| Conflicting claims | Compare scope, authority, and freshness; retain unresolved conflict |
| Missing owner preference | Ask the owner; research cannot supply their preference |
| Missing or inadequate artifact | Request authoring or refinement, then validate adequacy |
| Missing requirement despite clear wording | Check the decision's required inputs and resolve omitted behaviour |

Clarity is one trigger, not a completeness test. "Notify users when an order
fails" is readable but leaves recipients, timing, retries, duplicate suppression,
and delivery failures unspecified. Decision-specific checks expose omissions
that definitions alone cannot resolve.

## The Shared Knowledge-Resolution Loop

**Identify missing knowledge -> retrieve, research, clarify, or author ->
validate -> reassess the decision.**

The scheduler would manage dependencies, resumption, and independent work.
Capabilities would gather evidence or produce artifacts. JEV would assess
relevance, ambiguity, coverage, and adequacy within bounded supplied context;
deterministic checks would handle record existence and identifier validity.
A missing capability stays explicit instead of silently invoking a legacy skill.

Each decision would carry required knowledge, prerequisite artifacts, linked
entities, applicable constraints, evidence, assumptions, contradictions, unresolved
questions, and a sufficiency rule. These are conceptual needs, not an agreed schema.

JEV confidence, evidence coverage, source reliability, and approval authority
remain separate. A confident assessment of poor or incomplete evidence does not
prove that a decision is sound.

### Readiness and Bounded Work

The proposed per-decision gate asks whether required inputs are adequate,
applicable constraints are covered, consequential claims have support, and gaps
are resolved or explicitly accepted by the appropriate owner. Accepted assumptions
remain visible with their consequences and a reason to revisit them.

The overall plan also needs coverage across these areas:

| Planning area | Proposed readiness question |
|---|---|
| Outcome and scope | Are beneficiaries, intended change, success conditions, and exclusions clear? |
| Constraints | Are relevant commitments, interfaces, and prior decisions accounted for? |
| Behaviour | Are normal, error, and boundary cases sufficiently specified? |
| Alternatives | Are consequential choices justified against agreed criteria? |
| Uncertainty | Are blockers distinguished from accepted assumptions and residual risks? |
| Delivery | Are useful increments, dependencies, and feasibility established? |
| Verification | Does each requirement have observable evidence of satisfaction? |
| Rollout | Are applicable migration, release, and recovery questions settled? |

Suggested controls bound retrieval depth, branch breadth, retries, cost, and time.
They detect repeated no-progress results and dependency cycles, and deduplicate
equivalent questions. Reaching a limit should yield an explicit unresolved
outcome. Changed personas, constraints, or evidence should invalidate dependent
assessments where their support no longer holds. Exact rules remain open.

## Hypothetical Example: Failed-Order Notifications

Consider **"Notify users when an order fails."** This illustration introduces
no existing product requirement or factual persona.

The beneficiary check finds no adequate recipient persona and requests authoring
or refinement. Recipient-specific decisions wait while independent retrieval
examines order interfaces and notification constraints.

If both purchase orders and trading orders exist, context may identify which
"order" the request means. Otherwise, the kernel needs focused clarification;
a glossary match alone cannot settle the choice.

Context judgments select product, interface, and operational sources. Retrieval
follows relevant branches, checks direct references, and includes applicable
global constraints. A hypothetical rule prohibiting duplicate alerts would need
its scope and status checked before constraining the plan.

Research can establish whether the interface exposes a final failure event and
whether retries share an identifier. It cannot choose an unspecified owner's
preference for immediate alerts versus a digest.

When inputs arrive, the loop reassesses recipients, failure meaning, timing,
and duplicate handling. Readiness requires observable acceptance behaviour and
a feasible delivery increment. Unsupported persona assumptions or unresolved
recipient choices remain gaps even if the plan document reads convincingly.

## Trade-offs

Explicit dependencies and selective knowledge resolution make gaps inspectable
and work focused, at the cost of additional state and adequacy checks.

An unconditional word-by-word pass is not the preferred refinement: phrases
and entities often carry the relevant meaning. Contextual detection is more
selective but can miss ambiguity and needs evaluation on realistic prompts.

Single-branch category routing is rejected within the proposal because it can
miss cross-cutting constraints. Multiple branches improve coverage but enlarge
candidate sets. Injecting every source avoids category selection while creating
cost and attention limits. These remain proposed trade-offs; no ADR approves them.

## Open Design Questions

- What are the canonical context types, and who maintains them?
- What persona evidence and approval rules make a prerequisite sufficient?
- How do batched JEV judgments retain independence and expose omissions?
- How are applicability, binding authority, supersession, and freshness represented?
- Which capabilities own entity linking, knowledge resolution, and artifact validation?
- Which uncertainty classes and readiness checks apply to each decision type?
- Which budgets, no-progress rules, and cycle handling stop recursive work?
- How are shared questions deduplicated and dependent decisions invalidated?
- How will evaluation measure missed constraints, unnecessary clarification,
  coverage at 10,000 records, and readiness errors?

These questions remain for a later architecture and implementation plan.

## See Also

- [Persona Management](../architecture/components/persona-management.md)
- [Knowledge Management](../architecture/components/knowledge-management.md)
- [Agent Knowledge Plane](../architecture/agent_knowledge_plane.md) — injection.
- [Agent Knowledge System](../architecture/agent_knowledge_system.md) — capture.
- [Traceability Guardrails](traceability-guardrails.md) — adjacent explanation.

The dated source table identifies the kernel operation and precedent-reuse
references. No matching local how-to or approved ADR exists for this planning loop.

<!-- DECISION HISTORY
- 2026-10-02 [explanation-author]: Captured user directions and assistant proposals
  for kernel-native planning and knowledge resolution; design remains open.
-->
