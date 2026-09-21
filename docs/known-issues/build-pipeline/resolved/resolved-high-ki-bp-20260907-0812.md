---
title: "KI-BP-20260907-0812 — `generate_product_truth.py` builds index paths with the platform separator, so on Windows the validator can never pass and every commit touching an AC YAML is blocked"
description: "KI-BP-20260907-0812 — `generate_product_truth.py` builds index paths with the platform separator, so on Windows the validator can never pass and every commit touching an AC YAML is blocked"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20260907-0812 — `generate_product_truth.py` builds index paths with the platform separator, so on Windows the validator can never pass and every commit touching an AC YAML is blocked

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** FIXED by `26f35212` — retained for context per the register's "fixed, recorded for context" exception, because the `.as_posix()` call at the construction site is otherwise unexplained and invites a well-meaning revert to `str(...)`.
- **Occurrences:** 1
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `docs/product-truth/scripts/generate_product_truth.py:423` — `paths[flow["id"]] = str(path.relative_to(STORE))` · consumed by `_check_derived_indexes` in `docs/product-truth/scripts/validate_product_truth.py` · surfaced through the `check-product-truth-validate` and `check-product-truth-generate` hooks (`templates/scripts/commit_guardian/commit_guardian.json:1093,1107`)
- **Filed under `build_pipeline` provisionally** — the package has no `product-truth` known-issues component file, and this machinery is deployed by `build_product_truth()` (`scripts/build_phases.py:3548`). Move it if a product-truth file is created.

**Symptom.** On Windows the product-truth validator fails against an unmodified, correct store:

```text
FAIL: [index] by_flow does not match a fresh rebuild — run generate_product_truth.py
1 error(s), 24 warning(s)
```

**Mechanism.** `load_flows()` stores each flow's location as `str(path.relative_to(STORE))`, which
renders with `os.sep`. The committed `index.json` was generated on a POSIX host and holds
`flows/fern-and-fig/checkout-and-pay.flow.json`; a Windows rebuild produces
`flows\fern-and-fig\checkout-and-pay.flow.json`. `_check_derived_indexes` compares stored against
rebuilt and reports drift.

**This is not store drift, and must not be recorded as such.** Verified across the whole store:

```text
by_flow entries:                14
separator-only differences:     14
genuine content differences:     0
```

Every mismatch is the separator alone. The store is correct on its native platform.

**Why the severity is high rather than cosmetic.** Both hooks fire on
`files: (^docs/product-truth/|^docs/acceptance-criteria/.*\.yaml$)`. Since the validator cannot
pass on Windows, a Windows contributor cannot commit **any** acceptance-criteria YAML — not only
product-truth files. AC authoring is blocked wholesale on the platform. The escape is
`--no-verify`, which disables every other gate in the same breath.

The write direction is worse than the read direction. Nothing stops a Windows contributor running
the generator in write mode; `index.json` is then rewritten with backslash paths, which fails for
every POSIX contributor and for CI. The file then flips separator on each platform's turn — a
churn loop where each side's "fix" breaks the other, and neither side is wrong.

**Detection.**

```bash
python - <<'PY'
import json, pathlib, os
STORE = pathlib.Path('docs/product-truth')
idx = json.load(open(STORE/'index.json', encoding='utf-8'))
norm = lambda x: x.replace(os.sep, '/')
for fid, e in idx.get('by_flow', {}).items():
    p = e.get('path','')
    if p != norm(p):
        print('platform-separator path in committed index:', fid, p)
PY
```

A committed index that already contains `os.sep`-flavoured paths means a Windows write has landed.

**Fix direction.** Emit POSIX separators at the single construction site — `path.relative_to(STORE).as_posix()` rather than `str(...)`. Store-relative paths inside a JSON manifest are identifiers, not filesystem paths, and should be platform-independent by construction. Audit the sibling loaders (`load_mocks`, and any other `relative_to` in the two scripts) for the same expression before closing. A regression test should assert that every emitted `path` value contains no backslash, which fails today on Windows and passes trivially on POSIX — so it must be written as a string-content assertion, not as a round-trip through `pathlib`, or it will pass vacuously on the platform that cannot reproduce the bug.

**Pattern:** a check that cannot pass is as useless as one that cannot fail, and pushes contributors toward `--no-verify` — which is the mechanism by which one platform-specific defect disables an entire gate set. **Related:** `KI-CG-20260907-0745` is the other defect found the same day whose practical effect is a blanket tool block on Windows; both are cases of POSIX-shaped assumptions reaching a Windows contributor through generated artifacts.

---
