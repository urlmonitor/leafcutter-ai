---
title: "KI-BP-021 — The closure guard's reference lens misses four import idioms, each yielding an empty closure the build reports as clean"
description: "KI-BP-021 — The closure guard's reference lens misses four import idioms, each yielding an empty closure the build reports as clean"
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

# KI-BP-021 — The closure guard's reference lens misses four import idioms, each yielding an empty closure the build reports as clean

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** **RESOLVED 2026-08-31.** All four `sys.path` idioms plus the three further
  shapes below are now resolved by the lens, covered by
  `unit_tests/test_bp_closure_guard_correctness.py` (tagged `BP-900g-8`, whose criterion
  these violate). Originally found during the BP-900g-8 build (PR #578); disclosed by the
  operator rather than by any gate, and deliberately not fixed in that PR to keep the diff
  reviewable.
- **Occurrences:** 1 (latent — **no live instance in the repo**, see Reproduction)
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/build_referential_integrity.py:691-708` `_is_syspath_mutation_call`,
  feeding `_extract_syspath_directories` (`:729-782`) and thence
  `compute_intra_package_closure` (`:875`)

**Symptom.** `_is_syspath_mutation_call` returns True only for `func.attr in ("insert",
"append")` reached through a bare `sys` name. A script that instead writes

```python
sys.path.extend([str(_sibling_dir)])     # or
sys.path[:0] = [str(_sibling_dir)]       # slice assignment — not an ast.Call at all
```

produces **no** candidate directory. Every subsequent plain `import sibling_module` then
resolves against zero candidates and is dropped from the closure.

**Why it matters more than the narrow trigger suggests.** The guard exists to make a missing
deploy entry fail the build. Its failure mode is not a crash — it is a script whose derived
closure is *empty*, which is indistinguishable from a script that genuinely has no
intra-package dependencies. The build then reports that script clean. This is the same
silent-empty shape the guard was written to eliminate, reintroduced one level down in the
guard itself.

Worse, the two forms differ in how far they get. `extend` at least reaches
`_is_syspath_mutation_call` and is rejected there, so it is a candidate for the one-line
widening. A slice assignment is an `ast.Assign` with an `ast.Subscript` target — it never
becomes an `ast.Call`, so the `ast.walk` loop in `_extract_syspath_directories:761-762`
skips it before any predicate runs. Widening the tuple does **not** cover it.

**The disclosure guarantee does not hold here.** `_extract_syspath_directories` logs a
WARNING naming file and line whenever a pushed path *fails to reduce statically* — the
module's docstring at `:752-757` states that "no path through this module produces an
unresolved intra-package reference with zero log output." That promise is true for a
mutation the lens **recognises** and cannot evaluate. It is false for a mutation the lens
does not recognise at all: `continue` at `:762` fires before any logging, so an `extend`
or a slice assignment is dropped in complete silence, at every log level. The docstring
should be corrected in the same change, or it will be read as coverage this code does not
have.

**Reproduction / current exposure.** Verified 2026-08-26 against the BP-900g-8 branch:

```bash
grep -rn "sys\.path\.extend\|sys\.path\[" scripts/ templates/
```

returns two hits, both **comments** mentioning `sys.path[0]`
(`scripts/ac_store/audit_authoring_components.py:51`,
`scripts/ac_store/validate_ac_schema.py:43`) and no executable instance of either form. So
nothing is mis-derived today; the entry records a gap that opens the moment someone writes
one of the two idioms, which no gate or reviewer would flag as unusual.

**Fix direction.** Widen the predicate to `("insert", "append", "extend")` and handle the
list-valued argument `extend` takes — its single positional is a *sequence* of paths, not one
path, so `_syspath_pushed_path_node` (`:711-726`, which returns `args[0]` for the one-arg
form) would hand `_eval_static_path` an `ast.List` and get None back, i.e. a warning rather
than a resolution. Both sides need the change; widening the tuple alone converts a silent
drop into a spurious warning. For the slice-assignment form, add a separate `ast.Assign`
branch. Then add the case the current tests lack: a fixture script that pushes via each
unsupported form and imports through it, asserting the dependency **appears** in the derived
closure — a negative fixture, since a test that only checks `insert`/`append` cannot fail
when the other forms are dropped.

**Three further idioms the lens does not see** — found by an independent adversarial review
round on 2026-08-26, after the entry above was first written. All three land in the same
place as the `sys.path` gap (empty closure, script reported clean) and all three are latent:

| idiom | why it is invisible | log output | live instances |
|---|---|---|---|
| `importlib.import_module("sibling")` / `__import__("sibling")` | `_extract_static_import_candidates` recognises only `ast.Import`/`ast.ImportFrom`; `_is_spec_from_file_location_call` matches only `spec_from_file_location` | **none** | 0 — grep of `scripts/` and `templates/` returns nothing |
| `from . import <subpackage>` | `:841-849` adds only `base/"{name}.py"` as a candidate, never `base/name/"__init__.py"`, and a plain import that resolves to nothing is treated as external by design | **none** | 0 — no `from . import` anywhere in either tree |
| `sibling: Path = Path(__file__).parent / "x.py"` | `_build_local_assignments` (`:500-539`) captures `ast.Assign` targets only, not `ast.AnnAssign` | WARNING (the "unresolvable" path) | 0 |

The annotated-assignment case is the least severe of the three precisely because it *is*
logged. The other two are silent, which makes them the same defect as the `sys.path` gap
rather than a milder relative of it — and in a codebase that annotates heavily, the
`AnnAssign` gap is the one most likely to appear first.

**Do not trust `git log` on this one.** The commit that introduced the lens, `4627c634`
("close the sys.path-insert blind spot in the closure guard"), describes the capability in
general terms that the code does not have — it reads as though `sys.path` mutation is now
handled, rather than two of its four idioms. That over-claim was caught after the commit
landed and is left in history rather than rewritten; this entry is the correction. It is a
live instance of the repo's own "commit messages must match the diff" rule
(`CLAUDE.md`, sourced to EPIC-PhantomDoneFilesTouched KI-4), which is worth noting because
the mechanism is the same one that rule exists to stop: a reviewer reading the log believes
a broader change landed than did.

**Pattern:** an allowlist of syntactic forms, guarding against a class of mistake, where an
unlisted form is silence rather than a warning.

---
