---
title: "Reference: Fast-Lane Prompt-Caching Layout"
description: "Parameter table, ordering contract, breakpoint marker, and cacheable-prefix guarantee for assemble_context_bundle in scripts/injection_builders.py."
type: reference
status: active
created: 2026-07-21
last_updated: 2026-08-26
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
by change-frequency so the stable prefix is byte-identical across calls.

That byte-identity is a property of this function's output and is what the
page below specifies. It is *not* a claim that any provider cache is
configured or observed — nothing in leafcutter does either. See
[Prompt Caching: What This Function Does and Does Not Guarantee](#prompt-caching-what-this-function-does-and-does-not-guarantee).

---

## Parameter Overview

`assemble_context_bundle` accepts six keyword-only parameters. The first
three are required; the last three are optional.

Membership in this table is governed by one rule: **the bundle carries only
content the receiving agent does not otherwise have.** Two former parameters,
`conventions` and `acs`, were removed under this rule rather than defaulted
to optional — see [Removed Layers](#removed-layers-conventions-and-acs) below.

| Parameter | Layer | Stable / Volatile | Change-frequency rank | Required |
|---|---|---|---|---|
| `architecture` | Stable prefix | Stable | 1 — lowest churn | Yes |
| `high_level` | Stable prefix | Stable | 2 | Yes |
| `prior_tests` | Volatile suffix | Volatile | 3 | Yes |
| `prior_outputs` | Volatile suffix | Volatile | 4 | No — omitted when `None` |
| `working_diff` | Volatile suffix | Volatile | 5 — highest churn | No — omitted when `None` |
| `breakpoint_marker` | Separator | N/A | N/A | No — default `"<!-- CACHE_BREAKPOINT -->"` |

---

## `assemble_context_bundle`

### Signature

```python
def assemble_context_bundle(
    *,
    architecture: str,
    high_level: str,
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
| `high_level` | `str` | — | L0/L1 parent AC content describing the big picture of the feature. Changes when feature scope changes. Placed second in the stable prefix, immediately before the breakpoint. |
| `prior_tests` | `str` | — | Tests already written for the same component or area. Changes as the test suite grows. First volatile layer — placed immediately after the breakpoint. |
| `prior_outputs` | `str \| None` | `None` | Distilled outputs carried forward from a prior agent phase. Optional; placed in the volatile suffix between `prior_tests` and `working_diff` when not `None`. Omitted entirely (no placeholder) when `None`. |
| `working_diff` | `str \| None` | `None` | Current working diff — the most volatile layer, changes on every file edit. Optional; placed last in the volatile suffix when not `None`. Omitted entirely when `None`. |
| `breakpoint_marker` | `str` | `"<!-- CACHE_BREAKPOINT -->"` | Literal string inserted once between the stable prefix and the volatile suffix. It marks where the byte-identical prefix ends — it is a textual convention inside the prompt, not a provider cache-control directive, and nothing in this system reads it back. Override only when integrating with a harness that uses a different sentinel. |

### Removed Layers: `conventions` and `acs`

Two parameters that used to sit in this table, `conventions` and `acs`, were
removed entirely (BO-2400c-1-vi) — not made optional, not defaulted to
`None`. Passing either keyword now raises `TypeError`. Their content did not
disappear; it moved to a place the receiving agent reads directly instead of
receiving inline:

- `conventions` — the harness already injects the workspace's CLAUDE.md into
  every agent dispatched into that workspace, so this layer was a second
  copy of text the receiving agent is handed anyway (measured
  byte-identical to CLAUDE.md at 38,291 bytes on the run that failed).
- `acs` — the run's acceptance-criteria store sits inside the run's own
  isolated workspace, where any agent working there can open it. Both
  context-carrying dispatches in `templates/workflows-js/fast-lane-ship.js`
  now instruct their agent to read each id's YAML record from that store
  directly, rather than receiving the record text inline.

Together the two removed layers were 129,178 of 148,891 bytes — 87% of a
bundle that had grown too large to cross an agent boundary as text in a
return value. They were removed rather than defaulted because an optional
layer leaves a live path by which the largest duplicate in the payload gets
reintroduced by a caller who does not know better. See
[BO-2400c-1-vi](../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400c-1-vi.yaml)
for the full reasoning and measurement.

### Ordering Contract

Layers are assembled in fixed order. The stable prefix is built first:

```
{architecture}

{high_level}

{breakpoint_marker}
```

Then the volatile suffix follows immediately:

```
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
byte-identical across invocations whenever `architecture`, `high_level`, and
`breakpoint_marker` are unchanged — regardless of the values of
`prior_tests`, `prior_outputs`, and `working_diff`.

This is the **cacheable-prefix property** (AC BO-2400c-1) — a tested fact about
this function's output, not a claim about any provider's cache behavior. It
is what makes a provider-side KV-cache hit *possible* if the harness or API
layer anchors on the stable prefix; leafcutter does not itself configure,
prime, or observe any such hit (see
[Prompt Caching: What This Function Does and Does Not Guarantee](#prompt-caching-what-this-function-does-and-does-not-guarantee)
below).

The guarantee holds because the function is pure and the stable prefix is always
assembled identically from its three inputs (`architecture`, `high_level`,
`breakpoint_marker`) plus the separator.

### Return Value

A single `str` containing:

```
{stable_prefix}\n\n{breakpoint_marker}\n\n{volatile_suffix}
```

where `volatile_suffix` is `"\n\n".join([prior_tests, *optional_layers])`, and
`optional_layers` accumulates `prior_outputs` then `working_diff`, each only
when not `None`. The return value always contains exactly one occurrence of
`breakpoint_marker`.

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
    high_level="## L1 AC\nGiven a batch of approved ACs, the fast-lane loop builds them in two dispatches.",
    prior_tests="## Prior Tests\nNo tests yet for this component.",
)
```

The resulting string contains one `<!-- CACHE_BREAKPOINT -->` dividing the
two stable layers from the single volatile layer.

**Call with optional layers (prior outputs and working diff included):**

```python
bundle = assemble_context_bundle(
    architecture=arch_content,
    high_level=hl_content,
    prior_tests=test_file_content,
    prior_outputs="Test-writer wrote 3 stubs: test_stable_prefix, test_context_reuse, test_threading.",
    working_diff="--- a/scripts/injection_builders.py\n+++ b/scripts/injection_builders.py\n...",
)
```

Both optional layers are placed after `prior_tests` in the volatile suffix,
in order: `prior_outputs` then `working_diff`.

**Custom breakpoint marker:**

```python
bundle = assemble_context_bundle(
    architecture=arch_content,
    high_level=hl_content,
    prior_tests=prior_tests_content,
    breakpoint_marker="<!-- STABLE_END -->",
)
```

The custom marker replaces the default HTML comment. The stable-prefix byte
identity guarantee still holds — the marker value is fixed at call time and
does not change between invocations.

---

## Prompt Caching: What This Function Does and Does Not Guarantee

There is no cache TTL knob anywhere in this system. Verified 2026-08-18 and
re-verified 2026-08-26: the string `cache_control` appears nowhere in
`scripts/`, `templates/`, or `config/`; `breakpoint_marker` is a literal
HTML-comment string inserted into a prompt (a textual convention, not a
provider cache-control mechanism); and leafcutter never issues the model API
call itself — the workflow engine's `agent()` call does, and it receives
plain prompt text. There is therefore no request on which any TTL could be
set, extended, or configured.

Keep these two facts distinct:

- **What `assemble_context_bundle` guarantees (real, tested):** the stable
  prefix — `architecture` + `high_level` + `breakpoint_marker` — is
  byte-identical across invocations whenever those three inputs are
  unchanged. See [Cacheable-Prefix Guarantee](#cacheable-prefix-guarantee).
- **What that property was hoped to enable (not observed, not configured,
  not measured by anything in this module):** a provider-side KV-cache hit
  on the stable prefix. Nothing in leafcutter primes, requests, or reads
  back a provider cache state.

[BO-2400c-2](../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400c-2.yaml)
does not ask for a TTL setting — it was re-specified away from configuration
to measurement. It asks for a context-reuse statement on a drive's terminal
record: how many context-carrying invocations the drive made, how many of
those were presented a stable prefix byte-identical to the first one, and
whether the anchor held for the whole drive. That statement is derived from
the prefixes the drive actually presented, not from re-assembling the bundle
afterward — it measures whether the byte-identical-prefix property held in
practice, not whether a provider cache was hit.

---

## See Also

- [How to run the fast-lane build loop](../how-to/fast-lane-build.md) — step-by-step guide for invoking the `/fast-lane-build` workflow that assembles these bundles.
- [How to choose a build path](../how-to/choose-build-path.md) — routing decision tree for fast lane vs. heavy path.
- [Injection Builder component](../architecture/components/injection-builder.md) — architecture-level view of the component that owns `scripts/injection_builders.py`.
- [BO-2400c-1-vi](../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400c-1-vi.yaml) — the record that removed the `conventions` and `acs` layers and carries the duplication measurement and reasoning behind it.
