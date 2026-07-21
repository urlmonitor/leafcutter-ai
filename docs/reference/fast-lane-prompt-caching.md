---
title: "Reference: Fast-Lane Prompt-Caching Layout"
description: "Parameter table, ordering contract, breakpoint marker, and cacheable-prefix guarantee for assemble_context_bundle in scripts/injection_builders.py."
type: reference
status: active
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
  - injection_builder
related_docs:
  - docs/how-to/fast-lane-build.md
  - docs/how-to/choose-build-path.md
  - docs/architecture/components/injection-builder.md
---

# Fast-Lane Prompt-Caching Layout

Parameters, ordering contract, and cacheable-prefix guarantee for
`assemble_context_bundle` in `scripts/injection_builders.py` — the
pure-string function that assembles a layered LLM context bundle ordered
by change-frequency so the stable prefix is byte-identical across calls
and eligible for KV-cache reuse.

---

## Parameter Overview

`assemble_context_bundle` accepts eight keyword-only parameters. The first
five are required; the last three are optional.

| Parameter | Layer | Stable / Volatile | Change-frequency rank | Required |
|---|---|---|---|---|
| `architecture` | Stable prefix | Stable | 1 — lowest churn | Yes |
| `conventions` | Stable prefix | Stable | 2 | Yes |
| `high_level` | Stable prefix | Stable | 3 | Yes |
| `acs` | Volatile suffix | Volatile | 4 | Yes |
| `prior_tests` | Volatile suffix | Volatile | 5 | Yes |
| `prior_outputs` | Volatile suffix | Volatile | 6 | No — omitted when `None` |
| `working_diff` | Volatile suffix | Volatile | 7 — highest churn | No — omitted when `None` |
| `breakpoint_marker` | Separator | N/A | N/A | No — default `"<!-- CACHE_BREAKPOINT -->"` |

---

## `assemble_context_bundle`

### Signature

```python
def assemble_context_bundle(
    *,
    architecture: str,
    conventions: str,
    high_level: str,
    acs: str,
    prior_tests: str,
    prior_outputs: str | None = None,
    working_diff: str | None = None,
    breakpoint_marker: str = "<!-- CACHE_BREAKPOINT -->",
) -> str:
```

All parameters are keyword-only (enforced by the bare `*`). The function is
pure: no I/O, no external calls, no shared-state mutation. Callers may freely
construct the string arguments from any source.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `architecture` | `str` | — | Architecture documentation content. Most stable layer. Rarely changes across invocations. Placed first in the stable prefix. |
| `conventions` | `str` | — | Project coding and workflow conventions content. Changes infrequently. Placed second in the stable prefix. |
| `high_level` | `str` | — | L0/L1 parent AC content describing the big picture of the feature. Changes when feature scope changes. Placed third in the stable prefix, immediately before the breakpoint. |
| `acs` | `str` | — | Per-batch L2/L3 AC content. First volatile layer — changes with every new batch of work items. Placed immediately after the breakpoint. |
| `prior_tests` | `str` | — | Tests already written for the same component or area. Changes as the test suite grows. Placed after `acs` in the volatile suffix. |
| `prior_outputs` | `str \| None` | `None` | Distilled outputs carried forward from a prior agent phase. Optional; placed in the volatile suffix between `prior_tests` and `working_diff` when not `None`. Omitted entirely (no placeholder) when `None`. |
| `working_diff` | `str \| None` | `None` | Current working diff — the most volatile layer, changes on every file edit. Optional; placed last in the volatile suffix when not `None`. Omitted entirely when `None`. |
| `breakpoint_marker` | `str` | `"<!-- CACHE_BREAKPOINT -->"` | Literal string inserted once between the stable prefix and the volatile suffix. The KV-cache anchors on everything before this marker. Override only when integrating with a harness that uses a different sentinel. |

### Ordering Contract

Layers are assembled in fixed order. The stable prefix is built first:

```
{architecture}

{conventions}

{high_level}

{breakpoint_marker}
```

Then the volatile suffix follows immediately:

```
{acs}

{prior_tests}

[{prior_outputs}   ← included only when prior_outputs is not None]

[{working_diff}    ← included only when working_diff is not None]
```

All segments are joined with `"\n\n"` (double newline). The breakpoint marker
is appended to the stable prefix with `"\n\n"` before joining with the volatile
suffix.

Callers MUST NOT reorder arguments. The function enforces the order
programmatically by building `stable_prefix` and `volatile_layers` as ordered
sequences — the argument names are documentation, not position-independent
labels.

### Cacheable-Prefix Guarantee

The stable prefix (everything before and including the breakpoint marker) is
byte-identical across invocations whenever `architecture`, `conventions`,
`high_level`, and `breakpoint_marker` are unchanged — regardless of the values
of `acs`, `prior_tests`, `prior_outputs`, and `working_diff`.

This is the **cacheable-prefix property** (AC BO-2400c-1). An LLM KV-cache
implementation that anchors on the stable prefix will find a cache hit on every
call within the same session or batch where the stable inputs have not changed,
even though the volatile suffix changes per AC batch or per edit cycle.

The guarantee holds because the function is pure and the stable prefix is always
assembled identically from its three inputs plus the separator.

### Return Value

A single `str` containing:

```
{stable_prefix}\n\n{breakpoint_marker}\n\n{volatile_suffix}
```

where `volatile_suffix` is `"\n\n".join([acs, prior_tests, *optional_layers])`.
The return value always contains exactly one occurrence of `breakpoint_marker`.

### Prior-Phase Output Threading

The optional `prior_outputs` parameter is the mechanism for threading distilled
outputs from a prior agent phase into the current agent's context. When a
previous phase produces a summarized result (for example, the test-writer's
list of written stubs), that summary is passed as `prior_outputs` to the next
phase's bundle assembly, placing it in the volatile suffix between the
already-known test content (`prior_tests`) and the in-progress work
(`working_diff`). When no prior phase has run, pass `None` — the bundle
assembler omits the slot entirely without inserting a blank entry.

### Examples

**Minimal call (no optional layers):**

```python
from scripts.injection_builders import assemble_context_bundle

bundle = assemble_context_bundle(
    architecture="## Architecture\nThis service uses a layered repository pattern.",
    conventions="## Conventions\nAll public functions must have docstrings.",
    high_level="## L1 AC\nGiven a batch of approved ACs, the fast-lane loop builds them in two dispatches.",
    acs="## L2 ACs\n- BO-2400c-1: stable-prefix guarantee\n- BO-2400c-2: TTL configuration",
    prior_tests="## Prior Tests\nNo tests yet for this component.",
)
```

The resulting string contains one `<!-- CACHE_BREAKPOINT -->` dividing the
three stable layers from the two volatile layers.

**Call with optional layers (prior outputs and working diff included):**

```python
bundle = assemble_context_bundle(
    architecture=arch_content,
    conventions=conv_content,
    high_level=hl_content,
    acs=batch_ac_content,
    prior_tests=test_file_content,
    prior_outputs="Test-writer wrote 3 stubs: test_stable_prefix, test_ttl_config, test_threading.",
    working_diff="--- a/scripts/injection_builders.py\n+++ b/scripts/injection_builders.py\n...",
)
```

Both optional layers are placed after `prior_tests` in the volatile suffix,
in order: `prior_outputs` then `working_diff`.

**Custom breakpoint marker:**

```python
bundle = assemble_context_bundle(
    architecture=arch_content,
    conventions=conv_content,
    high_level=hl_content,
    acs=batch_ac_content,
    prior_tests=prior_tests_content,
    breakpoint_marker="<!-- STABLE_END -->",
)
```

The custom marker replaces the default HTML comment. The stable-prefix byte
identity guarantee still holds — the marker value is fixed at call time and
does not change between invocations.

---

## Related Knob: Cache TTL (out of scope)

The `assemble_context_bundle` function produces the prompt string; it does not
control how long the LLM API caches the stable prefix. That is governed by the
**extended 1-hour cache TTL** configured in the API or harness layer (AC
BO-2400c-2). The TTL is set on the API request, not in this module. When the
TTL expires the harness re-primes the cache by submitting a call whose stable
prefix is byte-identical to the previous one; `assemble_context_bundle` ensures
this is trivially achievable as long as the stable inputs have not changed.

---

## See Also

- [How to run the fast-lane build loop](../how-to/fast-lane-build.md) — step-by-step guide for invoking the `/fast-lane-build` workflow that assembles these bundles.
- [How to choose a build path](../how-to/choose-build-path.md) — routing decision tree for fast lane vs. heavy path.
- [Injection Builder component](../architecture/components/injection-builder.md) — architecture-level view of the component that owns `scripts/injection_builders.py`.
