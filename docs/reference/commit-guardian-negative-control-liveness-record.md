---
title: "Reference: Commit Guardian Negative-Control — Record Fields"
description: "Field-by-field shapes for negative_control, the acceptable-input pair, currently, demonstration, and discrimination — plus the NEGATIVE_CONTROL_RESULT stdout-line grammar check_negative_control_liveness.py produces."
type: reference
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - commit_guardian
related_docs:
  - docs/reference/commit-guardian-negative-control-liveness.md
  - config/verification_flow.schema.json
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1-ii.yaml
---

# Commit Guardian Negative-Control — Record Fields

> **Parent document:** [Commit Guardian Negative-Control Liveness](commit-guardian-negative-control-liveness.md)
> — CLI usage, `hooks_manifest` registration, and the "Declaring a check"
> walkthrough live there.

Field-by-field reference for the shapes `check_negative_control_liveness.py`
reads and writes, and the stdout-line grammar it emits.

---

## `negative_control` field shape

Source of truth: `config/verification_flow.schema.json` `$defs/negative_control`.
Not duplicated here beyond field names and required-ness. A `negative_control`
value is exactly one of the two shapes below (`oneOf`).

### Falsifiable shape

| Field | Type | Required | Description |
|---|---|---|---|
| `input` | string | **yes** | The known-bad artifact, record, or invocation fed through the same entry point. |
| `command` | string | no | Single simple command that feeds the known-bad input through the entry point. Absent means this runner cannot examine the hook and records `blocked`. |
| `expected_result` | string | **yes** | The observable rejection. Today's only recognized value is `"non-zero exit"` — this runner reads exit code, never expected-result text, to decide the state. |
| `currently` | object | **yes** | The observed-state block — see below. Written by this runner, never hand-authored for an examined hook. |

### `not_applicable` shape

| Field | Type | Required | Description |
|---|---|---|---|
| `not_applicable` | boolean (`const: true`) | **yes** | Declares the hook has no known-bad input of its own to reject — a census/measurement check, not a judging gate. |
| `reason` | string | **yes** | Why no known-bad input is meaningful for this hook. |

A hook whose `negative_control.not_applicable` is `true` is skipped
entirely by the sweep — it is never examined and never gets a `currently`
block, and (as of GE-120f-1-ii) the acceptable-input pairing logic never
runs for it either.

---

## Acceptable input — hook-level `command` / `pass_criteria`

As of GE-120f-1-ii, a hook may declare two further top-level keys, siblings
of `negative_control` in the SAME `hooks_manifest.hooks[]` entry — never a
second declaration store. Both field names are copied verbatim from
`config/verification_flow.schema.json`'s own `$defs/check` shape, where
`command`/`pass_criteria` already sit beside `negative_control` within one
check object, for a different artifact type.

| Field | Type | Required | Description |
|---|---|---|---|
| `command` | string | no | Single simple command that feeds the check's *acceptable* input through the same entry point as `negative_control.command`. Absent, empty, or tokenizing (`shlex.split`) to the identical argv as `negative_control.command` means the pair cannot discriminate — see `discrimination` below. |
| `pass_criteria` | string | no | Today's only implemented reading is `"zero exit"` — the direct counterpart of `negative_control`'s own hardcoded "non-zero exit" reading. No generic parser exists; a different string is accepted but not interpreted differently. |

Both `negative_control.command` and this `command` are read from ONE hook
entry, at ONE path, every run. Removing either side (without touching the
other) is caught by the SAME `discrimination` classification below, never
by a second store going stale independently of the first.

---

## `currently.state` — as this runner observes it

Schema enum: `passing`, `failing`, `blocked`, `unverified`
(`config/verification_flow.schema.json` `$defs/currently.state`). The table
below states what each value means as **produced by
`check_negative_control_liveness.py`**, not as an abstract concept.

| State | Produced when |
|---|---|
| `passing` | The hook was examined, both declared commands ran as real subprocesses in the SAME run, the negative-control command exited non-zero, the acceptable-input command exited zero, **and** the negative-control invocation was classified `demonstration: "entry_point"` — i.e. `discrimination: "discriminates"` below. |
| `failing` | The hook was examined and its negative-control command ran, but the declared rejection was not observed through the entry point (zero exit, or non-zero exit classified `reach_inside`), **or** the acceptable-input command was also rejected — see `discrimination: "refuses_without_discriminating"`. |
| `blocked` | The hook was examined but no verdict could be reached: no negative-control `command`, `shlex.split()` could not tokenize either side, the hook declares no registered `entry` at all (decided before either subprocess runs — no ground truth to demonstrate through), the pair cannot discriminate (`discrimination: "pair_cannot_discriminate"`), or a subprocess raised `TimeoutExpired`/`OSError`. |
| `unverified` | The hook was **not examined** this run (excluded via `--check-id`, or the sweep never reached it) **and** it had no pre-existing `currently` block. The honest placeholder for "the attempt has never been made." |

A hook excluded this run that **already** carries a `currently` block is left
byte-identical — this runner never overwrites a state it did not itself
observe, and never derives a state from either declaration's text.

---

## `demonstration` — entry-point use vs. a reach-inside refusal

GE-120f-1-i extends this runner's per-check record with a `demonstration`
field. `config/verification_flow.schema.json`'s `currently` schema is
`additionalProperties: false` with a fixed four-value `state` enum — no
fifth value was added there. `demonstration` lives **outside** that block:
only on the runner's own per-check record dict and on the
`NEGATIVE_CONTROL_RESULT` stdout line.

| Value | Constant | Meaning |
|---|---|---|
| `entry_point` | `DEMONSTRATION_ENTRY_POINT` | The performed invocation's target script identity matched the hook's declared `entry`. |
| `reach_inside` | `DEMONSTRATION_REACH_INSIDE` | The performed invocation's target script identity did not match the hook's declared `entry` — the command reached the check by some route other than the one the protected surface uses. |
| `n/a` | `DEMONSTRATION_NA` | No completed invocation exists to classify. `blocked` and `unverified` records always carry `demonstration: "n/a"` — including a hook that declares no `entry` at all, forced `blocked`/`n/a` before either subprocess runs (see below; pr-reviewer H-1, fb_2026-09-25_79587943). |

Ground truth for "the entry point the protected surface invokes" is the
hook's registered `entry` field (`hook["entry"]`) — **never**
`hook["entry_point"]`, human prose on the real registration surface today.
The *stated* entry point in the report is the literal `tokens` list
actually passed to `subprocess.run` for the negative-control command, never
declared text echoed back. Both identities are resolved by
`_target_identity()` (skips a leading interpreter token, then a
`run_hook.py <target> ...` wrapper token) and compared for equality — a
match classifies `entry_point`, a mismatch classifies `reach_inside`. A
hook that declares no `entry` field at all is never classified either way:
`_examine()` checks `entry` before calling the classifier at all, and
before either subprocess runs, routing through
`_negative_control_pairing.no_entry_disposition()` instead — this
unconditionally forces `state: "blocked"` and `demonstration: "n/a"`, with
a schema-valid evidence item naming "no registered entry point to
demonstrate through" as the reason. `discrimination` for that record is
decided from the declared pair alone (no subprocess either side):
`pair_cannot_discriminate` when the pair is also non-discriminating on its
own declaration, otherwise `n/a` — a pair that would genuinely discriminate
cannot be credited for that when there is nothing to demonstrate it
through. This replaces a prior fail-open default (withdrawn) that
classified a no-`entry` hook `entry_point` — silently certifying a
demonstration with no ground truth to support it (pr-reviewer H-1,
fb_2026-09-25_79587943).

A `reach_inside` classification means the check's deciding logic works — a
rejection was demonstrably produced — but the check's service path does not
reach that logic the way the protected surface actually invokes it. Its
remedy differs from either `passing` or an entry-point `failing`: fixing
decision logic is not what is needed; wiring the service path to reach it
is. `templates/hooks/readme_read_guard.py` is the worked example.

---

## `discrimination` — three distinct wordings, three distinct remedies

GE-120f-1-ii extends the per-check record with a `discrimination` field, a
sibling of `demonstration` — living OUTSIDE the schema-shaped `currently`
block for the same reason `demonstration` does (architect-review's binding
design, `fb_2026-09-25_33c1543f` amended by `fb_2026-09-25_83f0382e`). It
composes both invocations' outcomes into a wording a reader can act on
without opening the check.

| Value | Constant | Meaning |
|---|---|---|
| `discriminates` | `DISCRIMINATION_DISCRIMINATES` | The negative-control command was rejected through the entry point AND the acceptable-input command was accepted. The only value under which `state` reads `passing`. |
| `refuses_without_discriminating` | `DISCRIMINATION_REFUSES_WITHOUT` | Both declared inputs were rejected. A refusal that never stops firing — the check has been widened until it rejects everything, as inert as rejecting nothing. `state` reads `failing`. |
| `pair_cannot_discriminate` | `DISCRIMINATION_CANNOT` | The pair's declaration cannot discriminate: the acceptable-input `command` is missing/empty, fails to tokenize, or tokenizes to the identical argv as `negative_control.command`. Detected BEFORE either subprocess runs — no invocation is made for either side this examination. `state` reads `blocked`. This is a FINDING, not a malformed-input error: it is reported and the sweep continues to the remaining hooks, never aborting. Also produced for a hook with no registered `entry` at all whose declared pair is ALSO non-discriminating on its own declaration — `no_entry_disposition()` evaluates the pair's own disposition regardless of the missing `entry`. |
| `n/a` | `DISCRIMINATION_NA` | Every record this pairing logic does not classify: the existing "declared rejection not observed" `failing` case (the negative-control command was not rejected at all — unaffected by the acceptable side), a genuinely-discriminating pair observed only `reach_inside`, a hook with no registered `entry` at all whose declared pair would otherwise discriminate (decided from the declaration alone — nothing to demonstrate it through), and every `unverified` or transport-failure `blocked` record. |

### The three findings and their opposite remedies

A negative-control sweep can report one of three distinct failures, each
in its own wording, because each needs a different repair:

| Finding | `state` / `discrimination` | What it means | Remedy |
|---|---|---|---|
| Refusal never fires | `failing` / `n/a` (declared rejection not observed) | The known-bad input was NOT rejected. | **Widen** the check so it actually rejects its declared bad input. |
| Refusal never stops firing | `failing` / `refuses_without_discriminating` | BOTH declared inputs were rejected — the check accepts nothing. | **Narrow** the check so it stops rejecting the acceptable input — the opposite direction from widening. |
| Declaration itself is broken | `blocked` / `pair_cannot_discriminate` | The two declared inputs are the same, differ in no way the check can act on, or the acceptable side was never declared. | **Fix the declared pair** — neither narrowing nor widening the check helps. |

One shared message across these three would let an implementer discharge
two findings with a single repair that makes the other worse — this is why
each keeps its own wording.

---

## Stdout contract

Exactly one line per hook that carries a (non-`not_applicable`)
`negative_control`, examined or not:

```
NEGATIVE_CONTROL_RESULT check_id=<id> state=<state> entry_point=<identity> demonstration=<value> discrimination=<value> command=<command>
```

`discrimination=` is inserted immediately after `demonstration=`, both
before the pre-existing greedy `command=`-to-end-of-line capture used by
the sole downstream parser — never swallowed into it. `entry_point=` is
never blank — a record with no resolvable invocation identity uses the
placeholder token `(unavailable)` (`_NO_IDENTITY`) rather than an
empty string.

From this line alone, without opening the check, a reader recovers: which
check ran (`check_id`), its verdict (`state`), the script identity actually
invoked (`entry_point`), whether that invocation came through the entry
point or by reaching inside (`demonstration`), which of the three findings
above applies, if any (`discrimination`), and the exact negative-control
command run (`command`).

Never two lines for one id; never a line for a hook with no
`negative_control` key at all.

---

## See Also

- [Commit Guardian Negative-Control Liveness](commit-guardian-negative-control-liveness.md) —
  CLI usage, `hooks_manifest` registration, and the "Declaring a check"
  walkthrough.
- `config/verification_flow.schema.json` — canonical `$defs/negative_control`
  and `$defs/currently` shapes this doc points at rather than duplicates.
- `templates/scripts/commit_guardian/check_negative_control_liveness.py`
  and `templates/scripts/commit_guardian/_negative_control_pairing.py` —
  the implementation.
