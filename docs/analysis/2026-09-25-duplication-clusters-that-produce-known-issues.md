---
title: "Worktree creation is not the only thing built seven times: twelve duplication clusters that keep producing known issues"
description: "Follow-up to the worktree consolidation analysis. Three read-only audits (workflows, Python scripts/hooks/build, prompts/docs) found twelve concerns that are re-implemented per site instead of shared, traced each to the known issues it caused, and found the same failure shape everywhere: a shared helper exists but few callers use it, 'could not check' reads as a pass, and a KI fix lands in one copy only."
type: explanation
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - build_orchestration
  - commit_guardian
  - ac_store
  - ac_driven_dev
  - build_pipeline
  - testing_quality
  - feedback_collector
related_docs:
  - docs/known-issues/README.md
---

# Worktree creation is not the only thing built seven times: twelve duplication clusters that keep producing known issues

`docs/analysis/2026-09-25-worktree-creation-consolidation.md` showed that worktrees are made by seven divergent
recipes and that the divergence caused a string of known issues. This page asks whether that is a one-off. It is
not. The same shape recurs in at least twelve other concerns, across all three layers of the package.

**Verdict.** The package does not lack shared components — it has many, and they are mostly unused:

| Shared helper that exists | Adoption |
|---|---|
| `commit_guardian/_resolve_root.py` | ~26 of ~56 root-resolving files; ~30 hand-written resolvers remain, and the shared one is itself wrong (KI-CG-20260925-shared-root-resolver…) |
| `_authored_change.get_authored_change()` (change-set derivation) | 2 of 72 hooks |
| `check_outcome.OUTCOME_COULD_NOT_CHECK` | 3 of 72 hooks |
| `_ac_store_index.get_ac_index` (cached store index) | 5 hooks + `done_proof`; ~40 private `rglob` walks elsewhere |
| `scripts/set_ticket_status.py` | no workflow calls it; 5 other recipes write `status: done` |
| `scripts/ac_store/approve_acs.py` | referenced by no prompt; plan-feature hand-edits `readiness` via status-checker |
| `scripts/ticket_prioritizer.py` | no caller; two planners and `prioritize.py` re-implement it |
| `emit_knowledge.py` | referenced by no template; four hand-written JSON appends |
| `_fl_lifecycle._update_ac_work_status` (hardened AC writer) | fast lane only; 8+ other writers are unhardened |

Three failure shapes explain almost every linked KI:

1. **Fixed here, not there.** At least 20 cases where a KI's fix reached one copy and the siblings kept the bug.
2. **"Could not check" reads as a pass.** Workflows default unreadable replies to `ok` / `"unknown"` / null; hooks
   exit 0 after inspecting zero files; validators ignore the path they were given.
3. **Prompts re-implement scripts.** Where a script exists, prompts hand-write the same procedure and drift from it.

The structural cause on the workflow side is ADR-030: workflow bodies have no `require` and no filesystem, so
every shared concern is either copy-pasted ("keep them in sync") or re-typed into a prompt.

## 1. Ranked clusters

Severity is the worst linked outcome. "Filed" marks KIs opened on 2026-09-25 from this analysis.

### C1 — Proving and marking done (blocker)

"Is this AC proven, and who may write `done`?" is answered independently by the pre-commit hook, the CI oracle,
the pytest plugin, the fast lane, two unregistered hooks, `mark_ac_done.py`, `_xref_apply`, an agent prompt, and
five ticket-status recipes.

- **Six `# covers:` readers** disagree on where a tag is valid (`test_enforcement.py:57`,
  `check_done_proof.py:296-303` whole-file, `done_proof.py:770-821` inside-a-test, `check_test_ac_tags.py:46`,
  `check_ac_coverage.py:41`, `ac-fulfillment-gate.md:252` prefix `grep`).
- **Five leaf/composite definitions**; the `test_required: false` waiver reaches leaf paths but not the composite
  paths (`check_done_proof.py:468-478`, `done_proof.py:1636-1641`); CI never checks children's `work_status`.
- **Parametrised ids judged by first case** — filed KI-ACS-20260925-done-proof-parametrised-first-match.
- **Async / decorated tests misattributed** — filed KI-ACS-20260925-done-proof-credits-tags-to-the-wrong-test.
- **`mark_ac_done.py`** does an unanchored replace, edits prose, leaves the key `todo`, prints success and turns LF
  into CRLF (reproduced on a copy of `BO-202.yaml`) — filed KI-ACS-20260925-mark-ac-done-reports-success…; five of
  its six callers omit `--test-root`, so the oracle never runs.
- **Ticket `status: done`** is written by status-checker hand-edits (`build-feature.js:1114`, `build-ticket.js:955`),
  a regex in finalize (`:1599`), `ticket-supervisor.md:172`, `pull-request.md:231` and the guarded script; parity
  enforcement is keyed on the retired `/done/` folder — 51 tickets read done with `pull-request: needed` — filed
  KI-CG-20260925-signoff-parity-enforces-only-under-done-folder.

Linked open KIs: CG-006, CG-013, CG-20260908-covers-tag, CG-20260914-done-proof-precommit-ignores-test-required,
CG-20260901-covers-regex, ACS-004, ACS-006, ACS-008, ACS-20260914-composite-proof-drops-path-leaves, BO-022,
BO-023 (reproduced), BO-20260826-1900, BO-20260831-1930/1932, BO-20260907-0803, TQ-20260914-1050.

**Consolidate into:** one `ac_proof` module (AST tag parsing incl. async/decorators and multi-id tags; `is_leaf`;
`is_waived`; `run_tests` requiring every parametrised case); one `ac_record.set_field` (column-0, byte-exact line
endings, atomic, re-parse-verified); `set_ticket_status.py` as the only status writer, emitting JSON; drivers set
`in_progress` on dispatch.

### C2 — How workflows run shell commands and read agent replies (blocker)

- **62 dispatches to status-checker** (`permits_shell: false`): plan-feature 27, finalize 20, build-feature 7,
  build-ticket 4, build-epic 2, fast-lane 2 — including finalize's `reset --hard` (`:1562`), raw `git commit`
  (`:1646`) and `worktree remove --force` (`:655`), and plan-feature's `apply-approval` YAML edit (`:3424-3429`).
- **Five reply-reading styles**: engine schema; four byte-identical `parseAgentJson` copies; fast-lane
  `coerceReleaseReply`; build-feature's double `JSON.parse`; bare `JSON.parse(output.trim())`. plan-feature and
  finalize make 85 `agent()` calls with zero schemas.
- **Fallbacks invert failure**: plan-feature PR delivery treats unreadable as `ok` (`:807`, the KI-BO-007 shape);
  finalize "assuming no PR" / "assuming zero tickets closed" / `worktree_root: "unknown"`; build-epic falls back to
  the epic folder.
- **The harness default stub returns `{status:'ok', exit_code:0}`** and never models a refusal (KI-BO-009).

Linked KIs: BO-020 (fixed in fast-lane only), BO-20260901-1620, ACD-005 and ACD-009 (fixed in plan-feature only),
BO-018, BO-007, BO-019, BO-027, BO-20260908-1030, BO-20260831-1932, BO-20260907-0804, and the 2026-09-25
`/plan-feature` incident.

**Consolidate into:** `runCommand(cmd)` bound to one agent with `permits_shell: true`, returning
`{status: ok|refused|error, exit_code, stdout, stderr}` under a schema; `callAgent(prompt, {schema})` where the
schema is mandatory and a refusal or unreadable reply is always `error`; a lint test comparing every workflow
`agentType` with `permits_shell`; deterministic reads moved to pre-flight `args` (the ACD-009 pattern).

### C3 — Human approval gates (blocker)

`resolveGate` / `pauseAtGate` are hand-copied between plan-feature and finalize; the KI-ACD-005 and KI-ACD-004
fixes reached plan-feature only. finalize still answers gates through a live agent call and has no
`channel === "person"` check, in front of "merge PR to main" — filed KI-BO-20260925-finalize-gate-accepts-agent-answers
(code-verified; merge path inferred). Separately, each confirmation-gated agent treats "no user present"
differently: `commit.md` has a supervised path keyed on `ticket_path`; `pull-request.md` has none; workflows paper
over it with "do NOT ask" prose or forget (finalize `:949`, `:2097`; plan-feature's commit dispatch passes no
`ticket_path`). `building-epics` §5.7 tells the coordinator to complete refused steps with raw git/gh — the
opposite of KI-SS-20260826.

**Consolidate into:** one gate block inlined by the build with a parity test; one `authorization` field in the
dispatch payload that every gated template reads.

### C4 — Finding the project root and building paths (high)

~30 hand-written root resolvers in six strategies with five failure behaviours; the shared `_resolve_root`
accepts the non-repository workspace parent (filed KI-CG-20260925-shared-root-resolver…); `docs_root` is honoured
on write and ignored on read (`build.py:1350-1353` — KI-BP-016 still live, and `build-self.sh:18` still issues the
command CLAUDE.md:523 forbids); workflow script paths are cwd-relative everywhere except plan-feature's repo-anchored
resolver; AC-store CLIs default to cwd-relative `docs/acceptance-criteria` (`approve_acs.py:402`,
`mark_ac_done.py:216`, `scan_ac_orphans.py:581`); `path_resolver.py` + `paths.json` has one importer, which passes
the wrong keyword; 41 files hard-code `docs/acceptance-criteria`.

Linked KIs: CG-20260914-ac-hooks-resolve-root-from-cwd, CG-009, CG-018, CG-024, CG-027, CG-028, ACD-004, ACD-009,
ACD-019, BP-001, BP-016, BP-20260907-1620 (the last three are one defect), BO-20260921-worktree-base-resolver.

**Consolidate into:** `subject_root(cwd) -> Path | NO_REPO` and `install_root()`; `paths.docs_root()` /
`paths.resolve(key)`; one workflow `scriptCmd(relPath)`. The worktree component must share these rules.

### C5 — Which files a hook checks, and what it reports (high)

~45 private `git diff --cached` queries in 9 filter spellings (the AC gates use `AM` and miss renames); merge
handling in three generations (first-parent-only in five hooks, octopus-safe in two, full operation record in two,
none in five); four test-seam dialects; `commit_guardian.json` marks 70 of 72 hooks `handed_by_commit_path` while
most derive their own diff, and `change_set_source.py` only polices `self_derived`. `could_not_check` exists and
three hooks emit it; the rest exit 0 on zero inspected files. `check_ac_schema.py <path>` ignores its argument
(filed KI-CG-20260925-check-ac-schema-path-argument-is-ignored).

Linked KIs: CG-20260826-1612, CG-20260907-renames, both CG-012 entries, CG-001, CG-018, CG-019, CG-002,
CG-20260914-ratchet-max-baseline, CG-20260831-glossary-detector.

**Consolidate into:** `_change_set.staged(root, include=AMR, under=…, exclude=…)` built on `_operation_record`;
one seam; fail closed if the seam is set but empty; `run_hook.py` maps `could_not_check` and "0 inspected when
files were expected" to non-zero; a census test fails any hook that emits no RESULT line.

### C6 — Commit, push, PR and merging `origin/main` (high)

- **8+ commit recipes**: five staging policies (`add -A` in fast-lane `:1674`; `add -u` in precommit-autofix;
  exact-name-only in plan-feature, which never stages the parent; "all in scope" in building-epics §5.6; "stage by
  name" in commit.md); three retry policies; the delegation hook matches the literal `"git commit"` so
  `git -C … commit` (five prompt sites) bypasses it — filed KI-CG-20260925-commit-delegation-hook-misses-git-dash-c.
- **No commit lock** in any driver (KI-BO-20260901-0920).
- **Merge / freshness** exists only as CLAUDE.md prose (fetch, then `git diff origin/main --numstat` must show no
  deletions). finalize Step 2 checks ancestry *before* fetching; `ship` and `close-worktree` still
  `git push origin main` onto a PR-only branch.
- **Six push/PR copies**, five hard-coding `gh auth switch --user urlmonitor` — filed
  KI-BO-20260925-templates-hardcode-a-personal-gh-account.
- `commit.md` Step 0 `pkill -f pytest` and bare `git stash` — filed KI-BO-20260925-commit-agent-pkill-kills-parallel-test-runs.

Linked KIs: BO-029, BP-20260831-1334, CG-20260907-password, CG-016, BP-014, BO-20260914-co-author-trailer,
BO-20260914-autofix-depth, BO-20260909-worktrees-go-stale, BO-007, CG-001.

**Consolidate into:** `commit_changes.py` (explicit path set, message from file with caller's trailer,
`--supervised`, probe → autofix → one retry, JSON); `sync_with_main.py` (fetch, rebase/merge, additive-only audit,
halt on deletions); `open_pr.py` (account from config, `GH_TOKEN` cleared, body from file). The delegation hook
parses argv.

### C7 — Running tests (high)

`AC_ENFORCE_STRICT` is set in quick-fix, `done_proof` and CI only, so test-writer, test-runner and finalize run
with not-done ACs masked as xfail — test-writer's "exit 0 means re-run until red" then pushes it to rewrite correct
tests. "Red" means *all* new tests failing with ImportError counting (test-writer) vs *at least one* with ERROR
inconclusive (`fast_lane.py`). `test_command*` config keys are written and never read; trading-project suite tables
(`live_trader/**`) remain in test-runner, python-coder, ship and `workflows/test.md`. finalize baseline and
post-merge runs use different runners; no fast-lane or quick-fix full-suite/ruff step; no ruff pre-commit hook.

Linked KIs: TQ-011, TQ-010, TQ-20260901-1655, TQ-20260908-node-check, TQ-004, TQ-20260831-mutation-probe,
BO-20260831-1520, BO-010, TQ-20260914-1050.

**Consolidate into:** `run_tests.py --scope ac|full [--baseline]` — always strict, `sys.executable`, rebuild or
refuse when stale, outcome `passed|failed|error|incomplete`; `verify_red_baseline` as the only red definition;
suites rendered from one `testing.commands` block.

### C8 — Deploy set and hook registration (high)

The deploy set is declared in ~26 hand lists (only three families derive theirs); `build_deploy_manifest_helpers`
carries dead copies that disagree with the live ones; six `ac_store` files are in no deploy map though prompts
reference two of them; `build_precommit.py:270` looks hook scripts up by basename in the wrong directory. A hook
must be registered in ~9 places; `precommit-autofix.json` lists three unregistered `blocking_hook_ids`, the deployed
copy is the legacy `{"routes": {}}` schema and is written only if absent, so the autofix tiers are dead; post-merge
and commit-msg shims are installed only by `setup_ticket_worktree.py`.

Linked KIs: BP-018 (blocker), BP-005, BP-20260907-0940, BP-20260921-1630, BP-20260831-0728, CG-20260831-manifest-shadowing,
CG-020, CG-20260914-post-merge-shim, TQ-20260914-fixtures-hand-enumerate, BP-011, BP-004.

**Consolidate into:** one declarative deploy manifest iterated by every phase, the closure guard, clean mode and
drift checks; `hooks_manifest` as the single registration source generating the autofix list, README table, CI id
lists and shim stages.

### C9 — AC schema validation (medium-high)

`validate_ac_schema.py` and the `check_ac_schema` hook (which CI runs) enforce disjoint rule sets — registry and
`readiness`/`priority` only in the former, test-contract and `declares_side_effect` only in the latter; the
components enum is copied and already drifted (44 vs 45); `validate_ac.py` still has the KI-ACS-001 bare-directory
no-op (filed KI-ACS-20260925-validate-ac-bare-directory-exits-0); `check_v2_ac_store_alignment.py` cannot see 92% of
the store (filed KI-ACS-20260925-v2-alignment-flat-lookup-misses-feature-folders).

Linked KIs: ACS-20260907-validator-weaker, ACS-009, ACS-20260909-standalone, ACS-011, ACS-003, CG-014, CG-015,
BP-20260901-0914.

**Consolidate into:** one `validate_record(rec, ctx)` called by the hook (staged set) and a CLI (paths); enum
derived from `docs/components.json`.

### C10 — Ticket status vocabulary and "what to build next" (high)

Five status sets (`set_ticket_status.py` accepts `inbox`, the guard does not; `blocked` is unreachable even with
`--force`); the build-feature and build-epic planners are LLM prompts omitting only `done`; `prioritize.py` treats
in-progress and blocked as ready (filed KI-BO-20260925-prioritize-py-treats-in-progress-and-blocked-as-ready);
`ticket_prioritizer.py` has the right sets and no caller.

Linked KIs: BO-20260907-0803, BO-20260907-0804, BO-025, BO-026.

### C11 — Sub-agent nesting worked out in prose (high, inferred)

At least nine prompts use a "soft cap depth 3" model; ADR-019 makes phase agents depth 1, where any Agent call is
dropped. So research-agent delegation from 29 templates, pull-request → conflict-resolver and commit → autofix fixer
are dropped calls. Registry/template mismatches: `commit` has the Agent tool with an empty allowlist;
`business-analyst` and `build-ac` have allowlists without the tool; `status-checker` is told to call a
non-existent `prod-puller`. Only the autofix instance is filed (KI-BO-20260914-autofix-re-dispatch).

### C12 — Feedback, telemetry and knowledge sinks (medium)

Four anchoring schemes for one `feedback.jsonl` (writers fall back to `.leafcutter/debugging/logs/`, readers to
`<project>/debugging/logs/`); ticket-supervisor passes a cwd-relative `--jsonl`; every telemetry call passes an
explicit `--log`, which bypasses the declared-sink fix; the pre-drive probe checks `agent_telemetry.jsonl`, not
`feedback.jsonl`; five phase agents are in no category's `allowed_writers` and the documented `[all_agents]`
sentinel is unimplemented; `emit_knowledge.py` is used by no template.

Linked KIs: FC-001, FC-002, FC-003, BP-017, KM-011, KM-010, BO-012.

**Consolidate into:** one `sinks.resolve(kind)` over the build-time declaration; drop `--log`/`--jsonl` from
prompts; a non-appending `--check-writable` probe.

## 2. Known issues filed from this analysis

| KI | Severity | Cluster |
|---|---|---|
| KI-ACS-20260925-done-proof-parametrised-first-match | blocker | C1 |
| KI-BO-20260925-finalize-gate-accepts-agent-answers | blocker (inferred path) | C3 |
| KI-ACS-20260925-mark-ac-done-reports-success-without-writing-the-key | high | C1 |
| KI-ACS-20260925-done-proof-credits-tags-to-the-wrong-test | high | C1 |
| KI-CG-20260925-signoff-parity-enforces-only-under-done-folder | high | C1 |
| KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent | high | C4 |
| KI-CG-20260925-check-ac-schema-path-argument-is-ignored | high | C5/C9 |
| KI-CG-20260925-commit-delegation-hook-misses-git-dash-c | high | C6 |
| KI-BO-20260925-templates-hardcode-a-personal-gh-account | high | C6 |
| KI-BO-20260925-build-single-ticket-treats-ticket-path-final-as-worktree-path | high | worktree / C4 |
| KI-BO-20260925-prioritize-py-treats-in-progress-and-blocked-as-ready | high | C10 |
| KI-ACS-20260925-validate-ac-bare-directory-exits-0 | high | C9 |
| KI-ACS-20260925-v2-alignment-flat-lookup-misses-feature-folders | high | C9 |
| KI-ACS-20260925-fix-ac-orphans-flush-left-lists | low (latent) | C1 |
| KI-ACS-20260925-derive-parent-id-copies-disagree | low | C1 |
| KI-CG-20260925-frontmatter-guard-truncates-at-in-value-dashes | low | C1 |
| KI-BO-20260925-commit-agent-pkill-kills-parallel-test-runs | low | C6 |

Not filed (observed but thinner evidence, or better recorded against an existing KI): ~12 agent templates declare
`handoff` outputs without `handoff_target` (update KI-BO-20260901-1045/1052); five phase agents missing from
`allowed_writers` (update KI-FC-003, which names two); 41 live references to the retired `/create-ticket` and six
orphan deployed agents (update KI-BP-005); `generate_ticket_from_ac` re-parsing the store ~4× per ticket (update
KI-ACD-017); `live-surface-tester` emitting `(status: skipped)` outside the signoff enum.

## 3. Register hygiene

These entries look fixed or stale in code but are still filed open. Each needs a test run before moving to
`resolved/`: KI-BO-20260907-0850, KI-ACD-006, KI-BO-018, KI-BO-20260901-1045/-1052 (fixed for 2 of ~14 agents),
KI-BO-032, KI-CG-024, KI-CG-017, KI-CG-021, KI-BP-010, KI-BP-019 (fixed in `template_compiler` only),
KI-ACS-20260914-mark-ac-done-refuses-every-test-required-false-leaf, KI-ACS-20260901-1730, KI-KM-010,
KI-ACD-014, KI-ACD-018, KI-BO-022 (fast-lane half), KI-BO-014. KI-CG-032 says "not on main" but is on main
(`e429421e`) and reproduces. KI-BP-20260910-1240 is filed resolved but its own L24 says "partially". KI-BP-001,
KI-BP-016 and KI-BP-20260907-1620 are three entries for one defect.

## 4. Suggested order

1. **Stop the silent-success writers first** — cheap and each is a single file: `mark_ac_done`, `approve_acs`,
   `validate_ac.py`, the parametrised first-match, the parity gate's folder key. Then reconcile the 51 tickets.
2. **C2 + C3** in one epic: the workflow runner/reply/gate modules. They share the ADR-030 inlining mechanism
   (marker-delimited blocks + parity test), which is the same mechanism the worktree helper needs.
3. **C4** together with the worktree component, so both use one root/path resolver.
4. **C1 proper** (`ac_proof`, `ac_record`), then **C5/C9** (change set, outcome, one validator).
5. **C6–C8, C10–C12** by blast radius.

Every step goes through `/plan-feature` per the ticket mandate; this page is the evidence base, not a plan.

## Method

- Three parallel read-only analysts, one per layer (`templates/workflows-js/` + harness; `scripts/`,
  `templates/scripts/`, `config/`, build phases; agent/skill/command templates, how-tos, both CLAUDE.md files and
  `config/agent_registry.json`), each told to exclude worktree create/locate/remove and to tie every cluster to KIs
  under `docs/known-issues/`. Two were resumed once to finish areas left unverified; helper sub-analyses covered
  the done-proof oracle, AC YAML writers and the deploy layer.
- Probes (scratchpad only, no repo writes): `root_probe.py` (resolver variants from three cwds), `phantom.py`
  (tickets `done` with `needed` agents), `reg_vs_tpl.py` (registry vs template frontmatter), `fd.py`
  (function-body diffs of twinned workflow helpers), `probe_ids.py`, and fixtures for `mark_ac_done`,
  `approve_acs`, `_gtfa_implemented_by`, `fix_ac_orphans`, `_fl_lifecycle` (KI-BO-023), `validate_ac.py` and
  KI-CG-032.
- The main session re-read the load-bearing lines of each filed KI before filing.
- **Not verified by running:** the finalize merge-gate path (C3), sub-agent depth drops (C11), `GH_TOKEN`
  precedence (C6), where status-checker's `apply-approval` edits land, and every `yaml.safe_dump` writer against
  the KI-ACS-017 multi-line case. Line numbers are as of 2026-09-25 on `main` and will drift.
