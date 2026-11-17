---
title: "Decision kernel: the printed decisions-publish command runs as shown"
date: "2026-10-02"
time: "17:30"
type: manual
components: 
  - decision_kernel
summary: "When a decision run stages a record, the publish command it prints can now be pasted and run as is, from any folder."
description: "The staged-record limitation printed a bare 'python -m kernel decisions publish', which failed with 'No module named kernel' outside the runtime checkout. It now prints the kernel's own interpreter (sys.executable) and the new scripts/run_kernel.py launcher, which needs no PYTHONPATH, plus the folder the record is written to: memory.decisions_dir under the kernel checkout (docs/decisions by default), resolved by the same MemoryConfig.decisions_folder helper that decisions publish uses. Paths are quoted only when they contain whitespace, with the PowerShell call operator on Windows. The decision-staging, decision-publishing and decision-lifecycle flows (with their checked io_contracts examples), the decisions mock dataset, the decision-record-staged mockup and the how-to now show the new command and folder. TICKET-20261002-KernelRunnablePublishCommand."
commits: 
  - ef86166e2e745aef556157738f6e44093631ad51
---

## Entry
