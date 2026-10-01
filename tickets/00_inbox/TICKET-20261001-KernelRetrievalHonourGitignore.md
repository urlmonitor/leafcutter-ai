---
title: "Kernel: repository retrieval reads only files git does not ignore"
status: todo
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - retrieval
last_updated: 2026-10-01
agents:
  python-coder: needed
  commit: needed
---

# Kernel: repository retrieval reads only files git does not ignore

## Actor / Goal
In order to give a live run the same corpus on every operating system and keep build outputs, run folders and local secrets out of evidence, we need repository retrieval to read only the files git does not ignore when the read-root is inside a git checkout.

## Context
- **What the cross-platform investigation found** (PR #977): production `repo_text` walks ignored files.
  - `build.py` installs `scripts/commit_guardian/`, `scripts/doc_compliance/` and `scripts/feedback/` as copies on Windows (no symlink rights) and as symlinks on Linux, which `os.walk` never enters.
  - As a result, `repo.patterns` scans 731 files on Windows and 579 on Linux, and the ranking statistics (IDF, length normalisation, source caps) differ by OS.
- **What the benchmark already does:** its harness reads `git ls-files --cached --others --exclude-standard` (`tests/kernel/retrieval/benchmark_support.py`). This ticket brings production in line.
- **Decision:** the user chose "honour .gitignore" over deny globs for the three shim folders, and over leaving it as it is (2026-10-01).

## Scope (no acceptance criteria by user decision)
- **Git checkout:** when a read-root is inside a git checkout, list candidate files from git (tracked plus untracked-not-ignored), then apply the existing read-root, deny-glob, traversal and size checks unchanged.
- **Reporting:** skipped files are reported as `git_ignored` in the retrieval cuts, never dropped silently.
- **Fallback:** a read-root outside any git checkout, or a missing `git` executable, keeps today's walk, and the run records the fallback as a limitation.
- **Explicit locators:** an explicit locator that names an ignored file is refused with a clear reason. It is not read.
- **Tests:**
  - ignored copies change no score;
  - the same tree gives the same pool on a simulated Windows copy layout and a Linux symlink layout;
  - the non-git fallback.

## Out of Scope
- Changing deny globs or source definitions in `config/kernel_config.default.json`.
- Re-recording the retrieval benchmark: its harness already reads the git file list.

## Comments
