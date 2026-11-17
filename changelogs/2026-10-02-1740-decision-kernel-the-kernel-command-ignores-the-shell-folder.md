---
title: "Decision kernel: the kernel command runs the intended kernel from any folder"
date: "2026-10-02"
time: "17:40"
type: manual
components: 
  - decision_kernel
summary: "Resuming a decision run from a shell sitting in another checkout no longer fails with 'run not found'."
description: "python -m kernel puts the current directory first on sys.path, so a shell in another checkout of this repository imported that checkout's kernel package and its empty run store, and resume exited 4 run_not_found. The installed /leafcutter skill now runs 'python -P -m kernel' (safe path), so PYTHONPATH wins; the how-to says why. LEAFCUTTER_KERNEL_RUN_ROOT can also pin the run store explicitly. A test reproduces the shadowing with a dummy kernel package in the cwd. Re-run install-skill to pick up the new command. 2 commits (TICKET-20261002-KernelRunStoreIndependentOfCwd)."
commits: 
  - 54ff236e2f88ca208f610a677954de923817c1a5
---

## Entry
