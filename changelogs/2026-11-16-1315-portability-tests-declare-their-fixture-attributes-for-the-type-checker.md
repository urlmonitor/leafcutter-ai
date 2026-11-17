---
title: "Portability tests declare their fixture attributes and narrow their optional values for the type checker"
date: "2026-11-16"
time: "13:15"
type: manual
components: 
  - testing_quality
summary: "Ten files under unit_tests/portability/ now type-check cleanly: test classes declare the attributes their setUpClass assigns, optional values are narrowed with isinstance before use, and generator fixtures are annotated as iterators. The slice goes from 168 mypy errors to 80. No test, assertion or marker changed."
description: "Test-only typing change, part of the batched clean-up before mypy becomes a blocking ratchet. test_ge_120c_1.py and test_ge_120e_1_i.py declare the class attributes setUpClass assigns (fixture, deployed_ok, _tmp, copy_a, copy_b, harness). test_ge_120e_3_ii.py reads its two module-level fixture repositories through _authored_fault_repo() and _carried_in_only_repo(), which narrow Path | None with an isinstance assertion naming the setup error. _bp1500g2_harness.py and test_tq100a_2.py assert the module spec and its loader with isinstance before module_from_spec and exec_module. test_uxp_700c_3_i.py annotates its two flow records as dict[str, object] and narrows the parsed verdict line to str after its existing assertIsNotNone. The four test_bp_1500d_* yield fixtures are annotated Iterator[...] instead of the yielded type, and test_bp_1500d_1.py annotates its empty build record. No new type: ignore, cast or Any. Left unchanged: test_ge_120e_1.py (62 errors) and test_ge_120e_2.py (17 errors), both already over the 400-line file-size limit, where declaring the attributes would need twice as many lines of genuinely dead code removed; and _inf_1100d_1_settings_harness.py (1 error), which mypy only reports on a host where the pypa build package is installed and shadows scripts/build.py."
adrs: []
commits: []
breaking: false
---

## Entry
