---
title: "Reference: Commit Guardian Negative-Control Liveness"
description: "CLI contract, hooks_manifest registration, and declaration walkthrough for check_negative_control_liveness.py — the sweep that puts a hook's declared negative_control.command AND, as of GE-120f-1-ii, its own declared acceptable-input command through a real subprocess in the same run. Field-by-field record shapes live in the companion reference doc."
type: reference
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - commit_guardian
related_docs:
  - docs/reference/commit-guardian-negative-control-liveness-record.md
  - config/verification_flow.schema.json
  - docs/architecture/components/commit-guardian.md
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1-ii.yaml
  - docs/known-issues/commit-guardian.md
---

# Commit Guardian Negative-Control Liveness

CLI contract, `hooks_manifest` registration, and declaration walkthrough for
`check_negative_control_liveness.py` — the runner that puts each hook's
declared negative-control input, and (as of GE-120f-1-ii) its own declared
acceptable input, through a real subprocess rather than trusting either
one's text. Field-by-field shapes for `negative_control`, the
acceptable-input pair, `currently`, `demonstration`, and `discrimination` —
plus the full stdout-line grammar — live in the companion
[record-fields reference](commit-guardian-negative-control-liveness-record.md).

---

## Why a `negative_control` exists

`config/verification_flow.schema.json` `$defs/negative_control` states the
rule this whole mechanism enforces: "The known-bad input that MUST be
rejected. A check without one can pass on dead code." A hook can be
well-formed, registered, and green while quietly refusing nothing — the
`negative_control` is the artifact that lets a later run prove the check
still refuses its own declared bad input, rather than asserting it once and
never asking again.

---

## Both declared inputs, one entry point, one run

A hook may declare, beside `negative_control` (the known-bad input it must
reject), two further top-level keys as **siblings** of `negative_control` in
the SAME entry — never a second declaration store: `command` (the input the
check is required to *accept*) and `pass_criteria`. Both commands are put
through the SAME entry point, in the SAME run, for every examined hook that
declares both — see the companion doc's [Acceptable
input](commit-guardian-negative-control-liveness-record.md#acceptable-input--hook-level-command--pass_criteria)
and [`discrimination`](commit-guardian-negative-control-liveness-record.md#discrimination--three-distinct-wordings-three-distinct-remedies)
sections for the full field shapes and the state/discrimination mapping.

A pair whose acceptable-input `command` is missing, empty, or tokenizes to
the identical argv as `negative_control.command` cannot discriminate at
all. That check runs **before** either subprocess, is reported as a
finding (never raised as an error), and the sweep **continues** to the
remaining hooks — an examined hook is never left unexamined because a
sibling hook's declaration was broken. `not_applicable` hooks are skipped
entirely, exactly as before GE-120f-1-ii — the pairing logic never runs for
them.

---

## CLI reference

### Entry points

| Invocation | Behaviour |
|---|---|
| `--selftest` | Prints `NEGATIVE_CONTROL_LIVENESS_SELFTEST_OK` and exits `0`. Touches no file — proves the deployed module and everything it imports load in a cold process. |
| `--manifest PATH [--check-id ID ...]` | Loads `PATH` as a `commit_guardian.json`-shaped manifest, sweeps `hooks_manifest.hooks[]`, examines every hook carrying a falsifiable `negative_control` (or only the `--check-id`-named ones), and writes the mutated manifest back to `PATH`. |

### Arguments

| Argument | Repeatable | Description |
|---|---|---|
| `--manifest` | no | Path to the manifest to sweep and rewrite in place. |
| `--check-id` | yes | Restrict examination to these hook ids. All other `negative_control`-carrying hooks are left unexamined. |
| `--selftest` | no | Cold-load probe; mutually exclusive in practice with `--manifest`. |

Exactly one `NEGATIVE_CONTROL_RESULT` stdout line per examined-or-not
`negative_control`-carrying hook — see the companion doc's [Stdout
contract](commit-guardian-negative-control-liveness-record.md#stdout-contract)
for the full line grammar, now including `discrimination=`.

### Exit-code contract

| Condition | Exit code |
|---|---|
| Every hook **examined** this run ended `passing` (including zero hooks examined) | `0` |
| At least one examined hook ended `failing` or `blocked` | non-zero (`1`) |
| `--manifest` missing, unreadable, not valid JSON, or lacking `hooks_manifest.hooks` | `2` |
| `--selftest` | always `0` |

Unexamined hooks never affect the exit code, regardless of what state they
hold. A `pair_cannot_discriminate` finding fails the run the same way any
other `blocked` record does — it is a finding, not an early abort.

---

## `hooks_manifest` registration

One entry was appended to
`templates/scripts/commit_guardian/commit_guardian.json`
`hooks_manifest.hooks[]` (72 → 73 entries; pure append, no existing entry
touched).

| Field | Value |
|---|---|
| `id` | `check-negative-control-liveness` |
| `entry` | `run_hook.py`-wrapped invocation of this script with `--manifest` pointed at the deployed copy of the same manifest file. |
| `always_run` | `true` — the sweep reads the whole manifest's declared population, never the staged-file list. |
| `pass_filenames` | `false` — same rationale as `check-build-drift`'s existing entry in this manifest. |
| `negative_control` | `{"not_applicable": true, "reason": "..."}` — this entry is the census/liveness runner itself; it has no known-bad staged-file input of its own to reject. |

Registering this entry is what makes the sweep reachable from a real commit
— a runner nothing calls is inert (see Known Issues cross-link below).

---

## Current coverage (day one)

Neither GE-120f-1's original sweep nor this doc's `demonstration`
(GE-120f-1-i) and `discrimination` (GE-120f-1-ii) extensions add
`negative_control` or acceptable-input declarations to any of the 72
pre-existing `hooks_manifest.hooks[]` entries. Populating those
declarations is out of scope for this doc's coverage and is deferred to
child tickets **GE-120f-4** and **GE-120f-4-i** — see [Declaring a
check](#declaring-a-check) below for the shape they will produce.

As a result, a real sweep over this repository's actual manifest today
examines **zero** pre-existing hooks — only the runner's own
`not_applicable` entry exists, and the sweep skips `not_applicable` entries
by design. Most hooks are simply **not yet represented** in this mechanism,
which is a different state from `unverified` — `unverified` is reserved for
a hook that *declares* a `negative_control` but was not put through it this
run.

---

## Declaring a check

A complete `hooks_manifest.hooks[]` entry carrying both sides of the pair
this doc's [Both declared inputs](#both-declared-inputs-one-entry-point-one-run)
section describes:

```json
{
  "id": "check-example",
  "entry": "python .leafcutter/scripts/commit_guardian/check_example.py",
  "negative_control": {
    "input": "a staged file containing the pattern this check must reject",
    "command": "python .leafcutter/scripts/commit_guardian/check_example.py --manifest fixtures/bad_case.json",
    "expected_result": "non-zero exit"
  },
  "command": "python .leafcutter/scripts/commit_guardian/check_example.py --manifest fixtures/good_case.json",
  "pass_criteria": "zero exit"
}
```

`negative_control.command` (the known-bad input) and the hook-level
`command` (the acceptable input) are siblings in the SAME entry — never two
records. `entry` is unrelated to either: it is the ground truth
`demonstration` compares each performed invocation's target identity
against (see the companion doc). GE-120f-4 and GE-120f-4-i populate this
shape onto the repository's real hooks; this ticket implements and
documents only the runner that reads it.

---

## See Also

- [Commit Guardian Negative-Control — Record Fields](commit-guardian-negative-control-liveness-record.md) —
  field-by-field shapes for `negative_control`, the acceptable-input pair,
  `currently`, `demonstration`, `discrimination`, and the stdout-line
  grammar.
- [Commit Guardian](../architecture/components/commit-guardian.md) — the
  pre-commit hook system this sweep is one gate within.
- `config/verification_flow.schema.json` — canonical `$defs/negative_control`
  and `$defs/currently` shapes this doc points at rather than duplicates.
- `docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1.yaml` —
  the parent AC this runner implements.
- `docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1-ii.yaml` —
  the acceptable-input pairing this doc's `discrimination` field satisfies.
- [Known Issues — Commit Guardian](../known-issues/commit-guardian.md) —
  KI-CG-021, the "a runner nothing calls is inert" precedent this
  `hooks_manifest` registration exists to avoid repeating.
- `templates/scripts/commit_guardian/check_negative_control_liveness.py`
  and `templates/scripts/commit_guardian/_negative_control_pairing.py` —
  the implementation.
- `templates/scripts/commit_guardian/commit_guardian.json` — the manifest
  carrying the `check-negative-control-liveness` registration.
- `templates/hooks/readme_read_guard.py` — the worked example for a
  `reach_inside` finding: deciding logic that is correct but whose real
  service path does not reach it with the same input shape.
