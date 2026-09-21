---
title: "Commit-guardian orphaned hook triage — KI-TQ-007 / KI-CG-021"
type: reference
status: active
created: 2026-09-14
components: [commit-guardian]
description: "Evidence-based per-script triage of the 18 commit-guardian hook scripts that no hooks_manifest entry invoked, with a register/delete/reclassify verdict and measured would-it-pass figures for each."
---

# KI-TQ-007 / KI-CG-021 — evidence-based triage of the 18 orphaned commit-guardian hook scripts

> **Status note, added 2026-09-14 on filing.** This report was written against `main` at
> `2524993b9`, when all 18 were unregistered. Since then: `check_pytest_style.py` and
> `check_sql_dependencies.py` were **deleted** as bybit-trader residue (PR #794);
> `check_outcome.py` and `check_v2_ac_store_alignment.py` were **reclassified** into
> `hook_parity.excluded_scripts` (PR #802); and the five marked REGISTER were **registered**
> under `GE-120h-3` (PR #808). The live baseline is **9**, and the authoritative per-script
> status is the `UNREGISTERED_BASELINE` comment block in
> `unit_tests/commit_guardian/test_hook_registration_inventory.py`, not the verdicts below.
> What remains valuable here is the **evidence** — the measured violation counts, the git
> archaeology, and the per-script reasoning behind each verdict. Treat the counts as
> measurements taken on that date, not as current figures.


Measured against `main` at `2524993b9` in `/home/henzeh/projects/leafcutter/leafcutter-ai`
(and the identical tree in the worktree `/home/henzeh/projects/worktrees/ki-tq-007`, branch
`fix/ki-tq-007-hook-registration-inventory`, where the inventory test lives).

Registration truth used throughout: `hooks_manifest.hooks` in
`templates/scripts/commit_guardian/commit_guardian.json` (62 entries, 5 of them
`enabled: false`). `.pre-commit-config.yaml`
was never consulted. `unit_tests/commit_guardian/test_hook_registration_inventory.py` was run and
**passes** (2 passed), so the 18-entry baseline is exact as of that SHA.

---

## 1. Summary table

| # | script | `main()`? | ever registered? | unit tests? | verdict | conf |
|---|--------|-----------|------------------|-------------|---------|------|
| 1 | `check_ac_coverage.py` | yes (`:207`) | **yes — legacy manifest only**, `b0feef5c8` 2026-06-04; entry deleted `21d341e38` (PR #134) | yes — `unit_tests/commit_guardian/test_check_ac_coverage.py` | NEEDS-DECISION | high |
| 2 | `hooks/check_ac_done_on_merge.py` | yes (`:183`) | never (`git log -S` empty on both manifests) | yes — `tests/commit_guardian/test_check_ac_done_on_merge.py` | **REGISTER** | high |
| 3 | `check_complexity.py` | yes (`:197`) | never | no | NEEDS-DECISION | high |
| 4 | `check_debug_scripts.py` | yes (`:248`) | never | no | **REGISTER** | medium |
| 5 | `check_doc_coverage.py` | yes (`:308`) | never | no | **DELETE** | med-high |
| 6 | `check_doc_links.py` | yes (`:334`) | never | no | **REGISTER** | medium |
| 7 | `check_docstrings.py` | yes (`:142`) | never | no (only `docstring_validators` indirectly) | NEEDS-DECISION | high |
| 8 | `check_documentation.py` | yes (`:332`) | never | no | NEEDS-DECISION | high |
| 9 | `check_folder_density.py` | yes (`:247`) | never | no | **REGISTER** | high |
| 10 | `check_outcome.py` | **no** — no `main()`, no `__main__` block | never | yes, indirectly — `unit_tests/portability/test_ge_120a_1.py`, `test_ge_120e_1_i.py`, `test_ge_120e_2_i.py`, `unit_tests/product_truth/test_uxp_700c_3_ii.py` | **RECLASSIFY** | high |
| 11 | `check_pytest_style.py` | yes (`:189`) | never | no | **DELETE** | high |
| 12 | `check_root_files.py` | yes (`:56`) | never | no | NEEDS-DECISION | high |
| 13 | `check_sql_complexity.py` | yes (`:105`) | never | no | **REGISTER** | medium |
| 14 | `check_sql_dependencies.py` | yes (`:113`) | never | no | **DELETE** | high |
| 15 | `check_test_ac_tags.py` | yes (`:274`) | **yes — legacy manifest only**, `e6e86497f` 2026-06-04; deleted `21d341e38` | yes — `unit_tests/commit_guardian/test_check_test_ac_tags.py` | NEEDS-DECISION | high |
| 16 | `check_test_fixture_bloat.py` | yes (`:307`) | never | yes — `unit_tests/commit_guardian/test_check_test_fixture_bloat.py` | **REGISTER** | high |
| 17 | `check_ticket_test_requirements.py` | yes (`:138`) | never | yes — `unit_tests/prompt_assembly/test_test_requirements_guard.py` | NEEDS-DECISION | high |
| 18 | `check_v2_ac_store_alignment.py` | yes (`:346`) | **yes — legacy manifest only**, `1fcd2f7c7` 2026-06-04; deleted `21d341e38` | yes — `unit_tests/commit_guardian/test_check_v2_ac_store_alignment.py` | **RECLASSIFY** | med-high |

All paths relative to `/home/henzeh/projects/leafcutter/leafcutter-ai/templates/scripts/commit_guardian/`
unless stated. All 18 are absent from `.github/workflows/*.yml` — the only guardian script CI runs is
`check_done_proof.py` (`.github/workflows/ci.yml:228`).

---

## 2. Counts, and what to do first

- **REGISTER — 6:** `check_ac_done_on_merge`, `check_debug_scripts`, `check_doc_links`,
  `check_folder_density`, `check_sql_complexity`, `check_test_fixture_bloat`
- **DELETE — 3:** `check_doc_coverage`, `check_pytest_style`, `check_sql_dependencies`
- **RECLASSIFY — 2:** `check_outcome`, `check_v2_ac_store_alignment`
- **NEEDS-DECISION — 7:** `check_ac_coverage`, `check_complexity`, `check_docstrings`,
  `check_documentation`, `check_root_files`, `check_test_ac_tags`,
  `check_ticket_test_requirements`

### Highest value first

1. **`check_outcome.py` → RECLASSIFY (do this first, it costs nothing and removes a false positive).**
   It has no `main()` and is the GE-120 shared outcome-vocabulary library imported by
   `run_hook.py:37` — i.e. by the dispatcher that fronts *every single registered hook* — plus three
   registered hooks. It is the most-executed file in the whole directory and the inventory test calls
   it an orphan purely because of its `check_` prefix. Add it to `hook_parity.excluded_scripts`
   (currently `[]`, `commit_guardian.json`) and the baseline drops to 17 with zero behaviour change.

2. **`check_ac_done_on_merge.py` → REGISTER.** Highest value-for-risk of the real hooks: it always
   exits 0 (`:213`, `:221-223`), so registering it cannot block anything, and it closes a real
   automation gap (source ACs are never auto-marked `done` after a merge today). The plumbing already
   supports it — `scripts/build_precommit.py:171-172` renders `stages` verbatim from the manifest, and
   `install_pre_commit_shims.py:87-117` (`collect_stages`) installs a git shim for **every** stage
   declared in the config, not just `pre-commit`.

3. **`check_test_fixture_bloat.py` → REGISTER.** Zero-risk: the `test_fixture_bloat` key does **not
   exist** in `commit_guardian.json` (verified against the 36 top-level keys), so
   `main()` resolves `config = {}` (`:327-337`) and `enabled` defaults to `False` (`:339`), which
   forces the warn-only path (`:392-394`, `return 0`). Register now, add the config block later to
   arm it.

4. **The three `git`-history cases — `check_ac_coverage`, `check_test_ac_tags`,
   `check_v2_ac_store_alignment`.** These are the only three of the 18 that were ever registered
   anywhere, they were all registered on the *same day* into the *same wrong file*, and they were all
   de-registered by the *same commit*. See §4 — deciding them is one decision, not three.

5. **`check_docstrings` / `check_complexity` / `check_documentation` — the "documented, configured,
   routed for autofix, and inert" trio.** These are the worst *reader* trap of the 18: five separate
   surfaces assert they are live (see §4). Whatever the verdict, the five surfaces must be corrected
   in the same change.

---

## 3. Per-script detail

### 1. `check_ac_coverage.py` — NEEDS-DECISION (high)

1. **What.** "Pre-commit hook that verifies every *active* AC in `docs/acceptance-criteria/` is
   referenced by at least one test file's `# covers: XX-NNN` tag" (`:1-21`). Warning-only, always
   exits 0 by design (`:10-13`).
2. **`main()`** — yes, `check_ac_coverage.py:207` (`main(argv)`), `sys.exit(main())` at `:238`.
   Accepts `--ac-dir` / `--test-dir`.
3. **Invoked by** — nothing executable. Named only in prose:
   `templates/docs/how-to/ac-traceability-store.md:169`, `docs/known-issues/commit-guardian.md`.
4. **Ever registered** — **yes, and this is the interesting part.** Commit `b0feef5c8`
   (2026-06-04, *"feat(ticket-04): add check_ac_coverage pre-commit hook"*) added it to
   `hooks_manifest.hooks` of **`templates/commit-guardian/commit_guardian.json`** — the legacy tree.
   `scripts/build_precommit.py` had already preferred the canonical manifest since 2026-05-18
   (`build_precommit.py` DECISION HISTORY at `b0feef5c8:scripts/build_precommit.py:338`,
   "EPIC-PortableInstallHardening/T03: Updated cg_dir to canonical
   templates/scripts/commit_guardian/ with backward-compat fallback"), and the canonical manifest
   existed at that commit (`git cat-file -e b0feef5c8:templates/scripts/commit_guardian/commit_guardian.json`
   → exit 0). **So the hook was born inert**: registered into a file the build only reads as a
   fallback. The entry was then deleted outright with the legacy tree by `21d341e38` (PR #134).
5. **Tests** — yes, `unit_tests/commit_guardian/test_check_ac_coverage.py`.
6. **Superseded?** Largely. `check-done-proof` (registered; also a required CI gate,
   `.github/workflows/ci.yml:228`) enforces the AC→test-proof direction, and
   `scripts/ac_store/done_proof.py` carries the richer tag scanner.
7. **Would it pass?** Ran it: **exit 0, 180 `WARNING: AC <id> has no test coverage` lines.** But it
   is structurally near-blind: `_ID_REGEX` at `check_ac_coverage.py:44` is
   `^\s*id:\s*([A-Z]{2,6}-[0-9]{3,})\s*$` — **anchored to end-of-line**, so a suffixed id such as
   `TQ-100b-4-i` never matches. Measured: **275 of 4,032** AC YAML records carry a bare `id: XX-NNN`.
   It can therefore only ever see ~7% of the store.

   **Decision needed:** given `check-done-proof` already enforces AC→test at commit and in required
   CI, is a whole-store, warning-only reverse sweep still wanted? If yes it needs two fixes before
   registration is meaningful — unanchor the id regex (blind to 3,757 of 4,032 records today) and set
   `verbose: true`, because a *passing* pre-commit hook's stdout is discarded (`KI-CG-026`), so all
   180 warnings would go to /dev/null.

### 2. `hooks/check_ac_done_on_merge.py` — REGISTER (high)

1. **What.** "Post-merge hook that marks source ACs as `work_status: done` when ticket files are
   updated to `status: done` in a merge commit" (`:2-12`). Reads `git diff HEAD~1 HEAD`, parses each
   changed ticket's frontmatter, and shells out to `mark_ac_done.py` per qualifying ticket.
2. **`main()`** — yes, `hooks/check_ac_done_on_merge.py:183`; `sys.exit(main())` at `:216-218`.
3. **Invoked by** — nothing. **The lead in the brief is backwards.** This script is the *caller* of
   `mark_ac_done.py`, not the callee: `_mark_ac_done_for_ticket` shells
   `[sys.executable, mark_ac_done.py, --ticket, …]` at `hooks/check_ac_done_on_merge.py:148-162`, and
   `scripts/ac_store/mark_ac_done.py:6` confirms from the other side — *"Called by
   check_ac_done_on_merge.py post-merge hook (automated) or …"*. Nothing anywhere installs a
   `post-merge` git hook that runs it: `grep -rn "post-merge\|post_merge"` over `scripts/`,
   `templates/scripts/`, `.github/`, `config/` returns only docstrings and unrelated commit-message
   prose.
   **This also means the new test's own inline comment is wrong** —
   `test_hook_registration_inventory.py:81` says *"invoked by scripts/ac_store/mark_ac_done.py, not
   pre-commit"*. It is invoked by nothing; fix that comment.
4. **Ever registered** — never in the canonical or the legacy manifest
   (`git log --all -S"check_ac_done_on_merge" -- <both manifests>` → empty). Historically there *was*
   a `hooks_manifest.post_merge` array in the legacy manifest, holding exactly one entry
   (`check-ticket-state-integrity`), but this script was never in it and that array died with
   `21d341e38`.
5. **Tests** — yes, `tests/commit_guardian/test_check_ac_done_on_merge.py`.
6. **Superseded?** No. Nothing else closes source ACs on merge.
7. **Would it pass?** It cannot fail — the exit code is unconditionally 0 (`:213`) and the
   `__main__` guard swallows `OSError`/`ValueError` into `sys.exit(0)` (`:219-224`). Registration is
   mechanically supported end-to-end: `build_precommit.py:171-172` writes whatever `stages` the
   manifest declares, and `install_pre_commit_shims.collect_stages` (`:87-117`) installs a git shim
   per declared stage.

### 3. `check_complexity.py` — NEEDS-DECISION (high)

1. **What.** "Blocks Python files where any function/method exceeds the cyclomatic complexity limit"
   (`:1-14`), AST-based, threshold from `complexity.max_score`.
2. **`main()`** — yes, `:197`.
3. **Invoked by** — nothing executes it. It is *imported* by another orphan:
   `check_sql_complexity.py:52` (`from check_complexity import calculate_complexities`).
   Referenced in prose at `README.md:37`, `INTEGRATION.md:76`, `templates/agents/commit.md:316`.
   **And it has autofix routing**: `templates/scripts/precommit-autofix.json:14` (mechanical-fix
   allowlist) and `:24-28` (`"hook_id": "check-complexity"` → coder agent). Remediation is wired to a
   gate that cannot fire.
4. **Ever registered** — never. Present since `11dbd26b7` ("Initial commit: extract from
   bybit-trader monorepo"); every manifest hit for its name is a `_comment` string inside its
   *settings* block, never a `hooks_manifest` entry (verified by reading the diffs of `11dbd26b7`,
   `2c2aa2283` and `038258bf1` — the last is a pure re-indentation).
5. **Tests** — none.
6. **Superseded?** **No.** `ruff.toml:36` is `select = ["E", "F", "E722"]` — no `C901`, no
   complexity rule at all. Nothing in the repo enforces cyclomatic complexity today.
7. **Would it pass?** No. Measured over 983 tracked `.py` at `max_score: 15`, applying its own
   `COMPLEXITY_EXCLUDED_DIRS` (`alembic`, `legacy`, `check_complexity.py:142`):
   **79 over-limit functions across 50 files.** Worst: `_build_agents_map` = 75
   (`scripts/ac_store/generate_ticket_from_ac.py`), `_compute_output_mappings` = 65
   (`scripts/build_helpers.py`), `_check_file` = 46
   (`templates/scripts/commit_guardian/check_ac_governance.py`).

   **Decision needed:** the repo already has the ratchet pattern for exactly this
   (`_file_size_ratchet.py`, `_doc_length_ratchet.py`). Is complexity worth a third shrink-only
   ratchet plus 50 grandfathered files, or is it accepted that this repo has no complexity gate? Do
   not leave it as-is — the autofix routing and README row currently tell every reader it is live.

### 4. `check_debug_scripts.py` — REGISTER (medium)

1. **What.** "Enforce metadata tagging on new/modified debug scripts" under `debugging/scripts/`
   (`:1-7`); required tags `DEBUG SCRIPT`, `CATEGORY`, `DESCRIPTION`.
2. **`main()`** — yes, `:248`.
3. **Invoked by** — nothing. `README.md:32` documents it as live blocking hook
   `check-debug-scripts`.
4. **Ever registered** — never (same bybit-trader inheritance as #3).
5. **Tests** — none.
6. **Superseded?** No.
7. **Would it pass?** Vacuously, here: `git ls-files "debugging/*"` returns **nothing** —
   `debugging/` is untracked in this repo. Unlike #11/#14 below its behaviour is entirely
   config-driven (`debug_scripts.valid_categories` / `.required_tags` / `.exempt_dirs`, all populated
   in `commit_guardian.json`), so it is portable and has real value in a consumer project that does
   keep `debugging/scripts/`. Registering costs this repo nothing and gives consumers the gate the
   README already promises them.

### 5. `check_doc_coverage.py` — DELETE (med-high)

1. **What.** "Advisory pre-commit hook that warns when major code changes land without corresponding
   documentation updates" (`:1-13`); three signals; "Never blocks a commit (exit code always 0)".
2. **`main()`** — yes, `:308`.
3. **Invoked by** — nothing. `commit_guardian.json` carries a `doc_coverage` settings block and
   `config.py:229-232` exposes `DOC_COVERAGE_*` constants for it.
4. **Ever registered** — never.
5. **Tests** — none.
6. **Superseded?** Yes — documentation-coverage enforcement now lives in the
   `documentation_gates` section of `config/guardrail_gates.yaml:351` plus the
   `documentation-verifier` phase agent (post-EPIC-DocumentationCoverageGuarantee / BO-2200).
7. **Would it pass?** **It cannot run at all.** Executed read-only:

   ```
   File ".../check_doc_coverage.py", line 324, in main
       default=str(_project_root / "knowledge_graph.json"),
   NameError: name '_project_root' is not defined. Did you mean: 'project_root'?
   ```

   Exit 1, unhandled traceback, on *every* invocation regardless of input. This independently
   confirms the observation already recorded under
   `KI-CG-20260831-hook-scripts-never-invoked` (commit-guardian.md:3036-3037). A one-word fix exists,
   but even fixed, its output is advisory and lands on the passing path where pre-commit discards it
   (`KI-CG-026`). Delete the script, its `doc_coverage` block, and the `DOC_COVERAGE_*` constants.

### 6. `check_doc_links.py` — REGISTER (medium)

1. **What.** "Enforce bidirectional traceability between code files and documentation by validating
   `DOC_LINKS:` references and cross-checking doc frontmatter" (`:1-27`). **"All failures are
   advisory warnings … they never block commits. Exit Codes: 0 — Always."**
2. **`main()`** — yes, `:334`; supports `--file` and `--all`.
3. **Invoked by** — nothing. Documented live at `README.md:36` and `README.md:327`; autofix routing
   at `templates/scripts/precommit-autofix.json:87-91` (`"hook_id": "check-doc-links"`).
4. **Ever registered** — never.
5. **Tests** — none.
6. **Superseded?** Partially overlaps `check-doc-frontmatter` (registered) on the `related_code`
   back-link side; the code-side `DOC_LINKS:` validation is unenforced today.
7. **Would it pass?** Yes — ran `--all`: exit 0 with **13 warnings**, small and actionable. Two
   caveats to fix alongside registration: (a) set `verbose: true`, or the advisory output is
   discarded on the passing path (`KI-CG-026`); (b) its DOC_LINKS parser has a real bug — it reads
   DECISION HISTORY lines as link paths, e.g.
   `WARNING … scripts/add_component.py → DOC_LINKS path '2026-06-08 00:00 [python-coder]: Initial
   implementation per ACS-300g-4a.' does not exist.` (3 of the 13 findings are this false positive).

### 7. `check_docstrings.py` — NEEDS-DECISION (high)

1. **What.** "Enforce Google-style docstrings with Args/Returns on all Python functions and classes"
   (`:1-9`), using `docstring-parser` to catch stale param names.
2. **`main()`** — yes, `:142`; supports `--file`.
3. **Invoked by** — nothing. It *imports* `docstring_validators.py` (`:25-32`), which is imported by
   **nothing else** — so that helper is dead with it. Documented live at `README.md:40`,
   `INTEGRATION.md:88`/`:283`, and asserted as enforced in `templates/rules/documentation.md:78`
   ("*This is enforced by `check_docstrings.py` in the pre-commit hooks*"). Autofix routing at
   `templates/scripts/precommit-autofix.json:15` and `:31-35`.
4. **Ever registered** — never.
5. **Tests** — no dedicated test file; the validators are re-exported "for backward compatibility
   (used by unit tests)" (`:24`) but no test file imports `check_docstrings`.
6. **Superseded?** **No.** `ruff.toml:36` selects only `E`, `F`, `E722` — no `D` rules. The only
   thing enforcing docstrings today is the advisory `doc-enforcer` *agent skill*.
7. **Would it pass?** No, twice over. Measured over the 127 tracked `.py` files that pass its own
   `should_check_file` filter (`excluded_dirs` = `unit_tests, alembic, debugging, legacy, tests,
   templates` — note **`templates` is excluded, so the entire package payload is out of scope**):
   **617 violations across 74 of 127 files.** Sample run on one ordinary file:
   `--file scripts/build.py` → exit 1 with 4 violations. Worse, it **crashes**:
   `docstring_parser.common.ParseError: Expected a colon in 'Nothing — all errors are printed to
   stderr…'` on `scripts/ac_store/scan_ac_orphans.py`, unhandled.

   **Decision needed:** is mechanical Google-docstring enforcement still wanted at all, given ruff
   carries no `D` rules and `doc-enforcer` covers it advisorily? If yes, it needs the `ParseError`
   caught *and* a shrink-only ratchet over 617 findings before it can be registered. If no, delete
   it together with `docstring_validators.py`, its `docstrings` config block, and the four surfaces
   that claim it is live.

### 8. `check_documentation.py` — NEEDS-DECISION (high)

1. **What.** Three rules (`:1-15`): every modified `.py`/`.sql` must have a `README.md` in its parent
   directory; new `.sql` need `Object Name:`/`Goal:`/`Business Context:`; new `.py` need
   `MODULE:`/`GOAL:`/`BUSINESS CONTEXT:`/`ARCHITECTURE:` in the module docstring. Blocking.
2. **`main()`** — yes, `:332`; also `--report-legacy`.
3. **Invoked by** — nothing. It *hard-imports another orphan*:
   `from check_root_files import ALLOWED_ROOT_FILES, ALLOWED_EXTENSIONS` (`:26`) — so
   `check_root_files.py` cannot be deleted without editing this file. It also imports
   `doc_validators.py` (`:32-38`), which is imported by nothing else. Documented live at
   `README.md:33`; `templates/skills/doc-enforcer/SKILL.md:207` tells the agent to run
   `python scripts/commit_guardian/check_documentation.py --report-legacy`.
4. **Ever registered** — never.
5. **Tests** — none.
6. **Superseded?** No registered hook checks Python module headers. `check_doc_frontmatter` and
   `check_output_drift` mention "BUSINESS CONTEXT" only in their own docstrings — grep-verified, they
   do not enforce it.
7. **Would it pass?** No. **35 of the 50 directories containing tracked `.py` files have no
   `README.md`** — including `scripts/ac_store`, `scripts/ci`, `scripts/evals`,
   `templates/scripts/commit_guardian/hooks`, `tests/ac_store`. And **479 of 983** tracked `.py`
   files are missing at least one of the four required header fields (that rule only fires on *new*
   files, but the README rule fires on *modified* ones, so the effective block radius is the 35
   directories).

   **Decision needed:** is "a README.md per source directory" still this project's convention? If
   yes, 35 READMEs must be written before registration; if no, drop rule 1 and register only the
   new-file header rules — those are cheap because new files are written by agents that already
   emit the block.

### 9. `check_folder_density.py` — REGISTER (high)

1. **What.** "Blocks commits when a staged file would cause any directory to exceed the maximum
   allowed number of non-markdown files (default: 15)" (`:1-20`).
2. **`main()`** — yes, `:247`.
3. **Invoked by** — nothing. `README.md:42` documents it live.
4. **Ever registered** — never.
5. **Tests** — none.
6. **Superseded?** No.
7. **Would it pass?** **Yes — it has a shrink-only ratchet built in already.**
   `_classify_folders` (`:236-244`) only raises a *violation* when a folder crosses the threshold *in
   this commit* (`after > limit and before <= limit`); a folder that was already over becomes a
   *warning*. Measured: **113 folders are already over 15** (worst:
   `docs/acceptance-criteria/ac-driven-dev` = 192, `unit_tests/commit_guardian` = 137,
   `templates/scripts/commit_guardian` = 110) — all of which classify as warnings, not blocks. This
   is the one of the nine "configured-but-inert" scripts that is safe to register as-is today.

### 10. `check_outcome.py` — RECLASSIFY (high)

1. **What.** Not a hook. "Declare, in exactly one place, the machine-readable outcome vocabulary that
   commit_guardian pre-commit checks emit when a check could not perform its inspection at all, as
   distinct from a genuine clean pass" (`:1-17`) — the GE-120 `RESULT:` vocabulary
   (`OUTCOME_OK`, `OUTCOME_COULD_NOT_CHECK`, `OUTCOME_NOTHING_TO_INSPECT`, `OUTCOME_NOT_RUN`).
2. **`main()`** — **no.** `grep -n "^def main\|^if __name__"` returns nothing. It is a constants +
   emitter module. This alone settles it.
3. **Invoked by** — imported, not invoked, by the **dispatcher every registered hook runs through**
   and by three registered hooks:
   - `run_hook.py:37` (`import check_outcome`), used at `:412`, `:449`, `:453`
   - `check_contract_shrinking.py:29` (registered as `check-contract-shrinking`)
   - `check_doc_frontmatter.py:127` (registered as `check-doc-frontmatter`)
   - `check_ac_parent_covered_by.py:109` (registered as `check-ac-parent-covered-by`)

   Each import site carries an explicit fallback shim for layouts where the module is absent — so it
   is treated as a deployment-critical shared dependency, not a gate.
4. **Ever registered** — never, and correctly so.
5. **Tests** — yes, indirectly: `unit_tests/portability/test_ge_120a_1.py`,
   `test_ge_120e_1_i.py`, `test_ge_120e_2_i.py`, `unit_tests/product_truth/test_uxp_700c_3_ii.py`.
6. **Superseded?** N/A.
7. **Would it pass?** N/A — it runs on every hook invocation already.

   **The real fix** is either renaming it off the `check_*.py` pattern (e.g. `_outcome.py`, matching
   the directory's existing `_resolve_root.py` / `_operation_record.py` convention — but this is a
   27-plus-importer rename and touches the deploy manifest) **or**, cheaply, adding it to
   `hook_parity.excluded_scripts`, which is `[]` today in *both*
   `templates/scripts/commit_guardian/commit_guardian.json` and
   `templates/commit-guardian/commit_guardian.json`. The inventory test reads
   `excluded_scripts` (`test_hook_registration_inventory.py:131`), so one line clears it from the
   baseline with no behaviour change.

### 11. `check_pytest_style.py` — DELETE (high)

1. **What.** "Rejects pytest-style test functions (top-level `def test_*()`) in
   **`unit_tests/live_trader/`** that are not methods of a `unittest.TestCase` subclass" (`:1-17`),
   because "the pre-commit `run-unit-tests` hook runs `unittest discover`" (`:6-9`).
2. **`main()`** — yes, `:189`.
3. **Invoked by** — nothing. `README.md:48` documents it live; `README.md:395` even warns porters
   that "`check_pytest_style.py` targets `unit_tests/live_trader/` by default".
4. **Ever registered** — never.
5. **Tests** — none.
6. **Superseded?** Its premise is gone: this repo runs **pytest** (`pytest.ini`,
   `.github/workflows/ci.yml`), not `unittest discover`, so top-level `def test_*` is collected
   normally and the silent-skip failure mode it guards against does not exist here.
7. **Would it pass?** Vacuously. `_TARGET_PREFIX = "unit_tests/live_trader/"` is **hardcoded**
   (`check_pytest_style.py:36`) and `git ls-files "unit_tests/live_trader*"` returns nothing. This is
   pure bybit-trader monorepo residue — the header comment at `:32-34` names
   "TICKET-20260511 (EPIC-MarketStructure)" from that repo. It can never match a file in leafcutter or
   in any consumer that is not bybit-trader. **Nothing supersedes it because nothing needs to.**

### 12. `check_root_files.py` — NEEDS-DECISION (high)

1. **What.** "Block commits that add unauthorized new files to the root directory" (`:1-15`), against
   `root_files.allowed_files` / `.allowed_extensions`.
2. **`main()`** — yes, `:56`.
3. **Invoked by** — nothing as a script, but **hard-imported by `check_documentation.py:26`** for
   `ALLOWED_ROOT_FILES` / `ALLOWED_EXTENSIONS` (the alias is declared for that purpose at
   `check_root_files.py:27-28`). Documented live at `README.md:31`.
4. **Ever registered** — never.
5. **Tests** — none.
6. **Superseded?** No.
7. **Would it pass?** **No — and it would block on this repo's own files.** The allowlist is
   bybit-trader's, unchanged since extraction: it permits `app_launcher.py`, `app_launcher_jobs.py`,
   `app_setup.py`, `app_start.py`, `database_queries.py`, `alembic.ini`, `remote_query.sh`,
   `settings.py`, `poetry.lock` — none of which exist here — while the following *real, tracked*
   leafcutter root files are not allowed: **`LEAFCUTTER_VERSION`, `SETUP.md`, `VERSION`,
   `build-self.sh`, `requirements-dev.txt`, `ruff.toml`**. And it fires on modify, not just add —
   `status.startswith("A") or status.startswith("M") or status.startswith("R")`
   (`check_root_files.py:51`) — so any commit that edits `ruff.toml` or `SETUP.md` would be blocked.

   **Decision needed:** rewrite `root_files.allowed_files` for leafcutter (and note that consumers
   inherit whatever you write) and register, or delete the gate. If you delete it, you must also edit
   `check_documentation.py:26`, which imports its constants.

### 13. `check_sql_complexity.py` — REGISTER (medium)

1. **What.** "Enforce SQL cyclomatic complexity limits at commit time" (`:1-14`) via keyword counting;
   threshold `sql_complexity.max_score: 75`.
2. **`main()`** — yes, `:105`.
3. **Invoked by** — nothing. It *soft-imports* `check_complexity.calculate_complexities`
   (`:52`, inside a `try`). Documented live at `README.md:38`; autofix routing at
   `templates/scripts/precommit-autofix.json:150-154` (`"hook_id": "check-sql-complexity"`).
4. **Ever registered** — never.
5. **Tests** — none.
6. **Superseded?** No.
7. **Would it pass?** Vacuously here — `git ls-files "*.sql"` returns **zero files**. Like
   `check_debug_scripts` it is fully config-driven and portable, so registering it is free for this
   repo and delivers the gate the README already promises consumers. Caveat: its fate is coupled to
   `check_complexity.py` via the `:52` import — if #3 is deleted, delete or inline that import in the
   same change.

### 14. `check_sql_dependencies.py` — DELETE (high)

1. **What.** "Enforce SQL dependency tags at commit time … ensures all SQL views and materialized
   views declare their dependencies for the dependency-resolved topological sort loading pipeline"
   (`:1-6`).
2. **`main()`** — yes, `:113`.
3. **Invoked by** — nothing. `README.md:39` documents it live.
4. **Ever registered** — never.
5. **Tests** — none.
6. **Superseded?** N/A.
7. **Would it pass?** Vacuously, but it is **not portable, unlike #4 and #13**: it hardcodes a
   `KNOWN_TABLES` set of bybit-trader trading tables — `candles`,
   `strategy_evaluation_cursors`, `candle_cumulative_stats`, `strategy_templates`,
   `support_resistance`, `queue_strategy_*`, `pnl_trades`, `pnl_trades_v2`, `positions`, `orders`,
   `candle_context`, `symbols` (`check_sql_dependencies.py:16-22`), with the comment "The dependency
   resolver only knows about SQL objects from `sql_functions/`". There is no config key
   (`README.md:39`: *"no config key — tag name is hardcoded"*). It encodes another project's schema
   and another project's loader. Delete.

### 15. `check_test_ac_tags.py` — NEEDS-DECISION (high)

1. **What.** "Verifies every Python test function in staged test files carries a `# covers: XX-NNN`
   tag linking it to an Acceptance Criterion" (`:1-21`). Launches in **warn mode** by default
   (`_DEFAULT_ENFORCEMENT_MODE = "warn"`, `:40`).
2. **`main()`** — yes, `:274` (`main(argv)`); reads paths from argv or
   `CHECK_TEST_AC_TAGS_FILES`.
3. **Invoked by** — nothing executable. Named in `templates/docs/how-to/ac-traceability-store.md:176`,
   `:212`, `:222` (which tells the user to run it by hand) and `templates/agents/test-writer.md:833`.
4. **Ever registered** — **yes, legacy-manifest only.** `e6e86497f` (2026-06-04, *"feat(EPIC-
   ACTraceabilityStore/03): add check_test_ac_tags.py pre-commit hook"*) added
   `check-test-ac-tags` to `templates/commit-guardian/commit_guardian.json`; deleted by `21d341e38`.
   Same day, same wrong file, same fate as #1 and #18.
5. **Tests** — yes, `unit_tests/commit_guardian/test_check_test_ac_tags.py`.
6. **Superseded?** Substantially. `scripts/ac_store/done_proof.py:777-790` reimplements the exact
   three tag positions — its own comment says "*the same three positions `check_test_ac_tags.py`
   accepts*" — and `done_proof` backs the registered `check-done-proof` hook **and** the required CI
   gate (`.github/workflows/ci.yml:228`).
7. **Would it pass?** In warn mode yes (exit 0). Measured with its own `check_file()` over all 644
   tracked test files: **5,725 untagged test functions in 642 of 644 files.** Its enforcement key
   `test_ac_tag_enforcement` is **absent** from `commit_guardian.json`, so the default `warn` holds.

   **Decision needed:** register in warn mode (5,725 warnings per run, discarded on the passing path
   unless `verbose: true`), or accept that `check-done-proof` is the surviving implementation and
   delete this one plus its 4 doc references. Do not register it in error mode — that blocks every
   commit touching any test file.

### 16. `check_test_fixture_bloat.py` — REGISTER (high)

1. **What.** "Scans staged `test_*.py` files for oversized inline data and warns (or blocks) authors
   when fixture convention thresholds are exceeded" (`:1-17`), per ADR-028. Explicitly designed to
   ship `enabled: false` / warn-only.
2. **`main()`** — yes, `:307` (`main(staged_files, config)`); `sys.exit(main())` at `:410-411`.
3. **Invoked by** — nothing.
4. **Ever registered** — never (`git log -S` empty on both manifests).
5. **Tests** — yes, `unit_tests/commit_guardian/test_check_test_fixture_bloat.py`.
6. **Superseded?** No.
7. **Would it pass?** **Yes, unconditionally, today.** Its config key `test_fixture_bloat` is not
   among the 36 top-level keys of `commit_guardian.json`, so `main()` resolves `config = {}`
   (`:327-337`), `enabled` defaults to `False` (`:339`), and every violation path returns 0
   (`:392-394`). Zero blocking risk. Register now; add the `test_fixture_bloat` block with
   `enabled: true` as a separate, deliberate step.

### 17. `check_ticket_test_requirements.py` — NEEDS-DECISION (high)

1. **What.** "Blocks code tickets that lack a populated `## Test Requirements` section. Non-code
   tickets (no coder agent needed) are always allowed through" (`:1-11`). Implements BO-2000e-1 /
   BO-2000e-1-i.
2. **`main()`** — yes, `:138` (`main(ticket_files)`). But its own header calls it a "**Pure
   library**" whose public API is `check_ticket_has_test_requirements(content)` (`:11`), and says it
   "may be registered via create-hook or called from commit_guardian.json" (`:10`) — i.e. it was
   written on the assumption that someone else would wire it.
3. **Invoked by** — nothing. `scripts/ac_store/generate_ticket_from_ac.py:1884` writes its output
   *to satisfy* this module's `_TESTS_ENTRY_RE`, so there is a live producer of the format.
   `check_proof_promise_claim.py:131-138` (**registered**) copies its `_TESTS_BLOCK_RE` verbatim —
   with a comment saying so — for a different purpose.
4. **Ever registered** — never.
5. **Tests** — yes, `unit_tests/prompt_assembly/test_test_requirements_guard.py`.
6. **Superseded?** Only partially: the registered `check-proof-promise-claim` parses the same block
   but answers a different question (promised-vs-claimed proof), not "is the section populated".
7. **Would it pass?** Ran with `</dev/null`: exit 0, silent. **But registering it as-is would be a
   vacuous no-op**, and this is the decisive finding: `main()` ignores `argv` entirely and, when
   `ticket_files is None`, reads paths **from stdin** (`:151-152`). Under `pre-commit`, filenames
   arrive as command-line arguments and stdin is empty — so the hook would check zero files and
   always pass. (This also explains the earlier report of it "hanging past a 45-second timeout":
   it was blocking on stdin, not looping.)

   **Decision needed:** the guard needs `main()` to prefer `sys.argv[1:]` before falling back to
   stdin. Is that fix wanted — i.e. is "no `## Test Requirements` on a coder ticket" still a
   *blocking* offence — given the known-issue that no authoring surface has emitted that block by
   default since v2.0.0 except `generate_ticket_from_ac.py`? Register only after the argv fix, or
   the registration is theatre.

### 18. `check_v2_ac_store_alignment.py` — RECLASSIFY (med-high)

1. **What.** "Verifies every inline AC store reference (`implements`/`amends`/`introduces AC-XX-NNN`)
   in a staged ticket body resolves to an active YAML file in `docs/acceptance-criteria/`"
   (`:1-24`). Blocking (exit 1) when a reference is dangling.
2. **`main()`** — yes, `:346`; supports `--ticket <path>` and `--ac-store`.
3. **Invoked by** — **a real, non-pre-commit caller.** `templates/agents/ac-validator.md:141`
   instructs the agent, in its deterministic step 2c, to run
   `python scripts/commit_guardian/check_v2_ac_store_alignment.py --ticket <ticket_path>`
   and to treat a non-zero exit as a blocker finding; restated at `:395`. The script's own docstring
   names this call site (`:12-13`, "*Accepts `--ticket <path>` for single-file invocation (used by
   ac-validator)*"). The template also handles the script being absent (`:157`).
4. **Ever registered** — **yes, legacy-manifest only**, `1fcd2f7c7` (2026-06-04, PR #52); deleted by
   `21d341e38`. Third of the same-day trio.
5. **Tests** — yes, `unit_tests/commit_guardian/test_check_v2_ac_store_alignment.py`.
6. **Superseded?** Its *input format* is close to dead: the inline
   `implements AC-XX-NNN` prose form appears in only **4 tickets**, all long-finished June 2026 work
   (`tickets/99_done/EPIC-ACTraceabilityStore/done/05,06,07`,
   `tickets/99_done/EPIC-UnifyACPipeline/done/02`). Modern tickets use `ac_traceability` frontmatter
   (ADR-012), which `check-ticket-ac-status-parity` and `ac_coverage_resolver` handle.
7. **Would it pass?** Yes — it exits 0 when no references are found, which is the case for every
   current ticket.

   **RECLASSIFY rather than DELETE** because it has a live agent caller, so removing it silently
   breaks `ac-validator` step 2c. The correct sequence is: decide whether the inline form is retired;
   if yes, remove step 2c from `templates/agents/ac-validator.md` *first*, then delete the script. If
   the caller stays, add the script to `hook_parity.excluded_scripts` so the inventory stops calling
   it an orphan.

---

## 4. Cross-cutting findings

### A. There is one historical de-registration event, and it accounts for exactly 3 of the 18

`21d341e38` — *"feat(build): remove deprecated `templates/commit-guardian/` tree (#134)"*,
2026-06-22 — deleted the legacy manifest's `hooks_manifest`, which contained **7 hook ids the
canonical manifest did not have** and a `post_merge` array the canonical manifest never had:

| legacy-only id | script | today |
|---|---|---|
| `check-ac-coverage` | `check_ac_coverage.py` | **orphan (#1)** |
| `check-test-ac-tags` | `check_test_ac_tags.py` | **orphan (#15)** |
| `check-v2-ac-store-alignment` | `check_v2_ac_store_alignment.py` | **orphan (#18)** |
| `check-ac-limits` | `hooks/check_ac_limits.py` | fine — canonical has it as `check-ac-tree-limits` |
| `transform-doc-frontmatter` | — | re-added to canonical later |
| `transform-description-field` | — | re-added to canonical later |
| `check-ticket-no-branch-move` | `check_ticket_no_branch_move.py` | script no longer exists |
| `post_merge: check-ticket-state-integrity` | `check_ticket_state_integrity.py` | script no longer exists |

The canonical manifest was **byte-for-byte unchanged in hook membership** across that commit — 35
ids before, the same 35 after (verified by extracting
`21d341e38^:templates/scripts/commit_guardian/commit_guardian.json` and
`21d341e38:…` and diffing the id sets). The migration moved the scripts and deleted the
registrations without merging them.

**But the loss started earlier and is worse than "a refactor dropped them".** All three were
registered on **2026-06-04**, into the legacy manifest — *seventeen days after* `build_precommit.py`
was changed (2026-05-18, EPIC-PortableInstallHardening/T03) to read the canonical manifest and use
the legacy path only as a `if not manifest_path.exists()` fallback (the fallback block, later
removed by `21d341e38`, is visible in that commit's diff of `scripts/build_precommit.py:315-318`).
The canonical manifest existed on 2026-06-04. **So these three hooks never ran for a single commit
in their entire lives** — they were authored into a dead registry, and PR #134 merely removed the
corpse. Three separate epics (ACTraceabilityStore/03, ACTraceabilityStore/04, UnifyACPipeline) each
shipped a green, tested, "registered" gate that had never fired.

That is `KI-CG-021`'s shape three times over, eighty days *before* `KI-CG-021` was filed, and the
same root cause the register keeps naming: nobody asked which file the build actually reads.

### B. The other 15 were never registered anywhere — nine of them are monorepo inheritance

`check_complexity`, `check_sql_complexity`, `check_docstrings`, `check_documentation`,
`check_root_files`, `check_folder_density`, `check_debug_scripts`, `check_doc_links`,
`check_doc_coverage`, `check_pytest_style` and `check_sql_dependencies` have been present since
`11dbd26b7` *"Initial commit: extract from bybit-trader monorepo"*, complete with settings blocks.
The repo's first tracked `.pre-commit-config.yaml` (`645122a6b:.pre-commit-config.yaml`) registered
18 hooks and **none of these**. They arrived as configuration without runners and have never had
one. Four of them are still visibly addressed to the other project: `check_pytest_style`'s
`unit_tests/live_trader/` (`:36`), `check_sql_dependencies`' trading-table `KNOWN_TABLES`
(`:16-22`), `check_root_files`' `app_launcher.py`/`database_queries.py` allowlist, and
`check_documentation`'s `sql_functions/` assumptions.

### C. There are **five** surfaces that assert these hooks are live, not the two in the brief

For the nine "settings-block" scripts, a reader has five independent reasons to believe they run:

1. `templates/scripts/commit_guardian/config.py` — typed constants per hook
   (`:102-103` complexity, `:108-109` sql_complexity, `:114-117` docstrings, `:122-124`
   documentation, `:137-139` folder_density, `:144-148` debug_scripts, `:205-209` doc_links,
   `:229-232` doc_coverage).
2. `commit_guardian.json` — a populated settings section per hook (all nine present among the 36
   top-level keys, each with a `_comment` naming the script).
3. **`templates/scripts/commit_guardian/README.md` — a hook-id table row**, stating severity
   ("Blocking"), the hook id, and the config keys: `:31` `check-root-files`, `:32`
   `check-debug-scripts`, `:33` `check-documentation`, `:36` `check-doc-links`, `:37`
   `check-complexity`, `:38` `check-sql-complexity`, `:39` `check-sql-dependencies`, `:40`
   `check-docstrings`, `:42` `check-folder-density`, `:48` `check-pytest-style`. **Eleven of the
   18 carry a README row asserting a hook id that exists in no manifest.**
4. **`templates/scripts/precommit-autofix.json` — autofix routing** for `check-complexity` (`:14`,
   `:24-28`), `check-docstrings` (`:15`, `:31-35`), `check-doc-links` (`:87-91`) and
   `check-sql-complexity` (`:150-154`). Remediation wired to gates that cannot fire — the same
   "fifth registration leg" already noted for `check_ticket_signoff_parity` in
   `docs/known-issues/commit-guardian.md:3047-3050`, now confirmed at four more ids.
5. Prose in `templates/rules/documentation.md:78` ("*enforced by `check_docstrings.py` in the
   pre-commit hooks*"), `templates/skills/doc-enforcer/SKILL.md:207`, and `INTEGRATION.md:76`/`:82`/
   `:88`/`:283`.

Whatever is decided per script, **all five surfaces must move in the same change** or the trap
survives the fix.

### D. Two orphans are broken, and nobody noticed precisely because nothing runs them

- `check_doc_coverage.py` — `NameError: name '_project_root' is not defined` at `:324`, every
  invocation, exit 1 with a traceback.
- `check_docstrings.py` — unhandled `docstring_parser.common.ParseError` on
  `scripts/ac_store/scan_ac_orphans.py`.

Both would have surfaced on day one of registration.

### E. Deleting orphans has collateral

Three helper modules are dead-with-their-hook and should be removed in the same change:
`docstring_validators.py` (imported only by `check_docstrings.py:25`), `doc_validators.py`
(imported only by `check_documentation.py:32`), and — indirectly — nothing else. Two hard
dependencies run *between* orphans and must be untangled before any deletion:
`check_documentation.py:26` hard-imports `check_root_files`, and `check_sql_complexity.py:52`
soft-imports `check_complexity`.

### F. One related KI is now partly stale

`KI-CG-20260831-hook-scripts-never-invoked` (commit-guardian.md:2932) is built around
`check_ticket_signoff_parity.py` being unregistered. **It is registered today** —
`check-ticket-signoff-parity` is in `hooks_manifest.hooks` and the script is not among the 18. The
entry's *remediation* item 1 is therefore done; items 2 (triage the rest) and 3 (close the
enumeration gap) are what this report addresses. Worth a status line on that entry.

---

## 5. Where the brief's framing is wrong

**1. The `check_ac_done_on_merge` lead is backwards, and the new test repeats the error.**
The brief says it "appears to be invoked by `scripts/ac_store/mark_ac_done.py`". The opposite is
true: `check_ac_done_on_merge.py:148-162` shells out to `mark_ac_done.py`, and
`scripts/ac_store/mark_ac_done.py:6` documents itself as "*Called by check_ac_done_on_merge.py
post-merge hook*". Nothing calls `check_ac_done_on_merge.py`. **This matters beyond the label:**
`unit_tests/commit_guardian/test_hook_registration_inventory.py:81` carries the same wrong claim as
an inline comment ("`# invoked by scripts/ac_store/mark_ac_done.py, not pre-commit`"), which reads to
the next triager as "already explained, move on". It is the only genuinely register-now hook in the
set and the baseline comment argues against registering it. Fix the comment.

**2. The `check_outcome` lead is correct, and understated.** It is not merely "imported by other
hooks" — it is imported by `run_hook.py`, the dispatcher through which *every one of the 62
registered hooks* executes (`run_hook.py:37`, used at `:412`, `:449`, `:453`). It is probably the
most frequently executed file in the directory.

**3. The "9 with settings blocks" split is accurate but not the useful cut.** All nine do carry a
block in both `config.py` and `commit_guardian.json` — verified. But the misleading-configuration
count is higher on other axes: **eleven** carry a README hook-id row (the nine plus
`check_sql_dependencies` and `check_pytest_style`), and **four** carry precommit-autofix routing. The
"presence of configuration reads as evidence of registration" problem the KI describes is a
five-surface problem, not a two-surface one.

**4. "Nothing runs them" is right; "nothing calls them" is not.** Two of the 18 have live,
non-pre-commit callers that the disk→manifest question cannot see:
`check_v2_ac_store_alignment.py` is invoked by the `ac-validator` agent
(`templates/agents/ac-validator.md:141`, `:395`), and `check_documentation.py --report-legacy` is
invoked by the `doc-enforcer` skill (`templates/skills/doc-enforcer/SKILL.md:207`). Deleting either
silently breaks an agent workflow. The inventory test is correct that no *hook* runs them; it is not
evidence that they are unreachable.

**5. "Would it even pass today" has a third answer the framing does not anticipate: "it would pass
vacuously."** Four of the 18 cannot fail in this repository because their input set is empty —
`check_pytest_style` (`unit_tests/live_trader/` does not exist), `check_sql_complexity` and
`check_sql_dependencies` (zero tracked `.sql` files), `check_debug_scripts` (`debugging/` untracked).
That is not the same as "safe to register and done": leafcutter is a *package* that deploys these
hooks into consumer projects, so an empty local input set says nothing about consumer impact. It
does, however, cleanly separate the *portable* vacuous hooks (`check_debug_scripts`,
`check_sql_complexity` — fully config-driven) from the *un-portable* ones (`check_pytest_style`,
`check_sql_dependencies` — hardcoded to another project's paths and schema), which is what drives
their opposite verdicts here.

**6. A scope note on the inventory test itself.** `hook_parity.hook_script_patterns` is
`["check_*.py", "run_hook.py", "regenerate_*.py"]` and `excluded_scripts` is `[]`. Because the
pattern is name-based, any future shared helper named `check_*.py` will land in this baseline the
same way `check_outcome.py` did. The cheapest durable fix is to populate `excluded_scripts` (and to
prefer the `_leading_underscore` convention the directory already uses for its ~23 helper modules)
rather than to keep re-litigating each one.
