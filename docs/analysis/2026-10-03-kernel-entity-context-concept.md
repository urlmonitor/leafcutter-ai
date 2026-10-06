---
title: "Entity meanings before kernel intent"
description: "Implemented design for repository entity recognition before intent: compact owner-authored meanings first, task evidence after routing."
type: explanation
status: active
created: 2026-10-03
last_updated: 2026-10-03
components:
  - decision_kernel
related_docs:
  - docs/architecture/components/decision-kernel.md
  - docs/product-truth/flows/leafcutter/decision-forming.flow.json
  - docs/product-truth/flows/leafcutter/decision-lifecycle.flow.json
  - docs/glossary.md
---

# Entity meanings before kernel intent

**Implemented design; verification is recorded separately.** The repository-search part of initial
enrichment is replaced by deterministic entity recognition and compact meanings. Intent needs
to understand what the request refers to and what work is requested. The capability
selected after intent retrieves the evidence needed to answer or act. The existing
decision-forming flow remains the canonical journey; its revised specification and
parent lifecycle describe this implementation. No new independent enrichment flow is needed.

## Behavior before this revision

The previous scheduler ran `intake -> enrich_context -> intent`. Its initial enrichment
combined the goal and supplied caller context into lexical search hints, then used
filename ordering and bounded section/BM25 retrieval. Its defaults limit search to
48 query terms, 180 files, six sources, six excerpts, 8,000 excerpt characters and
three seconds. It cannot inject the whole repository. Nevertheless, ordinary words
can consume search effort and produce evidence before the system knows what evidence
the task needs. In the observed request, “Can you use leafcutter now? I mean run the
kernel and know about it?”, terms included `mean`, `run` and `know`; the pass scanned
155 files and kept six excerpts totalling 3,760 characters. It made no Jev calls.

`TaskInput.goal`, the goal payload and exported goal-request schema previously allowed
at most 4,000 characters. A typical 1,000-word prompt exceeded that contract;
word count alone does not determine character length. This revision raises the limit
to 16,000 characters. DK-200 tests and earlier enrichment evals establish the historical
behavior only; DK-300 has separate recognition and integration tests.

## Ownership and existing pieces

“Content type” covers several namespaces; keep them distinct instead of inventing
one parallel registry in the glossary.

| Recognized family | Canonical owner and existing support | Meaning supplied to intent |
|---|---|---|
| Project terminology | Configured glossary surface, normally `docs/glossary.md`; `knowledge/native_types/glossary_term.py` extracts authored headings and definitions | Canonical term and a bounded definition |
| Document genre | `config/doc_types.json` owns the frontmatter enum, descriptions and deprecated aliases | Namespace `doc_type`, canonical value and its declared meaning; e.g. `how-to` resolves to `how_to` |
| Knowledge destination kind | `config/entry_kind_vocabulary.json` owns members and routing metadata | Namespace `entry_kind`, canonical value and destination role; a path alone is not a full semantic definition |
| Native artifact kind | `knowledge/native_types/registry.py` owns supported readers and labels; each native schema/store owns its fields and identity | Namespace `native_kind`, canonical kind and a short package-authored role; e.g. `AcceptanceCriterion` with display label `AC` |
| Functions, classes and methods | Source declarations; `kernel/capabilities/retrieval/chunking.py` already parses Python and resolves `Name` / `Class.method` spans | Fully qualified identity, bounded signature and optional first docstring sentence; no implementation body |
| Artifact IDs | Canonical stores and their validators/readers; native AC, ADR, decision, flow and ticket readers already expose identity and provenance | Kind, exact ID, short title and canonical reference; no criteria, decision rationale or full artifact body |

Use existing trusted parsers to build projections, not full native records in the
intent request. In particular, the AC reader retains all YAML fields: project just
the identity and title. `scripts/ac_store/ac_parent_id.py` explains the hierarchy;
parent derivation is not ID validation. Reuse the canonical AC validator and actual
store membership, including four-digit roots and nested suffixes. Other IDs use
their own owner’s syntax and membership, not the AC regular expression.

The glossary may explain “content type” and reference these owners through its
normal triage workflow. It should not list every type, ID, function or class again.
New aliases or semantic descriptions belong with the relevant owner. Until an owner
declares an alias, do not guess one from spelling similarity.

## Recognition, resolution and projection

1. Preserve the verbatim goal. Keep explicitly supplied conversation, observations
   and host capabilities in a separate caller-claim channel. Registered capability
   IDs describe configuration; they do not prove runtime health.
2. Read a permission-filtered local entity index for the selected repository
   snapshot. Match the admitted goal and bounded caller text in one deterministic
   pass. Extract glossary phrases, type names, code identifiers and owner-valid ID
   candidates. Ordinary unmatched prose yields no repository query.
3. Resolve exact names through typed index keys. Project a compact meaning for each
   resolved identity; preserve ambiguity and explicit unknown references. Repeated
   mentions share one card. Stop at fixed lookup and output bounds.
4. Checkpoint this interpretation context and its limitations once, before intent.
   Jev receives the unchanged goal plus permitted compact context and caller claims.
   An explicit output contract still controls routing. Recognition makes no Jev,
   embedding, network, host-work or human calls.
5. After intent, supported routed capabilities use resolved canonical references
   as optional retrieval hints. They read bodies, callers, relations and precedent
   only when needed for that task. A meaning card cannot stand in for task evidence.
   Resume reuses the interpretation checkpoint; later evidence records its own
   snapshot and provenance rather than silently refreshing initial meanings.

For phrases, use Unicode-aware identifier boundaries, case-fold glossary/type names,
and prefer the longest declared phrase within a family. Keep code symbols and IDs
case-sensitive under their owner’s rules. `AC` must not match inside `CACHE`;
`TaskInput` must not match inside `TaskInputExtra`. Quoted code and examples may
contain valid mentions but confer no instruction authority. A generic word such as
“reference” is a document genre only with a type cue (`type: reference`, “reference
document”) or an explicit declared alias. It must not turn every prose use into a
type hit. Repetition, uppercase spelling and substring frequency add no relevance.

Prefer an explicit `path.py::Class.method` or module-qualified symbol. A short name
resolves automatically only when unique among permitted candidates. Do not choose
the first filename when multiple modules define `run` or `Task`. Return up to three
bounded candidate identities and an unresolved-ambiguity marker; a path supplied
in the goal can disambiguate. Same-spelling matches in different namespaces remain
distinct candidates unless an owner declares equivalence. A referenced ID that is
validly shaped but absent is `unknown_id`, not evidence that the artifact exists.
Owner syntax errors stay `invalid_reference`; unsupported language symbols stay
`unsupported_kind`. Unmatched ordinary words are simply ignored.

Unknowns do not automatically force a question. “Implement a new FooWidget” can
route as change without FooWidget existing. Ask only after intent if ambiguity
changes the requested work or a necessary user choice. Definitions never supply
user preferences, authorize a command, prove that an AC is fulfilled, or answer
whether the kernel is available now. Recognizing change intent does not add a
change execution capability or extend the caller's permissions.

## A derived local index, with no broad fallback

Index construction is separate from a run’s initial pass. Reuse native readers and
existing source parsing through trusted, package-owned adapters. Extend symbol
extraction to produce qualified identity/signature metadata; the existing Python
span resolver is not yet a repository-wide symbol recognizer. The first version
supports Python symbols only, using AST declarations. Other languages remain
explicitly unsupported until reviewed adapters exist; they are not claimed as
recognized by filename or text heuristics. Never import repository code to discover
declarations.

The index is disposable derived data: repository/workspace identity, source snapshot,
schema version, reader coverage and source hashes identify it. Authors update the
canonical source, not cached cards. Update changed files outside pre-intent work;
a dirty checkout requires an index fingerprint that includes those changes rather
than just HEAD. A missing, stale, invalid or unavailable index yields an explicit
partial/unavailable result, with affected families omitted. It must not trigger a
repository crawl, BM25, embeddings, `*` search, graph-neighbor expansion or a complete
index rebuild inside intake. The routed capability can retrieve evidence later.

Permission filtering happens before matching or disclosing index entries. A broad
cache must not leak the existence, name, title, path, signature or hash of a denied
entity into a narrower run. Apply configured source IDs, read roots, deny globs,
resolved-path/symlink checks and data-policy redaction to both index use and later
direct lookup. Missing `read_repo` cannot be bypassed via a cached index. Caller
text and retrieved definitions are untrusted data, never executable rules.

Readers that validate a whole native store carry their complete validation dependencies
in the index. If current permissions exclude a dependency, recognition withholds that
owner kind and reports partial coverage. This conservative rule prevents a denied record's
parse or validation outcome from changing visible cards or coverage. Python parse failures
are tracked per permitted source. Freshness uses stored filesystem metadata and source hashes;
it does not claim tamper-proof detection of an adversary restoring every metadata field.

New native decision and flow sources have `automatic_research: false`: they support index
preparation and explicit source or canonical-reference lookup after routing without changing
ordinary automatic research selection. Each later lookup reapplies current permissions.

## Implemented bounds and contract

These defaults are configured by `entity_context` in the kernel configuration:

| Bound | Default |
|---|---|
| Admitted goal | 16,000 characters, unchanged in checkpoint and classification |
| Supplied caller text considered for recognition | 12,000 characters, newest conversation first after the full goal |
| Distinct candidate lookups | 64, with explicit IDs/qualified symbols first, then typed/longest phrases, then unique short names; deterministic source-offset tie-break |
| Returned identities, including ambiguity alternatives | 16 total, at most three alternatives per ambiguous mention |
| Definition/purpose text per identity | 300 characters, respecting sentence boundaries when possible |
| Serialized entity context | 8,000 characters including names, signatures, provenance, unknowns and limitations |
| Explicit unknown references | Eight, names capped at 128 characters, sharing the same serialized budget |
| Recognition deadline | Two seconds against an already available index |

Scan the entire admitted goal before selecting the bounded candidate set, so a term
at word 999 remains eligible. Repeated terms consume one identity slot. Extra prose
does not increase reads, cards or Jev calls. Maintain counts of detected, resolved,
returned and omitted candidates; distinguish an incomplete scan from an omitted
card. Never silently classify a prefix after a scan deadline.

Long goals use coordinated changes to `TaskInput`, goal payload/schema,
adapters, effective-goal handling, provider projection and tests. The current Jev
`max_state_chars` default is 60,000: the exact serialized request, including the
base classifier envelope, goal, caller claims and cards, must fit that receiver’s
configured limit. The 8,000-character card cap is not permission to exceed it.
Reserve the unchanged goal and required classifier fields first; trim optional
caller/card projections with counts and limitations. If the required request cannot
fit, reject it explicitly before classification. Never split a long goal into
independent intents or silently discard its tail. Oversized submissions remain
validation errors; supporting unbounded prompts is outside this concept.

The `EntityContext` contract replaces the initial `evidence` excerpt list with
`entities`, `unresolved`, `coverage`, `budgets` and `limitations`; caller context and
registered capability IDs remain separately typed. Each entity carries family,
canonical identity, matched surface/offsets, compact meaning, resolution state and
source provenance (source ID, canonical locator, snapshot, source hash and retained
projection hash). The checkpoint retains admitted mentions; the provider projection
may keep just a representative span and occurrence count to fit its shared budget.
States are `resolved`, `ambiguous`, `unknown_id`, `invalid_reference` and
`unsupported_kind`; whole-pass outcomes are `recognized`, `no_matches`, `partial`,
`unavailable` and `disabled`. The new versioned contract is separate from legacy
`gathered`/`no_evidence` enrichment checkpoints.

Illustrative projection, with hashes/snapshot populated from real sources at runtime.
The function purpose below is a hand-authored illustration of its declaration
docstring; production cards take purpose only from authored metadata/docstrings:

```json
{
  "status": "recognized",
  "entities": [
    {
      "family": "doc_type",
      "identity": "how_to",
      "matched": "how-to",
      "meaning": "Task-oriented procedure: step-by-step, narrow scope.",
      "source": "config/doc_types.json#/doc_types/how_to"
    },
    {
      "family": "symbol",
      "identity": "kernel.context_enrichment.gather_context",
      "meaning": "Function returning initial context; permissions and goal remain unchanged.",
      "source": "kernel/context_enrichment.py::gather_context"
    }
  ],
  "unresolved": [],
  "limitations": []
}
```

The production symbol card also carries its bounded declaration signature. A mention
of `DK-200a-1` would add only its validated type, ID, source title and canonical
locator. Neither mention causes the function body or AC criteria to be attached.
The original “run the kernel” question should receive the glossary meaning of
`Decision Kernel` only if a canonical owner explicitly declares `kernel` as its
alias; absent that declaration, retain the unresolved referent and caller context.
Do not invent a Leafcutter/product definition just to make this example look complete.

Trace the pass as recognition, resolution and projection under the existing
pre-intent scheduler boundary. Record index fingerprint/coverage, per-family counts,
ambiguous/unknown counts, lookup work, elapsed time, serialized sizes, truncation
reasons and zero enrichment Jev calls. Respect redaction in traces. Intent and later
research are distinct spans, so avoided searches and actual later evidence reads
can be measured separately. Meaning-only provenance must be distinguishable from
answer evidence in checkpoints, host artifacts and provider projections.

## Acceptance and evaluation before implementation is called done

Use a labeled recognition corpus independently of downstream answer quality. Exact
entity identity, offsets, alias resolution, ambiguity, provenance, permissions,
budgets and lookup counts are deterministic assertions; report precision and recall
by family and coverage, not just one overall score. Separately compare intent labels
and clarification behavior against the current baseline with the same caller context.
Do not claim fewer calls in an entire run merely because enrichment itself uses none.

| Case | Required result |
|---|---|
| 1,000-word admitted prompt with ordinary prose and `DK-200a-1` near the end | Full goal preserved; exact ID remains eligible; no broad search; fixed lookup/output limits. A separate >16,000-character case fails admission explicitly. |
| Same long prompt repeating one glossary term 100 times | One canonical card; repetition cannot crowd out distinct entities or enlarge retrieval work. |
| Ordinary prose without known entities | `no_matches`, zero body retrieval and no enrichment-owned clarification. |
| “reference this value”, `CACHE`, `TaskInputExtra` | No spurious genre, AC or TaskInput match. |
| Explicit `how-to` type and qualified function | Canonical doc type and signature/purpose cards; no complete document or function body. |
| `run` defined in two permitted modules | Bounded alternatives, no first-file winner; qualified path resolves exactly. |
| Valid but absent AC ID, malformed ID, new FooWidget | Honest unresolved states; change intent may proceed without a user question. |
| Denied path, symlink escape, or cached entity outside read roots | No identity or metadata disclosure and no cache-based permission bypass. |
| Missing/stale symbol index or unsupported source language | Explicit family coverage limit; no crawl or lexical-search fallback. |
| Long glossary definition, 100 distinct IDs, smaller receiver budget | Honest omitted counts, exact serialized limit enforced; original goal retained. |
| Definition containing “ignore previous instructions” | Data only; no policy, permission or output-contract change. |
| Live availability question or approval-dependent decision | Meanings establish terminology only; later observation/evidence or human approval is still required. |
| Human/host resume and dirty-snapshot change | Initial checkpoint reused; later evidence has separate provenance and changed snapshots remain visible. |

The BA and IT PO agents derived and reviewed the [DK-300 hierarchy](../acceptance-criteria/decision-kernel/DK-300-entity-context/DK-300.yaml)
before the test writer and Python coders implemented this revision. Each leaf links
its behavioral tests. An independent evaluator added adversarial regressions and
returned defects to the coder for repair. Historical DK-200 evidence and direct-gather
compatibility are preserved. The four fresh-run wiring criteria DK-200a-1, DK-200a-1-i,
DK-200a-2 and DK-200a-4 were explicitly reconciled to EntityContext on 2026-10-04;
their earlier contracts remain in Git history. Product-truth implementation status is generated from the linked ACs;
review readiness remains distinct from implementation and no human approval is implied.
The [verification report](../../reports/entity-context-verification.md) records the actual
test results and their limits separately from this design contract.
