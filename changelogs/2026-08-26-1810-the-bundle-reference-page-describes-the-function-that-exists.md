---
title: The bundle's reference page describes the function that exists
date: "2026-08-26"
time: "18:10"
type: manual
components: 
  - build_orchestration
  - injection_builder
summary: "The fast-lane prompt-caching reference now matches the code, and no longer documents a cache TTL knob that does not exist."
description: "BO-2400c-1-vii. Ten regions of docs/reference/fast-lane-prompt-caching.md described an eight-parameter signature that BO-2400c-1-vi reduced to six, including three worked examples that would raise TypeError if copied. Corrected against the real docstring, with a new Removed Layers section explaining that the dropped content was relocated rather than deleted, and the membership rule that decides what the bundle carries. Separately, the Related Knob: Cache TTL section described a TTL configured in the API or harness layer and cited BO-2400c-2 for it — no such knob exists and that criterion was re-specified to measurement. Replaced with a section that separates the byte-identity the function guarantees from the provider cache hit nothing in leafcutter configures or observes."
---

## Entry

`BO-2400c-1-vi` removed two layers from the context bundle. Its criterion deliberately
left `docs/reference/fast-lane-prompt-caching.md` out of scope — a reference page is
documentation-expert's surface, not python-coder's — and instructed the implementer to
report the divergence so a companion record could be raised. This is that record.

### The page described a function that no longer existed

Ten separate regions were wrong, not one. The parameter-count sentence, the overview
table, the signature block, the parameters table, both halves of the ordering contract,
the cacheable-prefix paragraph, the return-value expression, all three worked examples,
and the caching section. Correcting only the signature block would have left nine.

The examples mattered most, because readers copy them. All three passed `conventions=`
and `acs=`, which now raise `TypeError` on the first call. Each corrected example was
executed against the real module before sign-off; all three run, and the minimal example's
claim about the breakpoint marker was checked by counting markers in the output rather
than asserted.

Two things the corrected page says that a mechanical find-and-delete would have missed:

- **The content moved; it was not dropped.** Both context-carrying dispatches now instruct
  their agent to read each id's record from the run's own store. A page saying only "the
  `acs` parameter was removed" would invite the conclusion that the coder no longer sees
  its acceptance criteria — false, and exactly the belief that would prompt someone to add
  the layer back.
- **The rule, not just the new list.** A reader who learns only that there are three layers
  now will add a fourth the next time something seems useful. The rule is that the bundle
  carries only what the receiving agent does not otherwise have, and it is why both layers
  went.

### The caching section was false, not stale

This one predates the layer removal and is the more serious of the two. "Related Knob:
Cache TTL" stated that an extended 1-hour cache TTL is "configured in the API or harness
layer (AC BO-2400c-2)". Nothing about that was true:

- `cache_control` appears nowhere in `scripts/`, `templates/` or `config/` — verified
  2026-08-18 and re-verified 2026-08-26.
- The cache breakpoint is a literal HTML comment inside a prompt string: a textual
  convention, not a provider cache-control block.
- leafcutter never issues the model API call. The workflow engine's `agent()` does, and it
  receives plain prompt text. There is no request on which a TTL could be set.
- `BO-2400c-2` was itself re-specified from configuration to **measurement**. It now asks
  for a context-reuse statement on a drive's terminal record. It does not ask anyone to set
  a TTL.

So the page cited a criterion for a claim that criterion no longer makes, about a knob that
never existed. Stale text describes something that used to be true; this described
something that never was. It is not softened to "not yet configured" — that phrasing would
preserve the impression that switching it on is a matter of turning something on.

The replacement section keeps two facts apart, and that separation is the whole correction:

- **What the function guarantees, and what is tested:** the stable prefix is byte-identical
  across invocations whenever `architecture`, `high_level` and `breakpoint_marker` are
  unchanged.
- **What that property was hoped to enable, and what nothing observes:** a provider-side
  KV-cache hit. leafcutter does not prime, request, or read back any cache state.

Collapsing that distinction in *either* direction gets the page wrong again — claiming a
cache exists, or claiming the layer ordering is therefore pointless. The ordering is a real,
tested property and the page still documents it as one.

Two leftover sentences elsewhere on the page asserted that "the KV-cache anchors on
everything before this marker" and that the prefix is "eligible for KV-cache reuse". Both
contradicted the new section and were corrected in the same pass; a page that refutes a
claim in one section while restating it in a table is not fixed.

### Scope

One file. The code was already correct as of `BO-2400c-1-vi` and is untouched here. No test
is attached, and `test_rationale` records why: the only mechanically checkable claim — that
the examples run — is verified by execution and already constrained by the subprocess tests
in `test_bo2400c1vi_bundle_layer_set.py`. A test asserting the string "conventions" is
absent from a page would pass the moment a word is deleted while the ordering, the required
count, or the caching claim stayed wrong. That is the grep-shaped evidence this AC family
rejects everywhere else, and it is no more acceptable because the target is Markdown.
