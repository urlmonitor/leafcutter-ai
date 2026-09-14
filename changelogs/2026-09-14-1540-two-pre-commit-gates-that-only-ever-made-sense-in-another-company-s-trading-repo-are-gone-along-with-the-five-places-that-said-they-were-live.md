---
title: "Two pre-commit gates that only ever made sense in another company's trading repo are gone, along with the five places that said they were live"
date: "2026-09-14"
time: "15:40"
type: manual
components: 
  - commit_guardian
summary: "check_pytest_style.py and check_sql_dependencies.py arrived with the initial bybit-trader monorepo extract, were never registered in any manifest, and cannot match a file outside that repository — one hardcodes unit_tests/live_trader/, the other a set of trading tables. They are the first two scripts retired by the registration inventory added in #787, and the ratchet drops 18 to 16."
description: "check_pytest_style rejected top-level pytest-style test functions because the originating repo ran `unittest discover`, which silently skips them; this repo runs pytest, so the failure mode it guards against cannot occur, and its _TARGET_PREFIX of unit_tests/live_trader/ matches nothing here. check_sql_dependencies enforced a Dependencies: header for a sql_functions/ topological loader that does not exist here, against a hardcoded KNOWN_TABLES set of candles, pnl_trades, positions, orders and similar, with no config key to override. Neither is imported by any module and neither has tests. The deletion removes every surface that asserted they ran: both scripts; their config/package_boundary.json 'portable' declarations; their autofix routing in precommit-autofix.json, which pointed remediation at hook ids present in no manifest; their README rows stating severity 'Blocking'; the line in docs/agents/sql/sql-view-creator.md telling the agent its metadata header was enforced by check-sql-dependencies, which was never true; and the routing-table row. The README porting note's hardcoded-path example was repointed at check_root_files.py, which is the remaining real instance of that problem. Fixing the frontmatter that the doc-frontmatter gate then flagged removed three more dead sql_functions/ paths from the same trader era."
commits: 
  - 6d4a230ac
breaking: false
---

## Entry
