---
title: "An ineligible assigned_agent is substituted and says so, and a finished goal stops telling you to decompose it"
date: "2026-09-23"
time: "10:40"
type: manual
components:
  - ticket_creation_pipeline
  - ac_driven_dev
  - ac_store
summary: "The last four specification-only ACs from the dropped-test batch are built and green. A generated ticket no longer names an agent the ticket-supervisor cannot dispatch: an assigned_agent that is not is_ticket_phase, or not in the registry at all, is substituted for python-coder or llm-expert by surface and a WARNING names the substitute, the original and the AC id. Separately, goal_to_epic stops giving one message for two different zero-leaf conditions — a goal whose leaves are all done or superseded now says so instead of telling you to decompose leaves that are already decomposed. Five ACs marked done. A deployed run caught a defect that would have made the substitution a no-op on every consumer install."
description: "Built by hand, two coders in parallel on non-overlapping files, after /fast-lane-build proved untrustworthy (KI-BO-20260921). The red baseline was salvaged from branch salvage/gte-eight-ac-tests and seeded unchanged: 10 failed, 7 passed under AC_ENFORCE_STRICT=1 against current main; after implementation 17 passed, 0 failed, verified by the coordinator rather than taken on report. git diff shows all four seeded test files as PURE ADDITIONS — no test edited, weakened, skipped or xfailed. THE DEFECT THE DEPLOYED RUN CAUGHT, which is the most important thing here. _gtfa_phase_agent.py's first version resolved the agent registry at <root>/config/agent_registry.json — the worktree-relative convention its neighbour _gtfa_agents_inputs._resolve_config_path uses. A consumer install keeps config at <root>/.leafcutter/config/. So on EVERY consumer install the registry read would have failed, the module would have logged 'the ticket-phase eligibility check is skipped', and the ineligible agent would have been emitted verbatim — the entire feature a silent no-op, while every source-tree test stayed green. Found only by building to an isolated target and invoking the deployed copy. Fixed with _registry_candidates(), which probes <root>/config/ then <root>/.leafcutter/config/. Independently re-confirmed by the coordinator in a consumer-shaped tree: first candidate missing, second EXISTS. WHERE THE SUBSTITUTION LIVES, and why not where it was first aimed. The coordinator pointed at _gtfa_agents_map.py; the coder read it and went one layer up to _ac_inputs in _gtfa_cli.py, because _build_agents_map has 62 direct unit-test call sites across ~28 files, several passing fixture registries whose agents have no is_ticket_phase key at all (rust-coder, totally-new-lang-coder) and asserting those names survive into the map. Substituting there would have rewritten them and produced failures unrelated to these ACs. _ac_inputs is also the better seam on the merits: it is the generator's single read-the-AC's-assigned_agent point, it feeds both the preview and the write path, and the goal path shells out to the same script — one call site covers both generators with no second branch to drift. It leaves ac['assigned_agent'] itself untouched, so the ticket body's Context prose still records what the AC said (explicitly out of scope per the test file's own header) while only the dispatch plan — the agents: map and the Sign-offs list derived from it — is corrected. THE SUBSTITUTION RULES. is_ticket_phase is True: returned unchanged, no log record (the control). Entry exists but is_ticket_phase is anything else: substituted, warned. No registry entry at all: substituted, warned with DISTINCT wording naming the registry miss, per TKT-500f-5-i's third it_requirement. assigned_agent is None: returned untouched, so _gtfa_agents_inputs._require_work_agent's TKT-600b-5 refusal still fires rather than being silently satisfied by a substitute. substitute_for_surface() is the single place the branch rule lives — any files_touched entry under templates/agents/ or templates/skills/ yields llm-expert, otherwise python-coder — and the unknown-agent path calls the same function so it cannot acquire a private default. Eligibility is read from the real registry: _load_registry_entries reads agent_registry.json off disk and the verdict is entry.get('is_ticket_phase') is True, with no agent-name allow/deny list anywhere in the module. The test drives all 60 real registry entries (24 phase / 36 non-phase) through the generator and both arms come back empty. Goal-path parity was proven by running epic_tickets.generate_tickets_for_leaves as a real subprocess against a throwaway store and reading the ticket back off disk: no workflow-architect or made-up-agent entry survives in either the agents: map or the Sign-offs list on either path. THE ZERO-LEAF DIAGNOSTIC. goal_to_epic emitted one message for two distinct conditions. New pure helper _zero_leaf_diagnostic in epic_ac_phases.py distinguishes them by re-running the traversal with both exclusions off: a non-empty unfiltered set proves the leaves exist on disk and were removed by the filter (goal finished or retired), an empty one proves there are no L2/L3 descendants at all (goal never decomposed — ACD-1200a-3-i's case, whose wording is untouched and was confirmed byte-identical by running the real CLI). Same store, same function, so the two walks cannot disagree about what exists. The new message interpolates the real count rather than hardcoding it. traverse_ac_tree is passed in as a parameter rather than re-imported, preserving the call-time-lookup property the existing docstring calls out so a test that patches the name still sees its patch on the unfiltered re-walk. No new module, so no deploy-manifest change — confirmed rather than assumed. ACD-1200f-2-i WAS ALREADY GREEN, AND THAT WAS CHECKED RATHER THAN ACCEPTED. All three of its tests passed against unmodified main, which is indistinguishable from a blind test on a green result. Verdict after mutation: genuinely covered. Disabling only the `in seen` early return in _dfs_collect_leaves (leaving seen.add in place) turned 2 of 3 tests red with exactly the duplicate the AC exists to prevent — ['ROOT-002a-1', 'ROOT-002a-1-i', 'ROOT-002a-1-i', 'ROOT-002a-2']. The third staying green is correct: those leaves are not diamond-reachable, so it is a breadth check rather than the discriminator. The probe was run on an isolated /tmp copy, never in the shared worktree, so the parallel agent would not see a spurious red. THE REGRESSION TEST THE FALLBACK DID NOT HAVE. The registry-location fix shipped with only a one-off manual run as evidence — the same shape as the defect it guards. unit_tests/ac_store/test_tkt_500f_5_i_registry_fallback.py now locks it: a real consumer-shaped root (tempdir + .git + copied modules + registry written with json.dump at .leafcutter/config/ ONLY, asserting <root>/config/ does not exist), driven through a fresh subprocess rather than importlib.reload, asserting both that the resolved agent is python-coder AND that the degrade-path fingerprint 'eligibility check is skipped' is absent from stderr — the return value alone cannot distinguish 'found the registry elsewhere' from 'found nothing and happened to agree'. Registry contents are read from the live registry rather than hand-typed, raising a named AssertionError if the premises stop holding. Mutation-proven: reducing _registry_candidates to the single worktree-relative location turns both tests red with 'workflow-architect' != 'python-coder' — the shipped defect exactly — and the source file was restored byte-identical (md5 match, git status unchanged). AC STATUS. Five marked done through mark_ac_done.py's coverage gate: TKT-500f-5-i and ACD-1200a-10-i and ACD-1200f-2-i as leaves, then TKT-500f-5 and ACD-1200a-10 as composites once their only children were complete. implemented_by is left empty deliberately — this store's convention is that it names ticket files, and this was a direct-commit drive with no ticket. FLAGGED, NOT FIXED, both pre-existing and out of scope: the same worktree-relative config assumption is still live on main in _gtfa_config._load_guardrail_gates / _load_production_code_agents, so the whole COMPUTED agents-map path and guardrail_gates.yaml are unreachable on consumer installs — worth its own AC. And scripts/commit_guardian/check_test_ac_tags.py does not recognise letter/Roman-suffixed ids like TKT-500f-5-i: it reports 'missing a # covers: XX-NNN tag' against the new file and equally against the already-merged seeded files with identically-formatted tags, so it is a gap in that validator's regex rather than a tagging defect. It is warning-only, and both machine readers that matter — pytest_ac_enforcement and the strict plugin — parse the tags correctly. NOT COVERED: the genuinely-unreadable-registry path (a file that exists at a candidate but is corrupt, hitting _read_registry_file's warn-and-try-next branch) is the other half of TKT-500f-5-i's third it_requirement and remains untested; and no deployed-angle unit test was added, because CLAUDE.md prohibits new build.py spawn sites (77 existing at 59.8s each) — the copy-into-temp-root approach gives the same layout shape in 0.27s but does not prove manifest membership."
commits:
breaking: false
---

## Entry

The last four specification-only ACs from the dropped-test batch are built and
green. **17 passed, 0 failed** under strict AC enforcement, from a salvaged red
baseline of 10 failed / 7 passed. All four seeded test files are **pure
additions** — nothing was edited or xfailed to reach green.

### An ineligible agent is substituted, and says so

A generated ticket no longer names an agent the ticket-supervisor cannot
dispatch. An `assigned_agent` that is not `is_ticket_phase`, or absent from the
registry entirely, is substituted — `llm-expert` for agent/skill-template
surfaces, `python-coder` otherwise — and a WARNING names the substitute, the
original, and the AC id. The unknown-agent case gets distinct wording, because
an `assigned_agent` that does not exist is almost always a typo, and
substituting it silently hides the typo forever.

`assigned_agent: None` passes through untouched, so the existing TKT-600b-5
refusal still fires rather than being quietly satisfied by a substitute.

### The defect the deployed run caught

The first version resolved the registry at `<root>/config/` — the worktree
convention. A consumer install keeps config at `<root>/.leafcutter/config/`. So
on **every consumer install** the registry read would have failed, the module
would have logged "eligibility check is skipped", and the ineligible agent
would have been emitted verbatim: **the whole feature a silent no-op**, with
every source-tree test green.

Found only by invoking the deployed copy. Fixed with a two-location probe, and
independently re-confirmed in a consumer-shaped tree — first candidate missing,
second present.

### A finished goal stops telling you to decompose it

`goal_to_epic` gave one message for two conditions. It now distinguishes them by
re-running the traversal with both exclusions off: leaves that exist but were
filtered means the goal is complete or retired; no descendants at all means it
was never decomposed — which is `ACD-1200a-3-i`'s case, and its wording is
untouched.

### One AC was already green, and that was checked rather than accepted

`ACD-1200f-2-i` passed unmodified. Green is indistinguishable from a blind test,
so it was mutation-tested: disabling the visited-set early return turned 2 of 3
tests red with exactly the duplicate the AC prevents. Genuinely covered.

### The fallback's missing test

The registry-location fix shipped with a one-off manual run as its only
evidence — the same shape as the defect it guards. It now has a regression lock
built on a real consumer-shaped root, proven by mutation to go red against the
pre-fix code.
