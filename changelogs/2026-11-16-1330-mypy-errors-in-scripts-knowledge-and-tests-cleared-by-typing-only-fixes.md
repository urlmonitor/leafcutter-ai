---
title: "Mypy errors in scripts/, knowledge/ and tests/ cleared by typing-only fixes"
date: "2026-11-16"
time: "13:30"
type: manual
components: 
  - testing_quality
summary: "Clears 60 of the 75 mypy errors in the tracked scripts/, knowledge/ and tests/ Python files (scripts/evals/sets/ excluded) under CI's flags, with annotations, declared attributes and narrowing that the code already guaranteed. No new type-ignore, no cast to Any, no change to what the code does. The 15 left are listed with the reason each was not fixed."
description: "chore(types), mypy ratchet batch A. Measured with python -m mypy --ignore-missing-imports --explicit-package-bases over every tracked .py under scripts/, knowledge/ and tests/ except scripts/evals/sets/: 75 errors (scripts 43, knowledge 29, tests 3) before, 15 (scripts 3, knowledge 12, tests 0) after. Kinds of fix: local and attribute annotations (changelog_entry candidate, mock_data/mockup/synthetic_demo dicts, _cs_edits listed, _hold_exempt runs, _km_400b_5 overhead, completion_routing_cli reply); variables declared with the type a later assignment needs (_hold_comment and post_merge_reeval paging path/query; roadmap_query's second status_counts annotation dropped); bare class-level declarations that create no attribute, so getattr defaults behave as before (BackendUnavailable cause_class, time_limit_seconds and details; Neo4jBackend _write_settings); a TypeGuard on _write_policy._keys_within; a bound TypeVar for _cs_asserts._by_position, which makes three of that file's existing type-ignores unnecessary, so they are removed; an EmbeddingWriter protocol in knowledge/ports.py for embed_snapshot's writer; harvest_learnings names HarvestResult for the checker through a TYPE_CHECKING import; _hold_publish._status_text admits the int | None it already handled; agent_launch's per-base error class is memoised in a dict, because the checker reads a class object as not Hashable for functools.cache; _cs_runs names the stdout=PIPE stream with a precise cast to IO[bytes]; narrowing whose condition the code already guaranteed (check_fixed_scratch_paths, sql_resolve, covers_tag_identity, completion_routing_cli branch order, _hold_comment); a renamed local in scan_ac_orphans. In tests/kernel/memory/test_publish_cli.py a missing index now fails the two affected tests with a message instead of a TypeError. Left on purpose, each needing a runtime change or an assert this batch does not make: embedding_jobs.py (9, provider: EmbeddingProvider | None is dereferenced unconditionally, so a None provider always raises AttributeError); pytest_ac_enforcement.py:244 (sets report.outcome to 'xfailed', which is not one of pytest's three outcomes); neo4j_writes.py:167/220/256 and wrong_version_runner.py:274 (non-None only by call order); test_enforcement.py:229 (inspect.getsource on an object-typed value; narrowing would change results for objects inspect.unwrap resolves)."
adrs: []
commits: []
breaking: false
---

## Entry
