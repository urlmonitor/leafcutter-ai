---
title: Required and optional bundle layers stop sharing one nullable type
date: "2026-08-26"
time: "19:55"
type: manual
components: 
  - build_orchestration
  - injection_builder
summary: "The assemble-bundle subcommand reads required and optional layers in separate passes, so the three required ones are typed as strings rather than as possibly-absent."
description: "The informational mypy CI check reported three arg-type errors in _cmd_assemble_bundle: contents was a dict[str, str | None] whose required entries were passed to str parameters. Behaviour was never wrong -- argparse marks those three required=True -- but the code could not state that, so the checker was right to complain. Split into a required pass typed dict[str, str] and an optional pass typed dict[str, str | None], with a fail-closed guard on the required pass. Output verified byte-identical before and after on both the minimal and the all-optional-layers call. Pre-existing: five such errors before BO-2400c-1-vi, three after."
---

## Entry

The informational `Type-check changed files (mypy)` job reported three errors in
`_cmd_assemble_bundle`:

```text
scripts/injection_builders.py:761: error: Argument "architecture" to
  "assemble_context_bundle" has incompatible type "str | None"; expected "str"
```

Nothing was behaving wrongly. `--architecture`, `--high-level` and `--prior-tests` are all
`required=True`, and `_read_optional_layer` returns `None` only for a `None` path — so those
three entries can never actually be `None`. The problem was that the code had no way to
*say* so. One loop read all five layers into a single `dict[str, str | None]`, and the three
required entries were then handed to parameters declared `str`. The checker was right: the
type said "might be absent" and the call site required "present", and the only thing closing
that gap was a fact about argparse that lived nowhere in the types.

The fix is to stop flattening two different kinds of layer into one container. Required
layers are read in their own pass into a `dict[str, str]`; optional layers into a
`dict[str, str | None]`. The distinction was always real — it is what `required=True` means —
and it is now visible in the code rather than implied by a CLI declaration several hundred
lines away.

The required pass carries a fail-closed guard for the missing-path case. That branch is
unreachable today, and it is deliberately a guard rather than an `assert`: asserts vanish
under `-O`, and if the `required=True` flag were ever relaxed the alternative is `None`
reaching `"\n\n".join()` and raising a `TypeError` far from its cause — or, worse, a layer
silently emptied while the bundle still looks well-formed. That second outcome is the one
worth spending three lines on: an empty layer in a bundle that still carries its breakpoint
marker is exactly the shape `BO-2400c-1-iii`'s incompleteness check exists to catch, and the
cheaper place to stop it is here.

**Behaviour is unchanged, and that was checked rather than assumed.** The subcommand was run
against the same real on-disk layer files before and after the change, both for the minimal
three-layer call and for the call supplying `--prior-outputs` and `--working-diff`; both
pairs of outputs are byte-identical (`diff` exit 0). The full `unit_tests/workflows` and
`unit_tests/build_orchestration` suites pass (726 passed, 4 xfailed).

**This was pre-existing, not new.** The same imprecision produced *five* errors before
`BO-2400c-1-vi` removed two layers, and three after — that change reduced the count without
addressing the cause. It surfaced now only because a test added in `BO-2400c-1-vii` imports
the module, which pulls it into mypy's changed-file scope. Worth noting for anyone reading
CI history: the check reported SUCCESS on the PR that touched this same function while the
five errors were present, so its green there was not evidence of a clean file.
