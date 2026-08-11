---
description: "Run a full Fowler code-smell review by fanning out to two specialised reviewers in parallel — find-structural-smells (Sonnet, six local/mechanical smells) and find-design-smells (Opus, six cross-cutting/judgment smells) — then merging their findings into one prioritised report. Each finding names the smell and the refactoring that removes it."
---

# /code-smell-review — parallel Fowler code-smell review

Invoke the **`code-smell-review`** skill (via the Skill tool) and follow it. The skill runs
here in the top-level loop — it resolves the target, dispatches the two reviewers **in
parallel** (one Sonnet, one Opus), then merges their findings into one report at the
workspace root.

Do NOT dispatch a single agent to "do the review" — the fan-out must run at the top level so
it respects the depth-1 sub-agent limit (a sub-agent cannot spawn the two reviewers).

## Target resolution

Review, in priority order:

1. **Files/folders** the user named in `$ARGUMENTS`.
2. **Pasted code** inline in the message.
3. **Neither** — ask the user to paste, attach, or name the code.

```
/code-smell-review src/order/            # review a folder
/code-smell-review src/order/service.py  # review one file
/code-smell-review                        # review attached / pasted code
```

## Related surfaces

- `find-structural-smells` / `find-design-smells` — the two leaf reviewers; runnable
  standalone when you want only one bucket.
- `code-review-architect` / `/pr-review` — broad architectural review; use those instead when
  you want coupling/cohesion/framework-internals/defect coverage rather than the
  smell-and-refactoring lens.
