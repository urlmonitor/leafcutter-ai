---
title: "KI-ACS-008 — The oracle's tag-to-test layer cannot see an async test or a parametrised one"
description: "KI-ACS-008 — The oracle's tag-to-test layer cannot see an async test or a parametrised one"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-008 — The oracle's tag-to-test layer cannot see an async test or a parametrised one

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `scripts/ac_store/done_proof.py` — `_TEST_DEF_RE` (line 95, consumed by
  `_scan_single_test_file`); `_find_nodeid_for_test` (consumed by `_classify_outcomes`)

KI-ACS-006 collects defects in the oracle's **composite resolution**. These two sit one
layer lower, in the step that decides which test a `# covers:` tag belongs to and which
pytest result belongs to that test. Both fail closed, so both present as the same
indistinguishable verdict a genuinely untested AC produces — which is precisely why they
survive: the operator reads "no linked test found" and goes looking for a missing test
that is in fact sitting right under the tag.

**D-1 — `async def` is not a test definition.** `_TEST_DEF_RE` is
`r"^\s*def\s+(test_\w+)"`. There is no `async` alternative, so an `async def test_*` line
never updates `current_function` in `_scan_single_test_file`. Every tag inside that
function is either dropped (nothing seen yet → `current_function is None`) or, worse,
attributed to whatever **sync** test happened to appear earlier in the file. An AC whose
tests are all async is unmarkable through the gate; an AC in a mixed file gets its proof
silently reassigned to an unrelated function.

**Evidence.** A consumer install (DIAGraph) has **23** ACs whose every covers-tagged test
is `async def`. Four of them are `DTW-104` — `DTW-104a-3-i`, `DTW-104d-1`, `DTW-104d-3`,
`DTW-104d-3-i` — and the rest are the `N4J-100*` Neo4j integration set, the `CQ-100b-2*`
lifespan set, and `IDP-100d-4`. This is not a corner: any repo testing an async API
surface (FastAPI, an async driver) writes async tests by default, so the gate is
structurally unusable for the whole layer.

**D-2 — a parametrised test never resolves.** `_find_nodeid_for_test` matches with
`nodeid.endswith(f"::{func_name}")`. `_PYTEST_RESULT_RE` correctly *captures* the
parametrised form — its pattern includes `(?:\[.*?\])?` — so the results dict holds
`…::test_x[case]`, which does not end with `::test_x`. Both the basename-scoped pass and
the suffix-only fallback miss, `_find_nodeid_for_test` returns `None`, and
`_classify_outcomes` books the test as non-passing with the reason `linked test not run`.
A green parametrised test therefore reads as evidence the test never executed.

**Evidence.** Live in DIAGraph: `MSN-102` is covered only by
`tests/test_materials_graphdb_502.py::test_neo4j_error_returns_502`, decorated
`@pytest.mark.parametrize("path", MATERIAL_ROUTES)`. Zero occurrences in this repo today —
which is why it has never fired here, not evidence that it is rare.

**Why it matters.** Both defects push in the **false-negative** direction: they report
covered ACs as uncovered. That is the safer direction of the two, but it is the direction
that makes the gate get switched off — an operator who cannot mark a correctly-tested AC
done reaches for `SKIP=` or `--no-verify`, and from then on the gate protects nothing.
D-1's misattribution path in a mixed sync/async file is additionally a false **positive**:
AC-A's tag can be proven by AC-B's sync test.

**Fix direction.** D-1 is a one-token regex change — `r"^\s*(?:async\s+)?def\s+(test_\w+)"`
— plus a test with an async-only fixture file. D-2 wants the match to compare the nodeid's
function segment with the parameter suffix stripped (`nodeid.rsplit("::", 1)[-1].split("[", 1)[0]
== func_name`) rather than a raw `endswith`, and should classify a parametrised test as
passing only when **every** matching nodeid passed — one green case out of five is not
proof. Note `_find_nodeid_for_test` returns a single nodeid today, so D-2's fix changes
its signature; do it as one AC with the caller.

**Related:** KI-ACS-006 (composite-resolution defects in the same oracle); KI-CG-006 (the
pre-commit gate disagrees with this oracle in both directions).

**Pattern:** `docs/reference/false-green-mechanisms.md` — the inverse case: a gate whose
false refusals train the operator to bypass it.

---
