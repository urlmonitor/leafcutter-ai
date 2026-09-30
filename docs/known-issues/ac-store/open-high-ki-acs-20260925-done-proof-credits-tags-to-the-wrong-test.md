---
title: "KI-ACS-20260925-done-proof-credits-tags-to-the-wrong-test — a covers tag on an async test or above a decorator is attributed to the previous sync test"
description: "high — _TEST_DEF_RE has no async and the attribution walk stops at the decorator, so the oracle runs the wrong test for the AC; a passing neighbour can prove an AC whose own test fails."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/ac-store/open-high-ki-acs-008.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-006.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-ACS-20260925-done-proof-credits-tags-to-the-wrong-test — a covers tag on an async test or above a decorator is attributed to the previous sync test

- **Severity:** high. The oracle proves the AC with a different test than the one the author tagged.
- **Status:** open — no AC. Reproduced 2026-09-25 by a scratch fixture (sub-agent probe); regex re-read by the main session.
- **Where:** `scripts/ac_store/done_proof.py:214` (`_TEST_DEF_RE = re.compile(r"^\s*def\s+(test_\w+)")`) and the attribution walk at `:770-821`, `:866-871`.

## Symptom

```python
def test_a(): assert True

# covers: XX-100
@pytest.mark.slow
async def test_b(): assert False
```

The tag for `XX-100` is credited to `test_a`; the oracle runs `test_a`, which passes.

## Mechanism

`_TEST_DEF_RE` does not match `async def`, and a decorator line between the tag and the `def` breaks the "directly
above" attribution, so the walk falls back to the enclosing/previous matched test.

## Related

KI-ACS-008 D-1 (L37-43) reported the async half; it is still present. This is one of six independent `# covers:`
readers (`test_enforcement.py:57`, `check_done_proof.py:296-303`, `done_proof.py`, `check_test_ac_tags.py:46`,
`check_ac_coverage.py:41`, the `grep` in `ac-fulfillment-gate.md:252`) that disagree on where a tag is valid — see
KI-CG-006 and KI-CG-20260908-covers-tag-must-be-inside-a-test-function.

## Fix direction

One AST-based `ac_proof.parse_tags(file) -> [(ac_id, nodeid_prefix)]` covering `AsyncFunctionDef`, decorators and
multiple ids per tag; every reader imports it. Cluster 1 of the 2026-09-25 duplication analysis.
