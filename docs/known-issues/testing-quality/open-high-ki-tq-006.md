---
title: "KI-TQ-006 — A matcher widening measured by its own author's grep: estimated one false positive, actual twenty-three"
description: "high as a pattern — the flawed measurement and the flawed code shared one author"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-006 — A matcher widening measured by its own author's grep: estimated one false positive, actual twenty-three

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high as a pattern — the flawed measurement and the flawed code shared one author
  and one blind spot
- **Status:** open as a pattern. The specific instance is fixed and is recorded in
  `build-orchestration.md`'s `KI-BO-003`; **the general rule below has no enforcement** and that
  is why this stays open. `main` has since committed the same shape a second time — see
  `commit-guardian.md`'s final entry, whose own text records a per-marker cost generalised from
  the one marker that was measured.
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26
- **Where:** `scripts/build_placeholder_detection.py` (`_is_marker_at_line_start`,
  `_LEADING_MARKER_PREFIX`)

**Symptom.** A matcher was widened. Its cost was estimated with a grep, and the estimate said
"one instance". The true cost was **23 false positives across 4,815 files**. The grep searched
for *bulleted* markers; the rule that shipped also accepted *bare indentation*:

```python
_LEADING_MARKER_PREFIX = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*")
```

The bullet is **optional**, so bare indentation qualifies too — and in YAML block scalars and
wrapped markdown, *every* continuation line is indented. Any prose line beginning with the word
"placeholder" was flagged. **The shape that was never searched for is exactly the shape that was
wrong.**

**Evidence — three independent safety nets were green the whole time:**

| net | why it missed |
|---|---|
| 84 unit tests across two tripwire files | corpus authored from the same mental template as the grep |
| a canary asserting one file scans clean | that file happened to have no indented prose starting with the word |
| a full 3,729-test suite | nothing in it scans the AC store or agent templates |

A repo-wide before/after diff of the committed scanner against the working tree, over 4,815
files, is what actually measured it: 72 hits before, 94 after, **24 new — of which 23 were false
positives**, spanning 12 AC YAML files, 4 agent templates, a generated agent card, 4 tickets and
2 skill docs.

**Detection.** After changing any matcher, run it over the **whole repository** before and after
and diff the hit sets. Not a count — the actual set, with enough context to judge each new hit.
`git show HEAD:<file>` gives the baseline implementation, so this needs no branch juggling:

```python
before = load_module_from(git_show("HEAD:scripts/<matcher>.py"))
after  = load_module_from(worktree_path)
new    = after_hits - before_hits      # judge every element
```

**Fix direction (pattern).** For every matcher with a false-positive cost, keep a **repo-scale
canary** asserting zero hits over a large real corpus, not a handful of hand-picked files.
`test_ge122b_acceptance_criteria_tree_placeholder_hits_are_zero` scans all 3,092 AC YAML files
in ~1.3s. Scope it to the marker under test — that tree has legitimate `todo` hits which a naive
zero-hits assertion would have gone red on, pushing the next author to break `TODO` instead.
And measure **per marker**, never in aggregate: the second occurrence tightened the marker
responsible for 2 of 55 hits and left untouched the one responsible for 42.

**The generalisation, since this keeps being rediscovered:** an estimate produced by the person
who wrote the rule tests their model of the rule, not the rule. Only running it over data nobody
curated can falsify it.

---
