---
title: "KI-CG-008 — `check-doc-frontmatter` crashes with a `TypeError` on any non-string entry in `related_docs`, making the labelled-list form uncommittable"
description: "KI-CG-008 — `check-doc-frontmatter` crashes with a `TypeError` on any non-string entry in `related_docs`, making the labelled-list form uncommittable"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-008 — `check-doc-frontmatter` crashes with a `TypeError` on any non-string entry in `related_docs`, making the labelled-list form uncommittable

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `templates/scripts/commit_guardian/frontmatter_validators.py:226-250`
  (`validate_paths`), crash at `:245`
- **Reported by:** adopter repo DIAGraph (`roche-sandbox/dia-graph`), against pin `54356a92`

**Symptom.** The hook aborts with an unhandled traceback rather than emitting a validation
error:

```text
File ".leafcutter/scripts/commit_guardian/frontmatter_validators.py", line 246, in validate_paths
    full_path = project_root_path / p
                ~~~~~~~~~~~~~~~~~~^~~
TypeError: unsupported operand type(s) for /: 'PosixPath' and 'dict'
```

**Root cause.** `validate_paths` guards that the *field* is a list and never that its
*elements* are strings:

```python
path_fields = ["related_docs", "related_code", "architecture_diagrams"]

for field in path_fields:
    paths = fm.get(field)
    if not paths or not isinstance(paths, list):
        continue
    for p in paths:
        full_path = project_root_path / p     # p may be a dict
```

An adopter whose convention labels each related doc with its Diataxis genre —

```yaml
related_docs:
  - explanation: docs/explanation/architecture.md
```

— hands YAML a mapping, so `p` is `{"explanation": "docs/explanation/architecture.md"}` and
`Path / dict` raises. Nothing in the package declares which shape is canonical:
`doc_types.json` says nothing about `related_docs`, and the hook's own README describes only
"path existence of `related_docs` / `related_code`". So an adopter has no way to learn the
constraint except by crashing into it.

**Scope.** Not an outlier in the reporting repo — it is the dominant convention there. Of
50 documents under `docs/**/*.md` declaring `related_docs`, **at least 33** use the mapping
form. Every one of them is uncommittable, and because the hook crashes rather than failing,
the practical workaround is `SKIP=check-doc-frontmatter` — which is worse than a strict
gate, since it teaches the reflex that also disables the ~40 hooks that were working.

**Reproduce.** From a checkout where the declaring config is reachable (otherwise KI-BP-003
masks this by crashing first):

```bash
python .leafcutter/scripts/commit_guardian/check_doc_frontmatter.py docs/reference/configuration.md
```

**Scope note.** `check_adr_cross_reference._doc_mentions_adr` also consumes `related_docs`
but does a raw case-insensitive substring match over the whole file, so it is unaffected.
`validate_paths` is the only consumer that indexes into the elements.

**Fix direction.** Normalise the element before use and decide deliberately which form is
canonical — then say so somewhere an author will read. Accepting both is cheap:

```python
for p in paths:
    if isinstance(p, dict):
        candidates = [v for v in p.values() if isinstance(v, str)]
    elif isinstance(p, str):
        candidates = [p]
    else:
        errors.append(f"Unsupported entry in '{field}': {p!r}")
        continue
    for c in candidates:
        if not (project_root_path / c).exists():
            errors.append(f"Broken path in '{field}': '{c}' does not exist")
```

Whichever shape wins, the validator must **reject an unsupported shape with a message**
rather than raise. A hook that crashes on valid-looking YAML cannot be complied with, only
bypassed.

**Pattern:** the inverse of the usual false-green — a gate so brittle that the only
available response is to turn it off, taking every sibling hook with it.

**Re-verified 2026-09-23: STILL TRUE — unchanged, kept open.** The named code is unchanged
from the entry's own quoted excerpt:

```
$ grep -n "for p in paths\|full_path = project_root_path" templates/scripts/commit_guardian/frontmatter_validators.py
245:        for p in paths:
246:            full_path = project_root_path / p
```

`validate_paths` (`frontmatter_validators.py:236-249`) still guards only that the *field* is a
list (`if not paths or not isinstance(paths, list): continue`) and never that its *elements*
are strings — there is no `isinstance(p, dict)` or equivalent branch anywhere in the function.
A `related_docs` entry in the labelled-mapping form (`- explanation: docs/...md`) still hands
`p` as a `dict` to `project_root_path / p` at line 246, which still raises the same
`TypeError: unsupported operand type(s) for /: 'PosixPath' and 'dict'` the entry's Symptom
quotes. No normalisation, no rejection-with-message, and no canonical-shape declaration have
been added. Mechanism confirmed present; kept open.

---
