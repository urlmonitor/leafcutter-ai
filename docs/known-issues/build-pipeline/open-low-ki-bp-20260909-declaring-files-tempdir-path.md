---
title: "KI-BP-20260909-declaring-files-tempdir-path — the declaring-files scanner treats any `<anything> / \"_name.py\"` as a deployed sibling-module load, so a runtime-generated file written into a tempdir is demanded in the deployed tree"
description: "medium — fails closed (a spurious \"missing declaring file\", never a silent pass), but it blocks two required CI checks at once and the error names a file that is not supposed to exist, so the diagnosis is not obvious from the message."
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

# KI-BP-20260909-declaring-files-tempdir-path — the declaring-files scanner treats any `<anything> / "_name.py"` as a deployed sibling-module load, so a runtime-generated file written into a tempdir is demanded in the deployed tree

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — fails closed (a spurious "missing declaring file", never a silent pass), but it blocks two required CI checks at once and the error names a file that is not supposed to exist, so the diagnosis is not obvious from the message.
- **Status:** open — no AC. Worked around at the call site, not fixed at the scanner.
- **Occurrences:** 1 · **First seen:** 2026-09-07 (`BO-2900a-1-i`, PR #724, merged 16:01Z) · **Last seen:** 2026-09-07 · **Filed:** 2026-09-09
- **Where:** `scripts/ci/_declaring_files_scan.py:268-276`, in `_helper_module_declaring_files`.

**The mechanism.** The branch checks `isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)` and then inspects only `node.right`: if the right operand is a string constant matching `_HELPER_FILENAME_RE` (a leading-underscore `.py` name), the file is recorded as a declaring file that must exist under the deployed root. **The left operand is never examined.**

The comment immediately above it says otherwise:

```python
# Only a Path-join right operand counts as "loading a sibling
# file" (Path(__file__).resolve().parent / "_x.py"). A bare
# string constant elsewhere (e.g. name.endswith("_test.py"))
# is not a file-load and must not be treated as one.
```

That comment describes a `__file__`-anchored join, and the parenthetical even spells out the anchored form — but no code tests for it. The distinction the comment claims is the exact distinction the scanner cannot make.

**What it cost.** `done_proof.py`'s `_observe_reachability` materialises a runner script into a `TemporaryDirectory`:

```python
script_path = Path(tmp_dir) / "_reachability_runner.py"
```

Identical AST shape to a sibling-module load, so the scanner demanded a deployed `scripts/ac_store/_reachability_runner.py` — a file that never exists, being written fresh per invocation and dying with the tempdir. It failed the consumer-install job (which runs the scanner directly) and four cases in `unit_tests/portability/test_bp_900h_4_i.py` (which reach the same scanner through real `git clone --local` layouts). One cause, two checks, no shared symptom text.

**Workaround applied, and why it is not the fix.** Changed to `Path(tmp_dir, "_reachability_runner.py")`, which yields a `Call` node instead of a `BinOp` and no longer matches. Same path, same behaviour, and it is a syntax dodge: the next person to write `Path(x) / "_y.py"` for a non-sibling reason hits the same wall with no clue why, and nothing in the codebase warns them.

**Fix direction.** Test the left operand for `__file__` anchoring. The module already has exactly such a predicate — `_is_file_anchored_ancestor_walk` at `:99` — and already applies it at `:187`, though there it is handed an `ast.FunctionDef`, so it likely needs adapting rather than calling as-is on a `BinOp`'s left operand. Either way the concept is present in the file and simply is not consulted on this branch. If a tempdir-anchored join must still be distinguishable in some ambiguous case, prefer refusing to classify over classifying wrongly. Whatever is chosen, correct the comment: it currently documents a stricter rule than the code implements, which is what made the defect hard to see while reading the very lines that contain it.

**Related.**
- `KI-BP-20260909-declaring-files-helper-wrapped-import` (below) — same function's exemption logic, the other direction: an import that IS optional but is not recognised as such.
- `docs/reference/false-green-mechanisms.md` — not a false green (this one fails closed), but the same root shape: a comment asserting a check that the code does not perform.

**Pattern:** an AST pattern-match that recognises a syntactic shape and infers intent from it, with the comment describing the intent and the code matching only the shape.

---
