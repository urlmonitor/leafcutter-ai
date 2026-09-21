---
title: "Reference: Negative-Control Liveness States"
description: "Field shapes for a commit-guardian hook's negative_control declaration, the four currently.state values a liveness sweep can record, and the decision table a report reader uses to tell a genuine rejection from a launch failure."
type: reference
status: active
created: 2026-09-21
last_updated: 2026-09-21
components:
  - commit_guardian
related_docs:
  - docs/architecture/adrs/ADR-045-observed-refusal-establishes-protection.md
  - docs/testing/test-angles.verification.flow.json
  - docs/architecture/components/commit-guardian.md
related_code:
  - config/verification_flow.schema.json
  - templates/scripts/commit_guardian/check_negative_controls.py
  - templates/scripts/commit_guardian/commit_guardian.json
---

# Negative-Control Liveness States

Field-level lookup for the `negative_control` declaration a commit-guardian hook
registers, the runner that executes it, and the four `currently.state` values a
liveness sweep can record for a check.

---

## The `negative_control` Declaration

Every registered `hooks_manifest.hooks[]` entry in
`templates/scripts/commit_guardian/commit_guardian.json` MAY carry a
`negative_control` block: one known-bad input and the observable rejection that
input must produce. Two shapes exist, defined in
`config/verification_flow.schema.json` (`$defs/negative_control`).

### Falsifiable form

| Field | Type | Required | Description |
|---|---|---|---|
| `input` | string | Yes | The known-bad artifact, record, or invocation fed through the same entry point the check's own `entry` field uses. |
| `command` | string | No | Single simple command that feeds `input` through the entry point. When absent, the runner builds one from `entry` and `input`. |
| `expected_result` | string | Yes | The observable rejection: non-zero exit, a specific error string, or absence from a generated artifact. |
| `currently` | object | Yes | The current observed state, written by the runner — see [`currently.state` Values](#currentlystate-values). Never hand-authored. |

### `not_applicable` form

| Field | Type | Required | Description |
|---|---|---|---|
| `not_applicable` | boolean (`true`) | Yes | Marks a check for which no known-bad input is meaningful. |
| `reason` | string | Yes | Why no known-bad input applies — e.g. the check is a pure census or measurement with no pass/fail semantics of its own. |

See [The `not_applicable` Alternative](#the-not_applicable-alternative) below for
when to choose this form over leaving `negative_control` absent.

---

## The Liveness Runner

`templates/scripts/commit_guardian/check_negative_controls.py` is the code reader
of `negative_control`. Per invocation it:

1. Reads `hooks_manifest.hooks` from the **deployed** `commit_guardian.json` beside
   itself — never a hard-coded list, never the source-tree `templates/` copy.
2. Restricts its population to entries that are **examinable**: `_is_examinable()`
   requires a real `id` and a real `entry` string.
3. For each examinable hook's declared `negative_control`, runs the declared
   `command` (or the `entry` + `input` fallback) as a real subprocess through the
   same `run_hook.py`-wrapped entry point the protected surface uses.
4. Derives the record **purely from what that subprocess did** — `_observe()`
   never reads the declaration's `expected_result` as its own answer. The
   PRIMARY discriminator is `run_hook.py`'s own structured
   `RESULT: not_run checker=<target> reason=<reason>` report (parsed by
   `_parse_not_run_reason()`): any `reason` present means `run_hook.py` itself
   decided never to launch the delegated check's own process, which is always
   `blocked`, regardless of the reason or the wrapper's own exit code. A
   substring-based marker list and an argparse-usage-error signature are
   consulted only as a conservative fallback when no structured report line is
   present — see [Decision Table](#decision-table-reading-a-negative-control-report).
5. Writes the derived state into `negative_control.currently` on the deployed
   manifest, in place.

The runner is itself a registered `hooks_manifest` entry (`check-negative-controls`)
and is not exempt from the regime it enforces (ADR-045 §6a): its own declared
known-bad input is the `--self-check-empty-population` flag, and its own observable
rejection is refusing to report a clean sweep over zero examined checks.

`main()` refuses to run when the manifest names zero examinable checks, exiting 1
rather than reporting a vacuous clean sweep — the same failure mode ADR-045 §7
guards against one level up.

---

## `currently.state` Values

Reuses `config/verification_flow.schema.json`'s `$defs/currently.state` enum
verbatim — no synonyms.

| State | Meaning | When It Is Written |
|---|---|---|
| `passing` | The declared rejection WAS observed. | `_observe()`: the declared command ran, its exit code was non-zero, and no launch-failure marker appeared in its output. |
| `failing` | The declared rejection was NOT observed. | `_observe()`: the declared command ran and exited zero — the check did not reject its own declared known-bad input. |
| `blocked` | The attempt could not be run to a verdict. | `_observe()`: either the declared `command` does not contain the declared `input` substring, or `run_hook.py` itself reported a structured not-run outcome (`reason=disabled`, `reason=could_not_start`, etc.), or the subprocess could not be launched at all, or a launch-failure marker / argparse-usage-error signature appears in its output. Three distinct causes — see below. |
| `unverified` | The attempt has never been made. | `_observe()`: the hook is disabled (`enabled: false`), or it has no falsifiable `negative_control` declared at all (missing, `not_applicable`, or missing `input`). Written, never omitted. |

`blocked` must never collapse into `failing` — a launch/reachability failure and a
genuine-but-failed observation are mechanically distinct causes, and conflating
them would misreport an unexamined check as an examined one.

`unverified` is the schema's own honest placeholder: it is written so "this check
was never fed bad input" is visible in the artifact instead of silent.

---

## The Three `blocked` Causes

| Cause | What it means | Why it cannot be `failing` / `passing` |
|---|---|---|
| (a) Declared `command` does not contain the declared `input` substring. | The run cannot establish the check actually saw its known-bad input at all. Several commit-guardian hooks ignore `argv` entirely and read the git index or `HOOK_TEST_FILES` instead. | A clean exit from a check handed nothing would otherwise be misread as a verdict on an input it never received (would otherwise read `failing`). |
| (b) `run_hook.py` itself reports a structured not-run outcome (`RESULT: not_run checker=<target> reason=<reason>` — e.g. `reason=disabled`, `reason=could_not_start`), or the subprocess could not be launched at all, or a launch-failure marker appears in its output (`could_not_start`, "no such file or directory", `ModuleNotFoundError`, a bare traceback). Two `hooks_manifest` entries can share a script basename (`run_hook.py`'s `_is_target_disabled()` matches by basename, not hook id), so disabling one silently short-circuits the OTHER entry's own negative control at `reason=disabled`, exit 0 — the check's own process never launches. | The command never ran to completion as the check under test — `run_hook.py` decided not to launch it, or it failed before/during process startup. | A launch failure or a not-run short-circuit that happens to exit 0 or non-zero is not a genuine observation either way; recording it as `failing` (a clean exit that never examined anything) or `passing` (a launch failure that happens to exit non-zero) would certify a check that was never actually exercised. |
| (c) The subprocess's own exit code and output match Python argparse's hard-coded parser-error footprint (exit code 2, BOTH a `usage: ` line AND an `error: unrecognized arguments` line). | An argparse-based check that treats the appended known-bad input as an unrecognised or malformed CLI token never reaches its own examination logic — `ArgumentParser.error()` rejects it structurally before the check's `main()` body runs. Requiring both markers (not `usage: ` alone) excludes `change_set_source.py`'s own non-argparse `"usage: change_set_source.py <manifest_path>"` exit-2 convention in this same directory. | A matching non-zero exit code alone is not evidence the check evaluated its declared input; recording it as `passing` would certify logic that was never actually exercised against the declared input (would otherwise read `passing`). |

---

## Decision Table: Reading a Negative-Control Report

| Condition | Resulting State |
|---|---|
| Hook disabled, or no falsifiable declaration | `unverified` |
| Declared command does not contain the declared input | `blocked` |
| `run_hook.py` reports `RESULT: not_run checker=... reason=...` (any reason — e.g. this hook disabled, a same-basename sibling disabled, target missing) | `blocked` |
| Subprocess could not be launched / launch-failure marker in output (fallback, no structured report present) | `blocked` |
| Exit code 2 with BOTH a `usage: ` line AND an `error: unrecognized arguments` line (argparse's own parser-error footprint) | `blocked` |
| Declared command runs, exits non-zero, none of the above | `passing` |
| Declared command runs, exits zero, none of the above | `failing` |

`_parse_not_run_reason()` — the structured-report check — runs BEFORE the
marker-list and argparse-signature fallbacks, and is the PRIMARY discriminator:
those fallbacks exist only for a launch failure that does not route through
`run_hook.py`'s own protocol at all.

---

## The `not_applicable` Alternative

Use `{not_applicable: true, reason: "..."}` in place of `input`/`expected_result`
only when the check has no pass/fail semantics of its own to falsify — e.g. a pure
census or measurement check that counts records rather than rejecting anything.
`reason` must name specifically why no known-bad input is meaningful for that
check; a check that COULD be handed a known-bad input but simply has not been
wired yet should instead omit `negative_control` entirely, which the runner
records as `unverified`.

---

## See Also

- [ADR-045: A Check Counts as Protection Only Once It Has Been Observed Refusing](../architecture/adrs/ADR-045-observed-refusal-establishes-protection.md) — the decision record for why this regime exists, the two-guard design, and the worked example of an inert guard.
- [Commit Guardian](../architecture/components/commit-guardian.md) — the component doc for the pre-commit hook system this regime protects.
- `docs/testing/test-angles.verification.flow.json` — a worked-example `*.verification.flow.json` instance using the same `negative_control` and `currently` vocabulary at the check-angle level.
- `config/verification_flow.schema.json` — the schema source of truth for `negative_control` and `currently`; consult it directly rather than this doc for the full JSON Schema.
- `templates/scripts/commit_guardian/check_negative_controls.py` — the runner implementation this doc must stay synchronized against, particularly `_observe()`.
- `templates/scripts/commit_guardian/commit_guardian.json` — the deployed manifest holding every hook's `negative_control` declaration.
