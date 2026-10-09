---
title: "KI-BP-20261007 — RETRACTED: \"check-product-truth-validate fails closed on an undeclared aiosqlite dependency\" — tested and disproved; aiosqlite is supplied transitively by langgraph-checkpoint-sqlite and the real cause was a stale local .venv"
description: "RETRACTED the same day it was filed. There is no dependency-declaration defect. aiosqlite arrives transitively via langgraph-checkpoint-sqlite==3.1.1, declared at requirements-dev.txt:52; the gate passes in any environment provisioned from that file."
type: reference
category: reference
status: active
created: '2026-10-07'
last_updated: '2026-10-07'
components:
  - build_pipeline
  - ux_prototyping
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20261007 — RETRACTED: "check-product-truth-validate fails closed on an undeclared aiosqlite dependency" — tested and disproved

> Filed 2026-10-07 (PR #1040), retracted the same day on the first attempt to act on it.
> Index: [build-pipeline.md](../../build-pipeline.md).
> Retained rather than deleted because the way it was got wrong is reusable; the
> register's precedent for this is `KI-CG-20260826-1334`.

- **Severity:** none. The claimed defect does not exist.
- **Status:** RETRACTED 2026-10-07. The original entry asserted that `aiosqlite` "appears in **no** requirements file" and concluded that "a developer who provisions their environment exactly as documented still cannot run this gate". Both statements are false.

**What was actually true.** `aiosqlite` is supplied **transitively** by
`langgraph-checkpoint-sqlite==3.1.1`, declared at `requirements-dev.txt:52` alongside
`langgraph==1.2.12`. Installing the documented dev requirements installs it:

```
pip install -r requirements-dev.txt
python -c "import aiosqlite; print(aiosqlite.__version__)"   ->   0.22.1
```

With that in place the gate reaches a real verdict rather than an import failure:

```
python docs/product-truth/scripts/validate_product_truth.py --quiet
  -> exit 0, 0 FAIL lines, {"outcome": "checked-and-sound", "examined": 27, ...}
```

So the entry's two halves collapse into one cause, and it is the one the entry had
already identified correctly for `pydantic` and then failed to generalise: **the local
`.venv` was stale.** It predated the `langgraph*` pins exactly as it predated the
`pydantic==2.13.5` pin. Reinstalling `requirements-dev.txt` fixes both. There is no
package defect, no missing declaration, and nothing for build-pipeline to change.

**The evidence that should have stopped this being filed.** CI runs the *identical*
command — `python docs/product-truth/scripts/validate_product_truth.py --quiet`,
preceded only by `pip install -r requirements-dev.txt` (`.github/workflows/ci.yml`,
job "Product truth valid (offline)") — and it was **passing on all three PRs open at
the time of filing**, including the PR that carried the entry. A gate that fails in
every documented environment cannot be green in CI. That contradiction was visible on
the PR page and was not reconciled before filing.

**The method error, which is the reusable part.** The claim "declared nowhere" rested
on `grep aiosqlite requirements-dev.txt` returning no match. A grep for a package
name finds only **direct** declarations; it cannot see a dependency supplied through
another package, and most dependencies in a lockfile-less requirements file are of
that kind. The correct question is not "is this string present" but "does a documented
install produce this module", and only installing answers it.

That is the same shape as the defects this register is mostly about: a check that
could not see the thing it was looking for, reporting absence as a finding. The entry
was filed in the same session as, and immediately after, a correction to
`KI-CG-20260914` for exactly that failure mode.

**What remains true and is not retracted.** Two observations from the original entry
survive, neither amounting to a package defect:

- The gate reports a single import failure as ~244 contract errors, nearly all
  `unknown contract:` lines that are downstream of one missing module. A run that
  cannot import its dependencies should say so distinctly rather than as hundreds of
  content findings — the `GE-120a` / `GE-126b` shape. If that is worth pursuing it
  should be filed on its own merits, against the component that owns the validator.
- `grep "No module named"` before reading any `FAIL:` line remains the right first
  move when this gate reports a wall of errors.

**Consequence for the record.** Four commits on 2026-10-07 were landed with
`SKIP=check-product-truth-validate`, and two merged PR bodies (#1037, #1038) justify
that skip by citing this entry's since-disproved claim. The skips were unnecessary:
provisioning the venv would have let the gate run. No commit content is affected — the
gate passes on the merged tree.

**Pattern:** concluding "undeclared" from a grep over a requirements file, when the
dependency was transitive — and filing it despite CI, running the same command in a
clean environment, being green the whole time.

---
