# IT-PO learnings — agent assignment by technical surface (leafcutter)

Captured 2026-06-16 during BO-210 / GE-102 technical enrichment.

## The BA tends to assign python-coder uniformly; re-route by surface

When the BA decomposes a feature it often stamps every leaf AC with
`assigned_agent: python-coder`, even for behaviors whose real implementation
surface is NOT Python. The IT-PO must re-assign by the file the work actually
edits:

- **`python-coder`** — `.py` only. Pre-commit hook scripts under
  `scripts/commit_guardian/` and `templates/commit-guardian/check_*.py`,
  build/config round-trips of `.claude/*.json` + `templates/scripts/.../*.json`
  (the JSON is edited and round-tripped by build.py, so it is python-coder work),
  and `commit_guardian.json` hooks_manifest edits (e.g. adding a `tier` field).
- **`llm-expert`** — `templates/skills/*/SKILL.md`, `templates/agents/*.md`,
  `templates/workflows/*.md`. ANY behavior whose implementation is prompt /
  skill-body / agent-template text: auto-fix re-dispatch routing in the
  precommit-autofix SKILL.md, capsule-emission instructions in the coder agent
  templates (python-coder.md/sql-coder.md/frontend-coder.md), signoff SKILL.md
  capsule documentation, depth-cap / no-sub-agent / shell-convention rules that
  live in template bodies. These are the most commonly mis-assigned ACs.
- **`documentation-expert`** — `docs/**/*.md` how-tos and references.
- **`architecture-diagram-author`** — C4 / sequence / state diagrams.

Rule of thumb: if the criteria describe what an AGENT or SKILL should DO/SAY
(routing logic, prompt instructions, what a coder emits in its sign-off), the
surface is a template/skill body -> `llm-expert`, not python-coder.

## workflow-architect is NOT dispatchable as a ticket-phase agent

`workflow-architect` owns the create-hook / add-skill / add-agent skills, but it
is `tier: supervisor` and `is_ticket_phase: false`. The AC-build loop dispatches
ticket-phase agents only, so an AC assigned to workflow-architect risks being
undispatchable. For hook scaffolding + manifest registration, assign
`python-coder` and put the create-hook scaffold pattern (config key +
hooks_manifest entry with `tier` + doc-index row, ordering transform-before-
validator) in `it_requirements` instead. Confirmed with the user on GE-102c.

## Cross-component contracts: expects_from is single-valued

The AC `expects_from` field holds ONE `{ac_id, contract}`. When a consumer AC
depends on several upstreams (e.g. BO-210c-1 needs the capsule + the
AUTOFIX_AGENT line + blocking_hook_ids + the manifest tier), keep the primary
upstream in `expects_from` and capture the rest as explicit `it_requirements`
plus cross-component `depends_on` entries (per the BA convention that
cross-component links travel via depends_on). Same-folder `covered_by` only.

## Config/template parity is a recurring it_requirement

For any AC editing `.claude/*.json` or `templates/commit-guardian/*.py`, add an
it_requirement that the deployed file and its packaged template source are
edited together and verified in parity via the build.py round-trip — never edit
one side only. This is a standing leafcutter self-hosting constraint (ADR-001).

## Documentation gate fallback

If a feature ships new user-facing behavior (new hooks) but no parent L1 carries
`documentation_triggers`, the S7b gate is technically skipped — but still flag
the missing how-to coverage as a caveat and offer to author a
`documentation-expert` L2 AC (with `origin_agent: it-po`) depends_on the
behavioral ACs. Done here as GE-102e.

## Feedback-automation routers: .js workflow + Python helpers = python-coder; classifier judgment = llm-expert

Captured 2026-06-17 during ACD-1500 (feedback-router) technical enrichment.

A "router" feature that turns the feedback corpus into shipped work decomposes
into two surfaces, and the BA again stamped all leaves `llm-expert`:

- **Orchestration / queue-build / routing-matrix / confidence-gate / per-run-cap /
  protected-branch guard / resolve-loop / dedup / rate-limit** lives in a NEW
  depth-0 workflow (`templates/workflows-js/feedback-router.js`) plus shelling
  out to existing Python helpers (`scripts/feedback/aggregate.py --unresolved`,
  `resolve_feedback.py`, `submit_feedback.py`, `roadmap_query.py`). Assign all of
  this to **`python-coder`** (the .js workflow body + Python script glue). It is
  NOT llm-expert work even though it is "agent automation".
- **Per-entry judgment** (work_type ∈ {bug-fix,feature,improvement}, size ∈
  {S,M,L}, confidence 0.0-1.0, codifiability) lives in a NEW Haiku-pinned
  classifier agent template (`templates/agents/feedback-classifier.md` +
  `agent_registry.json` entry), dispatched at depth 1 per ADR-006. Assign these
  leaves to **`llm-expert`**. Determinism-across-runs ACs belong here too (pin
  Haiku + temp 0 in the prompt), not on the python orchestration side.

Standing it_requirements to capture IN the YAML (not just the report) for this
class of feature:

1. **submit_feedback.py allowed_writers is a BLOCKING config prerequisite.**
   `config/feedback_categories.yaml` gates category+writer; `process-finding` is
   `allowed_writers: [hook]` ONLY, so a router emitting process-finding is
   rejected (exit 1) until either a new router writer id is PR-added or the
   router emits with hook source. The vocabulary is PR-gated (closed) — flag the
   config decision explicitly as a build prerequisite.
2. **New tunables need a config home, not hard-coding.** confidence_floor,
   per_run_artifact_cap, protected_branches (default [main,master]), and a
   process-feedback rate-limit all belong in a NEW `config/feedback_router.yaml`;
   name the keys in it_requirements.
3. **ADR-006 depth-1 rule recurs:** the router is depth-0 and dispatches the
   classifier at depth 1; it must NOT chain a build supervisor inline. Put this
   in it_requirements on every orchestration/routing leaf.

Idempotency, atomicity (resolve only after confirmed artifact), and fail-safe
(missing roadmap -> park, not assume-aligned) are the recurring policy-level
it_requirements for self-improvement loops — state the WHAT, let python-coder
pick the HOW.

## selection_criteria DSL has no negation/derived-path: "X-without-its-Y" triggers are llm-type (llm-expert), the paired hook is python-coder

Captured 2026-06-17 during GE-104 (enforced-page-docs) technical enrichment.

The agent_registry selection_criteria DSL (scripts/selection_criteria_evaluator.py,
ADR-018) parses only positive atoms `<field> <op> <value>` with op in
{contains, equals, matches} over {files_touched, title, description, components},
combined with AND/OR. There is NO negation operator and NO way to correlate one
files_touched entry with the ABSENCE of a second, DERIVED entry. So any trigger
of the shape "a new X is added WITHOUT its derived doc/companion Y" is NOT
expressible as a dsl-type condition.

Resolution pattern (do this, don't extend the grammar for a one-off):
- Author the trigger as `{ type: "llm", expression: <NL judgment> }` per ADR-018's
  two-tier model. documentation-expert already carries llm-type conditions.
- Known limitation to record IN the AC: llm-type conditions currently raise
  LLMEvaluationRequired and the business-analyst caller falls back to
  default_status until the LLM eval path is wired -> the planning-time trigger
  degrades to not-firing. So pair it with a commit-time HOOK as the authoritative
  backstop; planning-time stays advisory.
- Assignment: authoring a registry trigger EXPRESSION (judgment semantics) is
  **llm-expert**. The companion commit_guardian hook script + the hooks_manifest
  entry + config section is **python-coder**. Same feature splits across both.

## Shared deterministic derivation must be ONE helper across commit-time + planning-time

When the same path->path mapping (e.g. page site/app/<route>/page.tsx ->
docs/reference/frontend/<name>.md) is needed by both a commit hook and a planning
trigger, mandate a SINGLE shared pure helper module (here:
scripts/commit_guardian/frontend_page_docs.py) and forbid inlining the rule in
either layer — otherwise the two enforcement points drift. Pin the algorithm
concretely in the L3 it_requirements: hyphen-join lowercased route segments;
normalize dynamic [param] -> p_param (and [...param]/[[...param]] -> p_param);
raise loudly on unknown route shapes rather than emitting an ambiguous path.
Wire it via delivers_to (producer) / expects_from (consumer) so the contract is
explicit. New-page detection = set-difference present-now minus present-before
(robust to git rename heuristics; deletions produce empty added-set = no gate).

## A pre-commit hook CANNOT call jcodemunch (or any MCP tool) — MCP is an LLM-agent channel only

Captured 2026-06-22 during GE-111 (traceability-stays-honest) technical enrichment.

The jcodemunch family (search_symbols / find_references / get_blast_radius) is
exposed ONLY as MCP tools (mcp__jcodemunch__*). Per ADR-006 / docs/agents/
conventions.md §4.2 the strict research-delegation rule strips these even from
coding agents — only research-agent holds them. A commit_guardian hook is a plain
Python subprocess invoked by git: it has NO MCP channel at all. So any AC whose
criteria say "resolve the symbol via jcodemunch tooling" inside a HOOK is not
literally implementable as written — the BA's "symbol-analysis tooling" must map
to one of: (a) shell out to a CLI/index binary (mirror check_duplicate_code.py
shelling out to jscpd), or (b) in-process resolution (Python stdlib `ast` over the
staged blob). Recommended default for the Python-heavy leafcutter repo: in-process
AST as the primary resolver (zero dependency, always available, deterministic);
treat cross-language CLI resolvers as optional add-ons behind a fail-open ladder.
Always check whether a "use the MCP tool X" instruction is targeting an AGENT
(MCP available) or a HOOK/script (MCP unavailable) before enriching.

## Fail-open ladder is the standard shape for an optional external resolver in a hook

The check_duplicate_code.py jscpd precedent is the canonical fail-open template:
degrade to advisory-skip (exit 0, file-floor still authoritative) on {binary/index
absent, unsupported language, version-incompatible CLI, subprocess timeout, non-zero
exit / parse error}. Each branch catches a SPECIFIC exception
(OSError/FileNotFoundError/TimeoutExpired/SubprocessError/SyntaxError) and logs at
WARNING (CLAUDE.md error-handling Rules 1-4). State the WHAT (these five signals
degrade the optional tier) in it_requirements; let python-coder pick the HOW. Keep
the always-on FLOOR (here: file-path existence) independent of the resolver so the
guarantee survives any tooling unavailability. Also: an in-hook fail-open skip is a
silent-to-stderr advisory at commit time — it must NOT enqueue a store-wide rescan
(that is a separate surface). Do not let a "scope = staged-only" commit gate get
conflated with a store-wide scan.

## Version-aware "confirmation" records: structured amended_by entry + content fingerprint

When an AC behavior is "confirm the code still satisfies this despite a structural
change, and re-flag if the source changes AGAIN", the durable, version-aware record
is a STRUCTURED amended_by entry (schema permits object items; ACS-400 /
check_ac_governance lists amended_by as implementation-agent-writable, so no
write-lock collision — no new top-level field needed). Shape: { reason: '<feature>-
confirm', entry: '<the implemented_by value confirmed>', source_fingerprint:
'<sha256 of the confirmed source>', confirmed_at, confirmed_by }. Version-awareness
= the fingerprint is sha256 of the STAGED source (whole-file blob at file tier;
symbol source span at symbol tier); clears the block iff stored == freshly
recomputed; a later source edit makes them differ so it auto-re-flags. Content-
driven staleness, no TTL. Mandate ONE shared pure fingerprint helper used by BOTH
the write path and the verify path so they cannot drift. Per-link via the 'entry'
key so confirming one link never masks a sibling. Boundary: a confirmation may
clear a moved/renamed verdict on a SURVIVING file only — never a deleted-file
verdict.

## L0/L1 composite ACs are NOT enriched — only L2/L3 leaves get assigned_agent + it_requirements

In GE-111 the BA had already stamped assigned_agent/complexity/contracts on the 18
L2/L3 leaves; the IT-PO job was almost entirely it_requirements + resolving the two
deferred open questions + tightening contract shapes. The 6 composite ACs (L0
GE-111, L1 GE-111a/b/c/d/e) correctly carry NO assigned_agent — leave them. The
single-valued expects_from convention recurred (GE-111e-1 consumes both the verdict
object AND the routes content): keep the primary upstream in expects_from, capture
the secondary in it_requirements.

## implemented_by source-presence check: extract-don't-import the audit loader; #anchor parsing is the only NEW resolution step

Captured 2026-06-22 during ACS-900 (deprecation-hygiene) technical enrichment.

A "block when a RETIRED AC still claims live code" hook reuses cross_reference_audit.py's
AC-loading (_load_ac_yamls: load each AC dict + read implemented_by). Two load-bearing
distinctions to pin in it_requirements:
- REUSE means EXTRACT the loader into an importable shared module both the audit script
  and the new hook depend on — NOT import-from-CLI and NOT copy-paste. Mandate a
  no-regression guarantee on the audit script's existing --apply/CLI behavior after the
  extraction. (Anti-duplication ACs like ACS-900e-1 get a delivers_to naming the helper.)
- The audit script's implemented_by reads are ticket-path-oriented and NEVER check
  SOURCE-file existence. So the source-presence verdict + #anchor parsing
  (implemented_by entries may carry a "path#anchor" suffix the audit never splits) is
  GENUINELY NEW behavior, correctly in-scope, NOT a duplication. Pin: parse on first '#';
  evaluate presence against the STAGED tree (so same-commit deletion reads as absent);
  anchor presence = dependency-free substring/identifier search, NO AST/parser (file
  existence + anchor-token-found is the floor) — keeps the hook portable.

The single biggest false-positive trap (state it as a hard it_requirement on the
re-point-to-successor pass case): the verdict MUST be computed against the retired AC's
OWN (post-re-point, now-emptied) implemented_by list, never a store-global file set. An
intact file that moved to the successor's implemented_by is therefore not the retired
AC's target and is correctly not flagged. De-scope successor-claim verification (don't
couple the block to cross-AC reconciliation) — emptying the retired AC's own list passes.

## ac-store deprecation hook = python-coder (all behavioral) + the 4-how-to/1-component-diagram doc split

ACS-900's five L1s decompose to a single new check_*.py under scripts/commit_guardian/
(deployed) + templates/commit-guardian/ (package source) + a commit_guardian.json
hooks_manifest entry => python-coder on every behavioral + wiring leaf (11 leaves). No
llm-expert child (unlike ACS-800f) — there is NO prompt/skill/template-prose surface.
Documentation: how-to triggers => documentation-expert (kept the embedded Mermaid
sequenceDiagram INSIDE the how-to as ONE documentation-expert AC rather than splitting to
architecture-diagram-author — avoids a trivial diagram AC and satisfies both [how-to,
sequence-diagram] triggers); the standalone component-diagram trigger => one
architecture-diagram-author AC. Recurring it_requirements for this hook class: (1) always-
block-on-real-violation is user-confirmed and must NOT be relaxed to a config warn tier
(distinct from GE-100/101 optional warn/strict); (2) fail-open-on-INTERNAL-error is
orthogonal — reproduce the check_ac_governance.py tail (try/except Exception + noqa BLE001
+ exit 0 + stderr prefix), stdout stays clean on error so it's never mistaken for a
violation; (3) deployed/template parity via build.py (ADR-001) on the hook AND the
manifest (canonical source = templates/commit-guardian/commit_guardian.json, config/ copy
is a build output); (4) hooks_manifest entry carries tier:'judgment' like its siblings.


## A pre-dispatch gate in /build-feature has TWO enforcement surfaces -> split python-coder + llm-expert, shared probe helper

Captured 2026-06-22 during BO-100d (EPIC-CodeQualityHooks KI-3, feedback-sink
pre-drive hard-block) technical enrichment.

/build-feature has two dispatch paths that BOTH must enforce any "before any
ticket runs" gate, or the gate silently leaks:
- `templates/workflows/build-feature.md` — slash-command PROSE (Step A worktree
  -> Step B dispatch). Surface = template prose -> **llm-expert**.
- `templates/workflows-js/build-epic.js` — the deterministic JS workflow that
  build-feature.md Step B delegates to (Claude Code >= 2.1.154). It has Step 0
  worktree-guard / Step 1 planner / Step 4 parallel() dispatch. The JS gate is
  the AUTHORITATIVE one; the prose path delegates to it. Surface = .js workflow
  body + Python probe-helper glue -> **python-coder**.

The KI-3 lesson made concrete: a gate that hard-blocks in build-feature.md but
NOT in build-epic.js silently reintroduces the bug (the JS path bypasses the
prose). So the "hard-block before dispatch" L2 was SPLIT one-per-surface
(python-coder build-epic.js gate + llm-expert build-feature.md prose parity),
NOT left as a single python-coder AC. The build-epic.js Step 0 worktree guard is
the precedent shape for a blocking pre-dispatch gate (typed blocked-result
return, mirror its abort prose).

Decomposition pattern to reuse for any pre-drive/pre-dispatch gate:
1. Factor the actual check as ONE shared probe helper (here: append-one-line +
   mkdir-and-reprobe + genuine-write-failure classification). Make it the
   delivers_to producer (the python-coder build-epic.js AC) and wire every other
   leaf's expects_from to it so the two surfaces cannot drift.
2. The deterministic-surface AC (python-coder) OWNS the helper + the JS gate.
3. The prose-surface AC (llm-expert) REUSES the helper via expects_from and only
   adds the gate step to the command markdown.
4. Edge-case L3s (mkdir-remediate, genuine-failure-hard-block, remediate-then-
   proceed) are all the SAME helper surface -> python-coder, no further split.
   Re-point their depends_on/expects_from from the superseded parent to the
   surviving helper AC (the producer), not to the prose sibling.
5. Standing it_requirement on EVERY leaf: dual-surface parity (both gates
   hard-block) + before-dispatch placement + idempotent probe + ADR-001
   deployed/template build.py parity.

Recurring framing note: "warn-only was insufficient -> must hard-block" repeat
findings (here TICKET-20260527-FeedbackSinkPreDriveCheck) belong in the AC
`notes` as lineage, and the non-bypassable/not-advisory intent must be an
explicit it_requirement so a coder doesn't restore a soft warn.

## Standing flag: build-orchestration is NOT in docs/acceptance-criteria/index.yaml despite prefix BO

The whole docs/acceptance-criteria/build-orchestration/ tree uses prefix BO, but
index.yaml has no `build-orchestration` / `BO` component entry (registered
neighbours: build-pipeline=BP, plus supervisor_system in components.json). This
is a known store-registry gap — surface it at the final gate for the user to
decide whether to register it; do NOT self-register (out of IT-PO scope).
</content>

## A whole merge-gate parity check is single-agent python-coder: the .js workflow IS the gate home, no llm-expert split

Captured 2026-06-22 during BP-1000 (EPIC-CodeQualityHooks KI-2, source<->template
script parity merge gate) technical enrichment.

The natural home for a new pre-merge gate is templates/workflows-js/finalize-feature.js,
whose existing Step 2 (merge origin/main into worktree --no-commit) -> Step 3 (post-merge
tests + HALT on regression) -> Step 4 (merge PR to main) structure gives an exact
insertion point: a new pre-merge parity step between Step 2 and Step 4 that HALTs on drift,
mirroring the Step 3 test-regression HALT. The `finalize-feature` agent in agent_registry is
is_ticket_phase:false (the .js workflow superseded it per the deprecation), so do NOT split
out an "llm-expert finalize-feature prose change" child — there is no prose surface in scope.
The .js workflow-body edit + the standalone Python diff module are BOTH python-coder (same
rule as ACD-1500: ".js workflow body + Python script glue = python-coder"). No multi-agent
boundary -> no split. All six behavioral leaves stayed python-coder; the three doc leaves
(component-diagram=architecture-diagram-author, how-to + reference-doc=documentation-expert)
covered the parent L1 documentation_triggers, so the S7b gate passed with no new doc AC.

## Concrete mirrored-pair vs source-only enumeration for build-pipeline parity scope (reusable)

The scope filter (BP-1000d-1) is NOT abstract — there is a real present false-positive class.
Mirror pairs that EXIST today (scripts/<group>/ has a templates/scripts/<group>/ counterpart):
ac_store/, commit_guardian/, sync_platforms/. Source-only directories with NO templates/scripts/
counterpart (must be EXCLUDED, never compared): agent-health/, changelog/, ci/, doc_compliance/,
feedback/, knowledge/, proposals/, release/, retrospective/, workflows/, worktree/. Bake this
concrete enumeration into the d-1 it_requirements so the coder has the exact in/out sets, and
mandate the scope be DERIVED from mirror-directory presence (never a hardcoded allowlist) so it
tracks reality as pairs are added/removed. Anchor the in-scope/exempt rule to ADR-013
(portable=consumer-facing has a templates/scripts/ source; package-internal is exempt) — "a new
script enters scope by gaining a templates/scripts/ counterpart" == "becoming portable per ADR-013".

## Self-referential-recursion guard for a parity tool that lives under scripts/

When the parity diff module itself is placed under scripts/, decide explicitly whether it is
consumer-facing. Expected case: it is a merge-gate-only dev tool (like scripts/ci/, scripts/workflows/)
with NO templates/scripts/ counterpart, so it is correctly source-only and EXEMPT from its own check
(no parity recursion). If instead it is deployed, ADR-001 forces the build.py round-trip (canonical
source edited, templates/scripts/ regenerated). Capture this as a conditional it_requirement and, if the
deploy decision is genuinely open, raise it as a caveat at the final gate rather than guessing.

## Verdict-object as the load-bearing single producer; reporter is a second consumer with its own delivers_to

BP-1000a-1 produces ONE verdict object { ok, pairs:[{source_path, template_path, identical, diff}] }
that a-2 (block), a-3 (pass), c-1 (report), d-1 (scope) all expects_from. Pin the shape concretely in the
producer's delivers_to (field names, repo-root-relative POSIX paths, source-vs-shipped diff orientation,
ok=true iff all identical) so the four consumers cannot disagree. The reporter (c-1) is itself a producer
to the how-to (c-2): give c-1 a delivers_to:documentation-expert naming the human-readable failure layout,
and wire c-2.expects_from to it, so the doc teaches the exact labels the coder emits. Byte-exact equality
(no whitespace/EOL/trailing-newline normalization) and enumerate-ALL-drifted-pairs (never stop at first)
are the two recurring it_requirements for a parity/diff producer.
