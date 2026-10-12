---
title: 08 - Jev-selected graph and repository traversal
description: Historical analysis and saved observations for 08 - Jev-selected graph
  and repository traversal.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# 08 - Jev-selected graph and repository traversal

Recommendation: add traversal as another offered research method, using the existing kernel work item and continuation. Keep graph navigation and folder/file navigation as distinct contracts. System supplies an observed, permitted frontier; Jev chooses among those candidates or returns without reading; System validates, executes and retains the result. An unsuccessful traversal returns its attributable attempt to shared comparison and may lead to another method. It must not restart itself or erase earlier evidence.

Scope: S4; RS-11 through RS-16, RS-27 and RS-29. Method selection/attempt collection belongs to [05-method-attempts.md](05-method-attempts.md); comparative judgment and changed-method policy have separate owners. This is analysis at `887c66d3896ba7727ce41b743887210a3883c6ce`, not implementation, AC enrichment or a test sign-off. Only this report was written; no tests, provider calls or database operations were performed.

## Observed baseline

The [target traversal flow](../../product-truth/flows/leafcutter/retrieval-source-traversal.flow.json) is draft/spec with all 11 steps/branches `not_started`. The [old gap report](../2026-10-02-retrieval-completion-gap-analysis.md) correctly separates reusable primitives from the missing adaptive loop.

The [fresh retest](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/results.md) ran current code against published source `59269e024e4d0290b68b03d0d382745966e67e29`, generation `20c370b99a39e0939e985846c9132986f8dc3052007b0dec5b43c19ddda7c28f`, mapper 7. Its graph-only live RS-02/03 questions reach research and answer-contract planning, then wait for clarification upstream of query execution. None of the traversal target journeys ran. Direct lower-layer controls establish five declared dependents, honest partial pages and clipped-result limitations; these do not establish Jev navigation, folder discovery or restart behavior. A graph-only harness also cannot establish default native-source behavior.

## Verified code and gaps

Paths and symbols below are inspected source anchors, not runtime proof.

| Existing boundary | What can be reused; precise limitation |
|---|---|
| `knowledge/adapters/neo4j_queries.py:124`, `neighbors`; `:24`, `CATALOG` | One-hop, repository/generation-scoped lookup bounds seed count and per-seed/output rows. Discovery matches either endpoint but returns original directed `Relation` payloads. `get_declared_dependents` explicitly follows incoming `depends_on`; `get_related_tests` follows outgoing `covered_by`. Never turn discovery direction into dependency meaning. |
| `knowledge/contracts.py`, `Relation`, `ProjectionSnapshot`; `knowledge/query_catalog.py`, operation descriptions | Source/target/edge type and serving-manifest kinds, fields and relationships exist. The graph contains approved canonical metadata and declared links, not a complete import/call/data-flow graph. Internal `neighbors` checks generation existence and filters supplied edge labels; it is not a public permission/mapping/frontier validator. |
| `knowledge/retrieval_steps.py:164`, `disclose_candidates`; `knowledge/populations.py:105`, `_children`, `:167`, `_dependents` | Bounded related-context disclosure and dedicated hierarchy/direct-dependency enumeration exist. These are fixed operations, not Jev choosing an observed next frontier. A dedicated population operation can establish its stated population; a partial adaptive walk cannot borrow that completeness claim. |
| `kernel/capabilities/retrieval/locators.py:98`, `_fetch_one`, `:129`, `fetch_explicit` | Exact file/line/heading/Python-symbol reads use configured source ownership, relative paths and `ReadPolicy`; locators are deduplicated and capped within one call. No durable visited/frontier identity exists here. |
| `kernel/capabilities/retrieval/access.py:60`, `ReadPolicy` | Resolved containment and scope read roots, case-insensitive deny globs, file-size/binary checks and explicit unreadable outcomes are reusable. A directory offer must apply these policies before exposing denied entry names. Existing checks are not proof against replacement between validation and opening a live path. |
| `kernel/capabilities/retrieval/repository.py:77`, `_iter_files`, `:266`, `search_repo_text` | Native search enumerates recursively and reads files before limiting returned candidates. The output cap is not a scan-entry/depth/read/total-byte bound. Its symlink-directory handling does not establish Windows junction behavior. Do not wrap this full scan and label it bounded interactive navigation. |
| `kernel/capabilities/retrieval/versioning.py:44`, `resolve_source_version`; `knowledge/adapters/git_source.py:95`, `immutable_checkout`, `GitSourceResolver.read` | Native evidence can take `scope.revision` as its label while reading live filesystem bytes. Git disclosure reads the exact commit and verifies a supplied whole-file hash; immutable checkout materializes regular Git files. Both are useful, but full archive/blob loading before clipping does not itself enforce a physical read-byte budget. |
| `kernel/capabilities/research/state.py:38`, `ResearchContinuation`; `executor.py:265`, `build_research_graph`; `results.py:45`, `waiting_result` | Research already persists child/evidence/coverage state through the owning kernel work item; its inner LangGraph deliberately has no checkpointer. Current nodes are plan/collect/evaluate/finish, without frontier navigation. Extend this model and graph instead of adding another durable service. |
| `knowledge/cursors.py`, `request_hash`/`decode`; `knowledge/service.py`, `KnowledgeService` | Neutral continuations bind request, scope, generation and cumulative session work. The service defaults to a new process-local signing key: opaque cursors alone do not prove fresh-process resume. Kernel-owned traversal state must retain committed results and either reuse a durable trusted cursor-key arrangement or report expiration without resetting work. |
| `kernel/registry/eligibility.py:126`, `_policy_code`; `kernel/scheduler/state.py:110`, `Budgets`; `nodes_integrate.py:118`, `integrate` | Capability permissions and run-wide time/call/cost/retry ownership exist. Missing traversal dimensions must extend this authority; a method-local usage copy cannot grant fresh allowance. |

For direction, with `A depends_on B`, incoming traversal at B observes A as a declared dependent; outgoing traversal at A observes B as its dependency. Preserve that edge and its source locator even when deduplicating the node or reaching it through another path.

## Options and minimum staged extension

| Option | Benefit | Tradeoff |
|---|---|---|
| Add more fixed query recipes and exact locators | Smallest use of existing bounded adapters. | Useful preparation, but cannot satisfy RS-13/29 or Jev-selected navigation. Do not call it S4 completion. |
| Add typed traversal state/nodes under existing research/kernel ownership | Reuses admission, waits, evidence, source policy and accounting; supports later multiple methods through S1. | Requires observed-candidate validation, incremental scan bounds and behavioral resume tests. Recommended. |
| Introduce a separate traversal worker/checkpointer/ledger | Independent subsystem. | Duplicates recovery, budget and attempt authority. Unnecessary for this scope. |

Stage A should expose one graph traversal contract using real manifest-supported relationships and finite observed candidates. Stage B adds repository folders/excerpts through an incremental, policy-filtered immutable source adapter. Offer each mode only when its source, permissions and enforced limits are available; unsupported code relationships remain unavailable. Later working-tree navigation is a separately labeled mode with observed content identities and stale refusal, not a commit-backed fallback.

Each stage must reach the public research route and return through S1 collection/S5 comparison. Multiple selected methods remain S1's sequential dispatch concern. Traversal can request a switch but cannot execute the alternative or choose a comparison winner.

| Node / owner | Required behavior |
|---|---|
| System `offer_frontier` | Resolve approved starting seeds; enumerate only observed permitted candidates from pinned source; preserve directed edges, paths, availability and coverage. Bound and charge the enumeration itself. |
| Jev `choose_frontier` | Literal bounded choice among offered candidate/action IDs, using the original question and history. Start with one read/expand selection per step; allow return, switch, clarify and stop. No generated paths, Cypher or reads. |
| System `validate_frontier` | Check snapshot membership/digest, pins, current authority, allowed relationship direction and actual mapping, visited operation identity, and remaining limits. Reject foreign/stale/escaped choices; do not silently choose another. Valid non-reading actions go directly to retention. |
| System `read_selected` | Execute only accepted selections; produce actual evidence, execution status, next frontier and measured usage. Preserve useful prior evidence on empty, denied, stale, timeout and clipped outcomes. |
| Jev `judge_progress` | Judge newly observed evidence against the original need and select continue/return/switch/clarify/stop. Skip this post-read node for non-reading choices. Unchanged evidence cannot justify an identical re-read merely to raise confidence. |
| System `retain_route` | Persist traversal state through the existing work-item continuation before the next externally dispatched step. Continue with retained state, or return the attempt/outcome to S1/S5. S6 owns changed-plan/clarification dispatch after comparison. |

## Producer/consumer contract

Proposed names are additive design contracts, not current APIs. Reuse S1's `AttemptEnvelope` unchanged for method identity, frozen inputs/pins, actual result receipts, evidence, coverage, limitations and usage references. A traversal-specific payload/reference adds:

- Input: `attempt_id: str`, exact `original_question: str`, `need_id: str`, `answer_requirements_ref: str`, `mode: graph|repository`, `source_mode: immutable_git|working_tree`, frozen `scope_ref/permissions_ref: str`, `source_pins`, `start_candidate_refs: list[str]`, immutable configured bounds. Graph pins include repository/source SHA/generation/mapper; immutable repository pins include commit and materialization identity; live mode uses observed content hashes and never claims commit-equivalent bytes.
- Frontier: `snapshot_id/digest: str`, `candidates: list[Candidate]`, `coverage: complete|partial|unknown`, `limitations: list[str]`. Candidate fields: `candidate_id: str`, `kind: node|edge|directory|file|excerpt`, `action: expand|read`, `source_ref: str`, `locator: str`, `content_identity: str|null`, `depth: int`, `parent_candidate_id: str|null`, `edge: {source_id: str,target_id: str,type: str,direction: incoming|outgoing}|null`. No candidate ID grants new authority.
- Decision: `snapshot_id: str`, `action: read|expand|continue|return|switch|clarify|stop`, `selected_ids: list[str]`, `decision_ref: str`. Enforce action-specific cardinality: non-reading actions have no selected reads. Preserve the action when routing; do not replace stop with post-read judgment.
- Durable state: `frontier_ref`, bounded `visited_operation_keys`, `completed_read_receipt_refs`, `evidence_refs`, path/edge history, pending selection, original pins/obligations and usage references. An operation key includes source/content identity, node/path/locator, action, relationship filter/direction and bounds. Merely seeing a node is different from completing its expansion or reading its body. Deduplicate equivalent excerpts while retaining distinct provenance paths.
- Output: S1 attempt plus `traversal_state_ref`, `navigation_action`, `coverage`, `unresolved_frontier_refs`, explicit `refusal_reason: str|null`, actual execution receipts and usage. Distinguish successful empty from denied/unavailable/error, and execution completion from answer sufficiency. Error/refusal returns zero new evidence with previous evidence references intact; it never proves zero matches.

Keep all cumulative spend authoritative in the kernel: scan entries, graph candidates/edges, depth, read count, physical bytes read, disclosed bytes and active elapsed time/deadline, including offers and refused/ambiguous work where actually spent. Check before starting each operation and during incremental work. A returned candidate cap or post-read clipping cannot bound upstream enumeration or blob loading. Reserve the existing assessment allowance. Pause/resume cannot refresh budgets or extend the agreed deadline semantics.

The kernel continuation is the durable owner; traversal owns the typed navigation payload within it, S1 owns attempt collection, adapters own reads, and the scheduler owns budget integration. Completed receipts are consumed once and not re-dispatched on resume. A crash after I/O but before a durable receipt has an unknown outcome; follow S1's explicit unknown/idempotency policy rather than claiming physical exactly-once reads.

S1 must preserve REQUIRED evidence needs even when a substitutable traversal attempt is SUPPORTING and fails. All alternatives failing or remaining partial leaves the REQUIRED need unsatisfied. Complementary mandatory facts are not optional alternatives. Neither a stop action nor a successful adapter result upgrades coverage.

## AC status and missing acceptance clauses

All rows below have `status: active`, `req_status: active`, `readiness: approved` in the inspected store. Existing done status covers the recorded behavior, not this new target loop.

| Exact AC | Current work status | Reuse / missing traversal clause |
|---|---|---|
| KM-400a-5 | done | Preserve repository/generation isolation; extend to offered-candidate identity and every returned edge endpoint. |
| KM-400d-2 | done | Preserve pinned Git disclosure; require immutable folder enumeration and byte identity, or explicit live-mode stale refusal. |
| KM-400d-3 | done | Preserve scoped/expiring continuations; add durable visited/frontier/read receipts and fresh-process behavior. |
| KM-400d-4 | done | Preserve cumulative retrieval limits; add incremental scan entries, navigation depth, reads and physical bytes across traversal/methods. |
| KM-500c-2 | done | Return actual traversal attempt for assessment; no-read return/switch/clarify/stop must retain history and bypass read/judge. |
| KM-500c-3 | done | Extend no-progress protection to cycles, identical read selections and changed-method return with conserved budgets. |
| KM-500e-3 | in_progress | Partial/unknown traversal cannot establish absence or exact counts; a remaining unread frontier prevents completeness. |
| KM-500f-1 | in_progress | Preserve relation kind, direction, depth and source; declared impact is bounded to inspected relationships. |
| KM-500f-2 | in_progress | RS-16/27 must keep declarations, inspected files, actual test execution and deployment receipts distinct. |
| KM-500f-4 | in_progress | Source explanation requires actual inspected locations; no graph/file-existence claim becomes a complete function/data-flow or runtime-cause claim. |

Add focused child clauses later for offered graph/file modes, observed candidate validation, A-B-A cycle handling with useful C, checkpoint/restart and non-reading routing (RS-11..16/29). IDs are unassigned here. S1 attempt contracts, S5 coverage/comparison, S6 fallback and upstream exact-ID/clarification repair are dependencies; none is silently implemented by S4.

## Discriminating proof required before completion

Use fixture repositories made through real source writers/Git projection and actual adapter outputs, plus the public typed research entry and existing SQLite restart harness. Scripted Jev choices prove wiring only; eventual live choice-quality evidence is separate. New tests must fail on missing behavior before implementation, not merely inspect names or mocked dispatch arguments. No new tests or RED baseline were run in this analysis.

| Test | Positive and negative assertions / wrong implementation to kill |
|---|---|
| Public graph route and direction, RS-11 | Offer graph plus another usable method; Jev selects graph and actual directed adapter evidence reaches shared collection. With `A depends_on B`, B's incoming dependents contain A, not the outgoing dependency set. Absent manifest mapping returns unavailable, not empty. Kill unconditional traversal, reversed-edge inference and dead helper wiring. |
| A-B-A plus unseen C, RS-13 | Complete A/B reads, close SQLite and construct a fresh runtime; resumed frontier rejects identical A/B operations and permits useful observed C once. Retain alternate edge provenance without duplicate reads/charges. Kill in-memory visited sets, marking every observed node fully read, and stopping at the first cyclic candidate while C remains. |
| Immutable versus changed live bytes, RS-12/14 | Mutate a worktree after an immutable offer: read still yields the pinned old Git bytes. In explicit live mode, mutation between offer/read yields stale refusal and retains prior evidence; wrong hash/revision/generation cannot be relabeled as success. Kill revision-label-only pinning and silent source fallback. |
| Root escape and authority, RS-14 | Test `..`, absolute/drive paths, denied case variants, foreign node IDs, out-of-root symlink and Windows junction, plus link/path replacement before opening. No outside/denied bytes or names reach candidates/evidence. Missing `read_repo` or source permission causes zero adapter reads. Kill lexical-only containment and validation-once authority. |
| Every budget axis, RS-13/27 | Use wide empty directories and high fanout, then independently exhaust scan/depth/read/physical-byte/disclosure/time limits at exact boundaries across restart. Stop further work, retain useful evidence and disclose unknown omissions. Include cancellation. Kill output-cap-only bounding, full scan before truncation and fresh budgets after resume. |
| Partial cannot prove absence/count, RS-15 | Return two valid records with an unread C/continued page, denied branch or unsupported relationship. Evidence remains usable, but no exact total, global absence or whole proof inventory is asserted, even if Jev votes sufficient. Compare against a complete, explicitly scoped population control. |
| Non-reading bypass, RS-29 | For each return/switch/clarify/stop selection on an offered snapshot, assert no subsequent read/expand or post-read Jev judgment, unchanged evidence/frontier and preserved action through shared collection. Keep earlier enumeration/Jev costs. Kill routing every valid selection through read or judge. |
| Unsuccessful alternative, RS-16/27 | Graph returns declared tests without run receipts; return that actual limited attempt to comparison and retain useful sibling evidence. A denied/failed traversal cannot erase the sibling or satisfy a REQUIRED proof need. S6-authorized changed method may run through S1; identical retry is refused. |

Reusable test homes: `tests/kernel/retrieval/test_retrieval_locators.py`, `tests/kernel/capabilities/test_retrieval_repository.py`, `tests/kernel/scheduler/test_checkpoint_restart.py`, `tests/knowledge/test_core.py`, `tests/knowledge/test_disclosure_limits.py`, and `tests/knowledge/test_source_boundaries.py`. Their presence is not new traversal coverage.

Reviewed guidance: root and `.claude/CLAUDE.md`, `templates/agents/research-agent.md`, `templates/agents/test-writer.md`, `templates/agents/it-po.md`, and ADR-053. Applied disciplines are source-backed findings, independent behavioral and producer/consumer tests, precise typed handoffs and one declared decision owner. No broad planning/enrichment workflow or sign-off was invoked.