---
title: "How to choose the right build path"
description: "Decide whether to invoke the fast-lane or heavy-pipeline build path for a ticket based on scope, attended mode, and defect cost."
type: how-to
category: how-to
status: active
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
related_docs:
  - docs/how-to/fast-lane-build.md
  - docs/architecture/diagrams/c2-fast-lane-build-path-components.md
  - docs/architecture/diagrams/c2-fast-vs-heavy-lane-phases.md
  - docs/architecture/components/build-orchestration.md
---

# How to choose the right build path

Leafcutter supports two build pipeline lanes:

- **Fast lane** — reduced verification suite for small, interactive, low-risk tickets.
  Skips the heavier review phases to minimize overhead.
- **Heavy pipeline** — full verification suite for large, unattended, or high-risk
  tickets. Every quality gate runs.

The routing decision is made by a single deterministic function:
`choose_lane()` in `scripts/build_orchestration/path_selection.py`. This guide
explains the decision rule, the ambiguous-scope safe default, and how to supply
an explicit lane override when needed.

---

## The decision rule

`choose_lane()` evaluates the routing in two steps. Step 1 is always checked first
and wins unconditionally when it applies. Step 2 runs only when no valid override is
present.

### Step 1 — Override check (unconditional win, BO-2400b-3-ii)

If the caller passes `override="fast"` or `override="heavy"`, that lane is used
immediately. The rule from Step 2 is still computed for auditability, but it does not
affect the outcome. The returned dict sets `overridden=True` and the `reason` field
records both the requested override and the lane the rule would have selected, so the
supersession is always traceable.

Any other value for `override` — including `None` (the default) or an unrecognized
string — is ignored. The rule in Step 2 then determines the lane.

### Step 2 — Documented single rule

When no valid override is present, the lane is determined by three inputs:

| Input | Type | Recognized values |
|---|---|---|
| `scope` | `str` | `"scoped"`, `"large"` |
| `attended` | `bool` | `True`, `False` |
| `defect_cost` | `str` | `"low"`, `"high"` |

**Fast lane** is selected if and only if ALL three conditions hold simultaneously:

1. `scope == "scoped"` — small blast radius (the ticket touches few files or a bounded area)
2. `attended is True` — the build is interactive; a human is present to respond if something goes wrong
3. `defect_cost == "low"` — an escaped defect reaching production has a low cost

**Heavy pipeline** is selected when ANY of the following is true:

- `scope == "large"` — large blast radius
- `attended is False` — unattended or batch build (no human available to intervene)
- `defect_cost == "high"` — an escaped defect has high cost

The rule is fail-closed: only the exact all-three-conditions-met combination routes
to fast. Any other recognized combination routes to heavy.

### Decision table

| scope | attended | defect_cost | lane |
|---|---|---|---|
| `"scoped"` | `True` | `"low"` | **fast** |
| `"scoped"` | `True` | `"high"` | heavy |
| `"scoped"` | `False` | `"low"` | heavy |
| `"scoped"` | `False` | `"high"` | heavy |
| `"large"` | `True` | `"low"` | heavy |
| `"large"` | `True` | `"high"` | heavy |
| `"large"` | `False` | `"low"` | heavy |
| `"large"` | `False` | `"high"` | heavy |
| unrecognized | (any) | (any) | heavy (ambiguous default) |

---

## Ambiguous-scope safe default (BO-2400b-3-i)

When `scope` is neither `"scoped"` nor `"large"`, the value is unrecognized. Rather
than raising an error or routing to fast, the function defaults to the **heavy pipeline**
(fail-closed) and sets `ambiguous=True` in the returned dict.

This is the safe default: it is always safer to run the full verification suite on a
ticket with an unclear scope than to skip verification and discover the problem in
production.

Callers should inspect the `ambiguous` field and surface a warning to the operator
when it is `True`, so they know the default was applied and can supply a recognized
scope value if appropriate:

```python
result = choose_lane(
    scope=scope,
    attended=attended,
    defect_cost=defect_cost,
    override=override,
)
if result["ambiguous"]:
    warn(f"Ambiguous scope — defaulting to heavy pipeline: {result['reason']}")
dispatch_lane(result["lane"])
```

The `reason` field always contains a human-readable explanation of why the heavy
default was applied, including the unrecognized scope value that triggered it.

---

## How to supply an explicit override

Pass `override="fast"` or `override="heavy"` to `choose_lane()`. The override wins
unconditionally, even when the rule would select the other lane.

```python
# Force the fast lane regardless of scope/attended/defect_cost:
result = choose_lane(
    scope="large",
    attended=False,
    defect_cost="high",
    override="fast",
)
# result["lane"]       == "fast"
# result["overridden"] == True
# result["reason"]     starts with "Lane overridden to 'fast' (rule would have selected 'heavy')."
```

```python
# Force the heavy pipeline regardless of scope/attended/defect_cost:
result = choose_lane(
    scope="scoped",
    attended=True,
    defect_cost="low",
    override="heavy",
)
# result["lane"]       == "heavy"
# result["overridden"] == True
# result["reason"]     starts with "Lane overridden to 'heavy' (rule would have selected 'fast')."
```

The `reason` field records both the override and what the rule would have chosen,
providing an audit trail without requiring the caller to re-run the rule separately.

When the override value is not one of `"fast"` or `"heavy"` (including `None`),
it is silently ignored and the rule determines the lane. This means omitting
`override` (using the default `None`) is always safe.

---

## Return value reference

`choose_lane()` always returns a `dict` with four keys:

| Key | Type | Description |
|---|---|---|
| `lane` | `str` | `"fast"` or `"heavy"` — the selected lane |
| `reason` | `str` | Human-readable explanation of the routing decision (always non-empty) |
| `ambiguous` | `bool` | `True` if scope was unrecognized and the heavy default was applied (BO-2400b-3-i) |
| `overridden` | `bool` | `True` if an explicit override was supplied and applied (BO-2400b-3-ii) |

Note: `ambiguous` and `overridden` can both be `True` simultaneously when an override
is supplied alongside an unrecognized scope value. In that case the override wins the
lane, but the `reason` still records that the scope was unrecognized.

---

## Choosing inputs in practice

**scope**

Set `scope="scoped"` when the ticket touches a bounded area with a small blast radius —
a single module, a single agent template, a documentation file, or a narrow config
change. Set `scope="large"` when the ticket touches shared infrastructure, a build
phase, a schema migration, or multiple high-coupling components.

When you are genuinely unsure, treat the scope as `"large"`. The rule defaults to heavy
on any unrecognized value (see the ambiguous-scope section above), so the fail-closed
behavior applies whether you leave `scope` as an unrecognized string or explicitly set
it to `"large"`.

**attended**

Set `attended=True` for interactive single-ticket builds where a human is watching
and can respond to questions or blockers. Set `attended=False` for batch drives,
CI-triggered builds, or any build that runs without a human monitoring the session.

**defect_cost**

Set `defect_cost="low"` for documentation, configuration, and test-only tickets where
a regression is caught easily and has no user impact. Set `defect_cost="high"` for
tickets that touch user-facing surfaces, data pipelines, agent dispatch logic, or
pre-commit hooks — anywhere that an escaped defect is hard to detect or costly to
reverse.

---

## See Also

- [Fast-lane build](fast-lane-build.md) — what the fast lane runs and when to expect
  it to be faster.
- [C2 diagram: fast lane vs heavy lane phases](../architecture/diagrams/c2-fast-vs-heavy-lane-phases.md) —
  visual comparison of the phase sets for each lane.
- [C2 diagram: fast-lane build-path components](../architecture/diagrams/c2-fast-lane-build-path-components.md) —
  component-level view of the fast-lane pipeline.
- [Build orchestration component](../architecture/components/build-orchestration.md) —
  architecture reference for the build orchestration layer.
- `scripts/build_orchestration/path_selection.py` — the authoritative implementation
  of `choose_lane()` that this guide documents.
