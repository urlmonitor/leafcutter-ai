---
title: "The frontmatter-reuse test type-checks clean"
date: "2026-11-16"
time: "12:15"
type: manual
components: 
  - build_pipeline
summary: "The informational mypy job reported two errors on unit_tests/test_bp_900g_8_v_frontmatter_reuse.py after PR #1418 merged. One added line narrows the cache-size bound to an int, so mypy reports nothing on that file and the test checks exactly what it checked before."
description: "test(build), BP-900g-8-vi. In test_reuse_is_in_memory_only_and_bounded, the bound is read with getattr(template_compiler, '_FRONTMATTER_CACHE_SIZE', None), so mypy types it Any | None, and unittest's assertIsInstance does not narrow a type. That produced mypy arg-type on assertGreater(bound, 0) at line 206 and operator on bound + 50 at line 213. An assert isinstance(bound, int) now follows the unchanged assertIsInstance. It repeats a check that has already passed at runtime, so it removes no assertion and changes no test name. The None default stays, so a missing bound still fails the assertIsInstance with its own message. The None was never reachable past that line: template_compiler defines _FRONTMATTER_CACHE_SIZE = 1024. No production code changes. After the change the CI mypy command prints nothing and exits 0, the file's 9 tests pass under AC_ENFORCE_STRICT=1, and ruff is clean."
adrs: []
commits: []
breaking: false
---

## Entry
