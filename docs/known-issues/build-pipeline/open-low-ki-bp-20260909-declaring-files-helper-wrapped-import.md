---
title: "KI-BP-20260909-declaring-files-helper-wrapped-import — only an import written lexically inside `try/except ImportError` is treated as optional, so guarding the *call* instead of the *import* reads as a hard dependency"
description: "medium — fails closed, blocks the consumer-install check, and pushes authors toward duplicating an import at every call site rather than factoring it into a helper."
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

# KI-BP-20260909-declaring-files-helper-wrapped-import — only an import written lexically inside `try/except ImportError` is treated as optional, so guarding the *call* instead of the *import* reads as a hard dependency

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — fails closed, blocks the consumer-install check, and pushes authors toward duplicating an import at every call site rather than factoring it into a helper.
- **Status:** open — no AC. Worked around by inlining the import; the scanner is unchanged.
- **Occurrences:** 1 · **First seen:** 2026-09-08 (`BO-2900d-2`, PR #729, merged 05:44Z) · **Last seen:** 2026-09-08 · **Filed:** 2026-09-09
- **Where:** `scripts/ci/_declaring_files_scan.py:212-231` (`_import_error_guarded_names`), consumed at `:247`.

**The mechanism.** `_import_error_guarded_names` walks for `ast.Try` nodes with an `ImportError` handler and collects import names **inside that node's body**. Exemption is therefore purely lexical: the `import` statement must itself sit within the `try` block. An import inside a helper function whose *call site* is wrapped in `try/except ImportError` is not collected, so the imported module is reported as a declaring file the guardrail cannot run without.

**What it cost.** `done_proof.py` reached the shared BO-2900d reachability seam through a `_load_reachability_seam()` helper. The helper's call was correctly guarded — an absent seam degraded to "no exemptions" exactly as intended — but because the `from _reachability_inventory import ...` sat inside the helper rather than inside the `try`, the scanner demanded `scripts/commit_guardian/_reachability_inventory.py` exist in a consumer install that has no reason to ship it.

**Why this is not simply "write it the other way".** The helper existed for a reason: one import site, one docstring explaining the optionality, one place to change. The scanner's rule quietly forbids that factoring for any optional dependency, and forbids it *silently* — nothing says "your guard is in the wrong place", only "this file is missing". The workaround (inline the import into the `try` at its single call site) happened to be fine here because there was exactly one call site; with two or more, the rule forces duplicated import-and-guard blocks.

**Fix direction, in preference order.** (1) Follow one level of indirection: if a name is imported inside a function whose every call site is `ImportError`-guarded, treat it as guarded. Sound but needs a call-graph walk the module does not currently do. (2) Honour an explicit opt-out marker — a recognised comment or a module-level `__optional_declaring_files__` tuple — so an author can state optionality the scanner cannot infer. Cheaper, and it makes the claim reviewable. (3) At minimum, improve the message: when a leading-underscore sibling import is reported missing, say that a `try/except ImportError` **around the import statement itself** is what marks it optional. That converts the current dead end into a one-line fix for whoever hits it next.

**Related.**
- `KI-BP-20260909-declaring-files-tempdir-path` (above) — same function, the mirror-image error: a shape that is *not* a dependency being treated as one.
- The "New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest" convention in `CLAUDE.md` — this scanner is the mechanical enforcement of that rule; both entries are about it over-reaching.

**Pattern:** a static analyser inferring optionality from lexical position, where the property it is actually trying to detect (does this code tolerate the module's absence?) is a runtime one.
