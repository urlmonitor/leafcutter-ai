---
title: "Contract-shrinking hook reads git output as UTF-8; a failed read is a hook error, not a crash"
status: todo
components:
  - commit_guardian
created: 2026-10-07
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - encoding
  - windows
  - pre-commit
  - contract-shrinking
last_updated: 2026-10-07
files_touched:
  - templates/scripts/commit_guardian/check_contract_shrinking.py
  - templates/scripts/commit_guardian/_authored_change.py
  - templates/scripts/commit_guardian/_operation_record.py
  - unit_tests/commit_guardian/test_contract_shrinking_decodes_utf8.py  # new
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260914-contract-guard-crashes-on-diff-bytes.md  # moved to resolved/
  - docs/known-issues/commit-guardian/resolved/resolved-high-ki-cg-20260914-contract-guard-crashes-on-diff-bytes.md  # new (moved)
  - docs/known-issues/commit-guardian.md
agents:
  status-checker: not_needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Contract-shrinking hook reads git output as UTF-8; a failed read is a hook error, not a crash

## Actor / Goal
In order that a commit is never refused because a hook crashed, we need check-contract-shrinking to
read git's output as UTF-8 on every platform, and to report a failed read as a hook error. Then a
Windows commit whose staged diff holds non-ASCII text gets a verdict, not a traceback.

## Context
- **Observed 2026-10-07.** Committing a large merge into the DK-400 E1 epic branch
  (`epic/abundled-request-that-routing-turns-away-is`) on Windows crashed check-contract-shrinking:

  ```text
  Exception in thread Thread-1 (_readerthread):
  UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 1971686: character maps to <undefined>
    File ".leafcutter/scripts/commit_guardian/check_contract_shrinking.py", line 529, in main
      if not diff.strip():
  AttributeError: 'NoneType' object has no attribute 'strip'
  ```

  The crash exited 1 and blocked the commit, although a crash is not a finding. With
  `PYTHONUTF8=1` the same hook ran and passed. `PYTHONIOENCODING=utf-8` does not help (see the
  known issue below): it governs Python's own standard streams, not how `subprocess` decodes a
  child's pipe.
- **Cause.** `_git_diff` (`templates/scripts/commit_guardian/check_contract_shrinking.py:333-358`)
  runs `git diff --cached` with `capture_output=True, text=True` and no `encoding` (:352-354).
  Python then decodes git's UTF-8 bytes with the locale code page, which is cp1252 on Windows.
  The deployed file `.leafcutter/scripts/commit_guardian/check_contract_shrinking.py` is the build
  output of this template; its line 529 is the same `main()` line.
  - Byte 0x9d is one of the five bytes cp1252 leaves undefined (0x81, 0x8d, 0x8f, 0x90, 0x9d). It
    occurs in UTF-8 `”` (U+201D, `e2 80 9d`); 0x90 occurs in `←` (U+2190, `e2 86 90`). An em-dash
    (`e2 80 94`), `…` (`e2 80 a6`) and `✓` (`e2 9c 93`) decode under cp1252 without an error, as
    mojibake, so a test built on them proves nothing.
  - On Windows, `subprocess` decodes each pipe in a reader thread (`_readerthread`, in the Windows
    `Popen._communicate`). The thread's exception is printed, not raised, and `stdout` comes back
    `None` with `returncode` 0, so `check=True` does not fire. Reproduced 2026-10-07 on Python
    3.14.2: `subprocess.run([sys.executable, "-c", "import sys; sys.stdout.buffer.write('x ” y'.encode('utf-8'))"], capture_output=True, text=True, encoding="cp1252")`
    prints `UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 4` and returns
    `returncode 0`, `stdout None`.
  - On POSIX, `Popen._communicate` decodes in the calling thread (`_translate_newlines`), so the
    same call raises `UnicodeDecodeError` out of `subprocess.run`. `_git_diff`'s handler (:356)
    catches only `OSError`, `TimeoutExpired` and `CalledProcessError`, so that is an uncaught
    traceback too. Linux CI runs a UTF-8 locale and sees neither.
  - `main()` (:519-580) then calls `diff.strip()` (:529) on the `None`.
- **Fixing :352 alone is not enough.** `_get_weakening_diff` (:409-439) asks the shared
  `get_authored_change()` for a second full `git diff --cached`. It runs through `_run_git` in
  `templates/scripts/commit_guardian/_authored_change.py:188-214`, whose call (:204-211) sets
  `text=True` and no encoding. `resolve_git_dir` runs `git rev-parse --git-dir` the same way, in
  `templates/scripts/commit_guardian/_operation_record.py:70-77`; its output is a path.
  - On a merge commit, the observed case, a Windows decode failure there gives `diff_text=None`
    (`_authored_change.py:308`). `_get_weakening_diff` returns it (:439), and `main()` takes the
    could-not-check branch (:534-547): a warning that the authored change set could not be
    derived, then exit 0. The weakening scan is skipped without a crash. That hides the defect
    rather than fixing it.
  - `_authored_change` is shared with check-doc-frontmatter (`check_doc_frontmatter.py`,
    `frontmatter_validators.py`). That hook's merge path gets the same fix.
- **Other calls in the hook file.** `_name_only` (:274-277) and the `MERGE_HEAD` probe in
  `_merge_scoped_paths` (:311-314) set no encoding either. `main()` no longer calls them, but
  `unit_tests/commit_guardian/test_ac_limits_merge_scope.py` drives `_merge_scoped_paths`
  directly. Fix them in the same pass.
- **The test seam cannot reproduce this.** `HOOK_TEST_DIFF` (:373-379) reads the diff from a file
  with `encoding="utf-8"` and skips git, and `_get_weakening_diff` returns early under it
  (:428-429). The new tests must go through real git.
- **Error disposition, not decided here.** `_git_diff`'s existing failure path prints
  `ERROR: git diff --cached failed` and exits 1 (:356-358), so a git failure blocks the commit. The
  known issue argues for GE-120a-1's disposition instead: could-not-check, announce it, exit 0. That
  is what `main()` already does when the authored change set cannot be derived (:534-547). The PR
  picks one and says why (AC-2).
- **Known issues.**
  - `docs/known-issues/commit-guardian/open-high-ki-cg-20260914-contract-guard-crashes-on-diff-bytes.md`
    (KI-CG-20260914, open, high) is this defect. It recorded one occurrence (2026-09-14, byte 0x90,
    a merge of `origin/main`); 2026-10-07 is the second. Its fix direction is
    `encoding="utf-8", errors="replace"`.
  - `docs/known-issues/commit-guardian/resolved/resolved-high-ki-cg-20260929-hook-run-strips-em-dashes-from-deployed-config.md`
    (KI-CG-20260929, resolved 2026-10-07 by GE-120g-4) is an encoding sibling on the write side
    (`json.dumps` escaping em-dashes), not the same defect.
- **Related ticket.** `tickets/00_inbox/TICKET-20261007-GeneratorSubprocessDecodesUtf8.md`: the same
  locale-decoding defect, in the epic generator's child process.
- **Other `text=True` calls without `encoding=` in `templates/scripts/commit_guardian/`.** Found
  2026-10-07 at 6ccbd14ea by an AST scan for calls with `text=True` (or `universal_newlines=True`)
  and no `encoding` keyword: 123 calls in 68 files. A further 27 `text=True` calls in the tree
  already pass `encoding`. Five of the 123 are in scope here (above). The other 118 are below,
  sorted by the literal command each one runs.
  - **Read a whole diff, file content or a commit subject (13 calls, 10 files).** These are the
    most exposed, since any non-ASCII text in the content can carry an undefined byte:
    `_ac_pattern_deletion_guard.py` :100; `check_ac_pattern_refs.py` :329; `check_ac_schema.py`
    :292; `check_adr_coverage.py` :70, :131, :154; `check_infra_docs.py` :103;
    `check_mermaid_parent_link.py` :74; `check_presence_only_assertions.py` :110;
    `doc_validators.py` :145, :378; `hooks/check_agent_spawn_consistency.py` :103;
    `hooks/check_agent_verification_consistency.py` :79.
  - **Command assembled at run time, or a non-git tool (10 calls, 9 files).** Not classified:
    `_work_item_repair_io.py` :182; `check_adr_collision.py` :103; `check_commit_scope.py` :90;
    `check_diff_coverage.py` :372; `check_duplicate_code.py` :482; `check_eval_staleness.py` :70,
    :107; `check_negative_control_liveness.py` :479; `check_package_surface_declaration.py` :110;
    `hooks/check_ac_done_on_merge.py` :150.
  - **Read paths, refs, names or counts (95 calls, 58 files).** These can only fail on a non-ASCII
    path: `_ac_pattern_deletion_guard.py` :65; `_ac_store_index_disk.py` :275;
    `_hook_trigger_tracked_paths.py` :55; `_resolve_root.py` :97; `_staged_ac_yaml_paths.py` :68,
    :97, :113; `check_ac_circular_deps.py` :124; `check_ac_limits.py` :353, :379;
    `check_ac_parent_covered_by.py` :181, :211; `check_ac_pattern_refs.py` :239, :285;
    `check_ac_schema.py` :352, :382, :398, :442; `check_adr_coverage.py` :40;
    `check_agent_diagrams.py` :43, :98; `check_agent_registry.py` :116;
    `check_architecture_scaffolds.py` :49, :65; `check_complexity.py` :110;
    `check_components_integrity.py` :156, :268, :289; `check_debug_scripts.py` :45;
    `check_description_field.py` :153; `check_diagram_naming.py` :48, :65, :161;
    `check_diff_coverage.py` :135, :164, :320; `check_doc_coverage.py` :70, :97;
    `check_doc_frontmatter.py` :98, :368; `check_doc_length.py` :254; `check_doc_links.py` :293;
    `check_doc_types_agents.py` :35, :121; `check_docstrings.py` :38; `check_done_proof.py` :292;
    `check_duplicate_code.py` :115, :145; `check_file_size.py` :194; `check_folder_density.py` :58,
    :129; `check_glossary_coverage.py` :64, :518; `check_identifier_uniqueness.py` :258;
    `check_infra_docs.py` :134; `check_mermaid_complexity.py` :227; `check_mermaid_drift.py` :59,
    :76, :231; `check_mermaid_parent_link.py` :86; `check_paths_integrity.py` :38, :54;
    `check_placeholder_defaults.py` :364, :478; `check_roadmap_schema.py` :38, :53;
    `check_root_files.py` :33; `check_secrets.py` :234; `check_sql_complexity.py` :85;
    `check_surface_components_e2.py` :189; `check_surface_components_e3.py` :182;
    `check_test_fixture_bloat.py` :68; `check_ticket_ac_status_parity.py` :54;
    `check_ticket_signoff_parity.py` :267; `check_v2_ac_store_alignment.py` :225;
    `check_workflow_meta.py` :239; `doc_validators.py` :339, :349, :486;
    `hooks/check_ac_done_on_merge.py` :53; `hooks/check_ac_limits.py` :137;
    `hooks/check_agent_spawn_consistency.py` :79, :114, :203;
    `hooks/check_agent_verification_consistency.py` :46;
    `hooks/check_files_touched_reconciliation.py` :83, :98, :124, :161;
    `install_pre_commit_shims.py` :247; `regenerate_roadmap_mirror.py` :56, :79; `run_hook.py` :92,
    :117, :316.
- **Sizes (measured with check-file-size's `count_lines`, 2026-10-07).**
  `check_contract_shrinking.py` measures 426 against the 400-line limit (625 raw), so it is over and
  every changed line must be paid back. `_authored_change.py` measures 147, `_operation_record.py`
  58.

## Acceptance Criteria
- [ ] AC-1: Every git call the hook makes decodes git's output as UTF-8 with an explicit `errors=` policy. That is `_git_diff` (:352), `_name_only` (:274) and the `MERGE_HEAD` probe (:311) in `check_contract_shrinking.py`, and `_run_git` in `_authored_change.py` (:204) and `_operation_record.py` (:70). On a cp1252 locale without `PYTHONUTF8`, a staged diff that holds non-ASCII UTF-8, and also bytes that are not valid UTF-8, is read in full and gets a verdict. This holds on an ordinary commit and on a merge commit.
- [ ] AC-2: A decode or subprocess failure while reading git output is reported as a hook error: one `[contract-shrinking guard]` message that names the git command and the cause. It is never an `AttributeError` or any other traceback. This covers `stdout` coming back `None` (the Windows shape) and `UnicodeDecodeError` raised from `subprocess.run` (the POSIX shape). The PR states whether the error blocks (exit 1, as `_git_diff` does today) or fails open with `OUTCOME_COULD_NOT_CHECK` (exit 0, GE-120a-1), and why.
- [ ] AC-3: A test feeds the hook, through real git, a staged diff containing non-ASCII UTF-8 under a cp1252 locale. The locale is simulated through the subprocess `encoding` parameter: every `subprocess.run` call that sets `text=True` without an encoding is given `encoding="cp1252"`. The test is red on the current code, on Windows and on Linux.
- [ ] AC-4: The existing tests stay green: `unit_tests/commit_guardian/test_check_contract_shrinking.py`, `test_contract_shrinking.py`, `test_contract_shrinking_ignores_mentions.py`, `test_ge_119_contract_shrinking_rename_aware.py`, `test_ge_122e_1.py` and `test_ac_limits_merge_scope.py`, and `unit_tests/portability/test_ge_120e_1.py`, `test_ge_120e_1_i.py`, `test_ge_120e_2.py`, `test_ge_120e_2_i.py`, `test_ge_120e_3_ii.py`, `test_ge_120e_4.py` and `test_ge_120e_4_i.py`.

## Test Requirements

```yaml
tests:
  - name: test_staged_utf8_diff_is_scanned_under_cp1252_default
    location: unit_tests/commit_guardian/test_contract_shrinking_decodes_utf8.py
    type: integration
    covers: [AC-1, AC-3]
    description: |
      In a temporary git repository, commit a production module and a test file. Then stage a
      production change whose added line holds U+201D (UTF-8 e2 80 9d, the byte observed), an
      added `@unittest.skip(` in the test file after it, and a second text file holding a raw
      0x97 byte (a cp1252 em-dash, not valid UTF-8). Run the hook's real main() from the
      repository root, with subprocess.run wrapped so that a call with text=True and no encoding
      gets encoding="cp1252". Do not set HOOK_TEST_DIFF. Expect exit 1 and the BLOCKED report
      naming the test file: the whole diff was read and scanned past both bytes. Red today:
      AttributeError on Windows (stdout None); UnicodeDecodeError raised from subprocess.run on
      POSIX.
  - name: test_merge_commit_with_utf8_diff_is_scanned
    location: unit_tests/commit_guardian/test_contract_shrinking_decodes_utf8.py
    type: integration
    covers: [AC-1, AC-3]
    description: |
      Same simulation inside a merge (git merge --no-ff --no-commit, so MERGE_HEAD is present).
      The author's own staged change, not the incoming side, holds U+201D, the production change
      and the added skip, so the byte is in both the full staged diff and the merge-scoped diff.
      Expect exit 1 BLOCKED, and no "could not derive the authored (merge-scoped) change set"
      warning. Still red if only _git_diff is fixed: the shared derivation decodes as cp1252 and
      the hook falls through to could-not-check with exit 0.
  - name: test_failed_git_read_is_a_hook_error_not_a_traceback
    location: unit_tests/commit_guardian/test_contract_shrinking_decodes_utf8.py
    type: unit
    covers: [AC-2]
    description: |
      Three cases, each replacing subprocess.run for the git diff call: it returns returncode 0
      with stdout None (the Windows reader-thread shape); it raises UnicodeDecodeError (the POSIX
      shape); it raises OSError. In each, main() raises nothing, the output holds one
      "[contract-shrinking guard]" message naming the git command and the cause, and the output
      holds no "Traceback" and no "AttributeError". The exit code matches the disposition the PR
      chose (AC-2).
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_staged_utf8_diff_is_scanned_under_cp1252_default, test_merge_commit_with_utf8_diff_is_scanned | | |
| AC-2 | test_failed_git_read_is_a_hook_error_not_a_traceback | | |
| AC-3 | test_staged_utf8_diff_is_scanned_under_cp1252_default, test_merge_commit_with_utf8_diff_is_scanned | | |
| AC-4 | (existing tests) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/commit_guardian/test_contract_shrinking_decodes_utf8.py` with the three
  tests above, and confirm each is red on the current code.

### python-coder
- [ ] `check_contract_shrinking.py:274`, `:311` and `:352`: pass `encoding="utf-8"` and an explicit
  `errors=` (the known issue proposes `"replace"`; the scan's patterns are ASCII).
- [ ] `_git_diff` (:356-358) and `main()` (:527-531): report a `UnicodeDecodeError` or a `None`
  stdout as the hook error AC-2 describes, with the disposition the PR chooses.
- [ ] `_authored_change.py:204-211` and `_operation_record.py:70-77`: the same encoding. `_run_git`
  treats a `None` stdout as a failed call, so it becomes a could-not-check result, never
  `diff_text=None`.
- [ ] Pay back every changed line in `check_contract_shrinking.py` under the ratchet. Then run
  `python scripts/build.py`, so the deployed copy under `.leafcutter/scripts/commit_guardian/`
  matches, and stage every tracked output it changes.
- [ ] Resolve KI-CG-20260914: record the 2026-10-07 occurrence, move the file to
  `docs/known-issues/commit-guardian/resolved/` with the `resolved-` prefix
  (`docs/known-issues/README.md:116-117`), and update its row in
  `docs/known-issues/commit-guardian.md`.

### test-runner / pr-reviewer / commit
- [ ] Run the new file and the AC-4 tests on Windows without `PYTHONUTF8`.

## Risk & Safety
- Touches money? No.
- Touches data? No. The hook only reads.
- Behaviour change: on Windows a commit that used to crash now gets a verdict. A real contract
  shrink inside a large merge, hidden until now by the crash or by `PYTHONUTF8=1` runs, can now
  block. check-doc-frontmatter's merge path reads UTF-8 too, through the shared `_authored_change`.
- Reversibility: revert the commit, then rebuild.

## Out of Scope
- The other 118 calls listed in Context. They want their own ticket, starting with the 13 that read
  content.
- Output-side encoding: what a hook prints to a cp1252 console.
- The epic generator's child process (`TICKET-20261007-GeneratorSubprocessDecodesUtf8`).
