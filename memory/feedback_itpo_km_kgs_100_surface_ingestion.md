# IT-PO learnings — KM-KGS-100 knowledge-graph surface enrichment (knowledge-management)

Captured 2026-06-22 during /create-ac technical enrichment of the KM-KGS-100
tree (count-agnostic knowledge-graph surfaces + AC-store "acs" surface ingestion).
Component: knowledge-management. The BA had already populated assigned_agent,
estimated_complexity, delivers_to/expects_from, and doc_links well; the only gap
was it_requirements: null on all 13 leaves. No splits were needed (each leaf is
single-surface).

## The load-bearing constraint the criteria imply but never name: edge_fields is duplicated

scripts/knowledge_query.py carries a HARD-CODED `_SURFACE_EDGE_FIELDS` dict
(lines ~70-79) that duplicates the per-surface `edge_fields` already declared in
config/paths.json. Multiple KM-KGS-100 criteria ("no surface added to a hard-coded
list", "edge_fields driven entirely by the declared set", "validation iterates over
whatever set is declared", "no special-casing", "add one config entry, rebuild") are
ALL really one technical requirement: make extract_edges + the validator read
edge_fields from the declared paths.json surface entry and DELETE the hard-coded
dict. That dict also does NOT list implemented_by / covered_by, so the acs surface's
new edge fields cannot work until it's removed. Put this in it_requirements on the
edge-production leaf (100a-3), the count-agnostic leaf (100c-1), the no-code-change
leaf (100c-2), and the validation leaf (100d-1) — it is the spine of the whole tree.

## The .yaml-vs-.md ingestion gap is the second hidden constraint

The acs surface points at docs/acceptance-criteria/, whose files are .yaml in nested
subfolders. extract_nodes' directory path globs `**/*.md` ONLY and falls back to the
filename stem for a missing id. The acs surface needs: (a) .yaml ingestion added, and
(b) node id taken from the `id` frontmatter field, NOT the filename stem, and (c)
files with no id field SKIPPED rather than stem-fallback (the store's own index.yaml
is a real no-id file that must not become a node). State these explicitly — the coder
will otherwise reuse the markdown path and silently emit zero acs nodes or spurious
index.yaml nodes.

## Viz legend = a SURFACE_COLORS entry, not a code branch

scripts/visualise_knowledge_graph.py renders the legend only for surfaces present in
the data AND present in the hard-coded SURFACE_COLORS dict (no 'acs' key today). The
"acs appears in the legend" criterion (100b-2) therefore reduces to "add an acs colour
to SURFACE_COLORS"; the viz already delegates assembly to knowledge_query._collect_all,
so nodes/edges flow automatically. Don't let the coder build a second ingestion path.

## component_membership + synthetic hubs: ordering matters for the dead-end validator

The components frontmatter field maps to the `component_membership` edge type, whose
targets are SYNTHETIC hub nodes created inside _collect_all BEFORE the phantom-edge
filter runs. The "every edge points to a real node / drop dead ends" leaves (100d-2,
100d-2-i) must preserve that ordering or legitimate component edges get filtered as
dead ends. The existing filter is already allow-list-free (membership against the full
node-id set) — the it_requirement is "reuse that filter, don't add a special-case",
not "build a new validator".

## Agent assignment confirmed the standing surface-routing rule

BA's pattern held cleanly: behavioral/code leaves (paths.json + knowledge_query.py +
visualise_knowledge_graph.py, all .py/.json round-tripped) -> python-coder; how-to
(100b-3, 100c-3) -> documentation-expert; component diagram (100a-4) + sequence
diagram (100b-4) -> architecture-diagram-author. All three exist and are
is_ticket_phase: true. No re-routing needed — this tree is .py/.json/.md-docs/diagrams
only, no llm-expert (template/skill-body) surface in scope.

## Documentation gate (S7b) passed via parent documentation_triggers

100a:[component-diagram]->100a-4; 100b:[how-to,sequence-diagram]->100b-3+100b-4;
100c:[how-to]->100c-3; 100d:[] -> skipped. Full coverage, no gap-fill AC needed.

## Process note (untracked store)

AC store folders are untracked in this repo, so `git diff --stat` yields empty output;
verification fell back to the schema validator (scripts/ac_store/validate_ac_schema.py
takes positional file paths, no --help) + a grep that it_requirements is populated on
all 13. The .build-feature.lock false-positive warned about by the BA did not recur,
but I wrote files one at a time anyway.
