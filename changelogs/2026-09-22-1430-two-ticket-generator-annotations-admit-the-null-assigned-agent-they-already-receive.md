---
title: "Two ticket-generator annotations admit the null assigned_agent they already receive"
date: "2026-09-22"
time: "14:30"
type: manual
components: 
  - ac_store
summary: "A guard landed on main making generate_ticket_from_ac refuse an AC whose assigned_agent is null, and 355 store records carry exactly that, so None is a common runtime value on this path. Two signatures in the CLI layer still declared str. They now declare str | None. Annotation-only: CLI stdout and exit codes are byte-identical before and after."
description: "In scripts/ac_store/_gtfa_cli.py, _build_agents_map_for_write_path(assigned_agent) and the second member of _ac_inputs return tuple are widened from str to str | None. _ac_inputs is where the None originates: ac.get(assigned_agent, python-coder) defaults only an ABSENT key, so an AC carrying the key with an explicit null yields None, which both the preview and the write path forward to _build_agents_map for it to refuse (TKT-600b-5). Both modules carry from __future__ import annotations, so this is free at runtime. Two further signatures were examined and deliberately left as str, because their str is true rather than a lie: _legacy_agents_map and _collect_needed_agents each have exactly one caller, both inside _build_agents_map strictly after its _require_work_agent guard has already raised on None, and _collect_needed_agents adds the value into a set[str] that a None would poison with a literal null phase. _build_agents_map itself does receive None and its str is a genuine misstatement, but widening it makes mypy reject its own post-guard handoff to _legacy_agents_map: _require_work_agent returns None so it narrows nothing, and _gtfa_agents_map reaches it through the _sib importlib seam whose result is Any. Expressing that guarantee needs the guard to RETURN the narrowed value and the caller to bind a new name, which is a signature change rather than an annotation change, so it is documented in place and left for a follow-up. Verification: mypy --ignore-missing-imports --explicit-package-bases --no-error-summary reports 0 errors before and after, with and without --warn-unreachable; generate_ticket_from_ac.py --ac ACD-1100d --dry-run still refuses by name at exit 1 and --ac BO-2200c-5 --dry-run still generates at exit 0, both byte-identical to the pre-change output; ruff check clean. Measured content lengths stay well under the 400-line cap at 314, 237 and 196 lines."
breaking: false
---

## Entry
