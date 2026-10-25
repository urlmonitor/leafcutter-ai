---
title: "TQ-200d live before-score recorded, with five known issues it found: three scorer and harness defects, one test-runner agent fault, and a stale workspace-maker copy"
date: "2026-10-25"
time: "21:30"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "The first live run of the four local-only evals (origin/main 5e5a37380, 2026-10-25): test-runner 1/3, sql-test-writer 1/3, test-designer 1/3, test-writer 0/8 (never launched). Five known issues filed from it. KI-TQ-20261025-eval-harness-system-prompt-exceeds-windows-command-line (medium): the test-writer template is too long for a Windows command line, so every test-writer row fails at launch with WinError 206. KI-TQ-20261025-test-runner-row-fails-on-quoted-checker-message (low): report_names_no_address reads the bare postgres:// in the db_check checker's own message as an address. KI-TQ-20261025-sql-test-writer-eval-rejects-valid-live-outputs (medium): the to-run-later check wants the function name in the free-prose wrong version, and the empty-window check accepts counts only in SQL. KI-TQ-20261025-test-runner-runs-a-test-file-as-a-script (medium): the live test-runner ran a pytest file with plain python and reported PASS; its template offers that command and never names test_command. KI-BO-20261025-workspace-maker-clone-head-stale (medium): two fresh workspaces came up with HEAD on an older main and the newer tree staged, most likely made by the stale in-repo copy of the maker that predates the 1d316e0a0 fix."
description: "Docs only. Four new files under docs/known-issues/testing-quality/ (low index bucket; three graded medium) with four register rows in testing-quality.md (open recounted from the directory: 38 to 42), and one new file under docs/known-issues/build-orchestration/ (low bucket, graded medium) with one register row in build-orchestration.md (open recounted: 77 to 78). Sites at origin/main 5e5a37380: run_agent_eval.py:234-242/:259-300/:684-733, produced_tests_mode.py:41-43/:97-103, produced_tests_transcript.py:98-116, agent_eval_config.json:167; db_check/_address.py:54-58, db_check/checker.py:268-279/:346, produced_tests_reports.py:31-33/:37-38/:68-71/:74-87, test-runner.jsonl:1/:3; sql_test_writer_eval/evidence_kinds.py:28/:42-46/:67-71/:74-89, sql-test-writer.jsonl:1, sql-test-writer.md:219-224/:330; test-runner.md:27-33/:104-105, produced_tests_commands.py:259-272; worktree_ensure_steps.py:200-242, worktree.py:126/:140-154, worktree_git.py:46, plus the gitignored in-repo install leafcutter-ai/.leafcutter/scripts/worktree.py:86/:107/:142. Evidence: live before-score 2026-10-25 on Windows 11 (test-runner smoke 20:57:07Z and full 20:58:19Z, sql-test-writer 21:05:42Z, test-designer 21:10:13Z, test-writer 21:10:20Z), the runs' session transcripts, and the scratch workspace's reflogs. The results JSON files, with their trigger_shas, stay local in the session scratchpad and are not committed. Remediation directions recorded, not applied."
commits:
breaking: false
---

## Entry

The first live before-score of the four test agents whose evals can only run locally was taken
on 2026-10-25 at `origin/main` `5e5a37380`. "Live" means the real agent was run on each example,
not the recorded answers. The results:

| Agent | Score | What failed |
|---|---|---|
| test-runner | 1/3 | The configured-database example failed because of a scoring fault: the agent correctly repeated the database checker's message, and the eval read it as naming a database address. The second failure is the agent's: asked to run one test file, it ran the file as a plain script, so no test ran, and still reported a pass. |
| sql-test-writer | 1/3 | Both database examples failed because of scoring faults: the agent's output was correct each time. The trap example passed. |
| test-designer | 1/3 | The bug-fix and gate examples failed because the agent never names the wrong versions "revert the fix" and "the gate always allows". Its instructions do not ask for them yet. That instruction is TQ-500f-2-ii, still to be built, so these failures are expected until it is. The trap example passed. |
| test-writer | 0/8 | No example started: the test-writer's instructions are too long for a Windows command line. |

The result files, with the fingerprints of the files each run depended on, are kept locally and
are not part of this change.

Five problems found along the way are now recorded as known issues. Three are faults in how the
evals launch or score an agent: the Windows command-line limit, the eval reading the checker's
message as an address, and two sql-test-writer checks that accept only one way of writing a
correct answer. One is a fault in the test-runner agent itself: its instructions suggest running
a single test file as a plain script and never point it at the project's configured test command.
The last is about workspaces: two new workspaces came up with their history on an older main and
the newer files already staged. The likely cause is an old copy of the workspace maker that is
still installed inside the repository and predates the fix for exactly this. Each entry names the
affected lines and the suggested fix; none of the fixes is applied yet.
