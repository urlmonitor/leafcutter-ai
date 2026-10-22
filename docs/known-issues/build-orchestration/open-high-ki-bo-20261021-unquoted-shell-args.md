---
title: "KI-BO-20261021-unquoted-shell-args — the fast lane's wrong-version, claim and other commands, and the red-baseline gate in /build-feature and build-ticket.js, build shell lines by pasting paths and ids in unquoted, so a path with a space breaks the step and an id with shell metacharacters runs extra commands"
description: "high — fast-lane-ship.js on main builds the wrong-version recover, list and finish commands (TQ-500g-1-v, #1280) as template strings with the worktree path, AC-store path, AC ids and the work key pasted in bare, and hands them to command-step-runner, which runs a command exactly as given. The claim command is built the same way and goes to the same runner. The red-baseline gate in build-feature.js and build-ticket.js does the same, but relays its command through status-checker. A worktree, root or AC-store path that contains a space splits into two arguments, so the step fails to parse and the lane halts fail-closed. A consumer repo under a 'Bybit-Trader Live' folder hits this on every drive. An AC id or work key that carries ';', '$(...)' or backticks becomes a second command. PR #1299 (TQ-500g-1-vi, open) already fixed this pattern in its new wrong-version blocks in build-feature.js and build-ticket.js, but it did not fix these sites."
type: reference
category: reference
status: active
created: '2026-10-21'
last_updated: '2026-10-21'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md
---

# KI-BO-20261021-unquoted-shell-args — workflow shell lines paste paths and ids in unquoted

> Filed 2026-10-21. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. Nothing is wrongly committed: every site parses its reply fail-closed, so a
  broken command halts the lane. But two things are wrong. First, a project whose path contains a
  space cannot complete **any** fast-lane drive. Second, any AC id or work key that reaches these
  lines is pasted into a shell command, so a value with shell metacharacters runs a command the
  workflow never wrote. That is an injection surface in the package's own build path.
- **Status:** open, no AC. Not fixed here, by instruction.
- **Occurrences:** 1. Found by reading the code on 2026-10-21, during the review of PR #1299. That
  PR fixed this pattern in its own new code. This entry was not reproduced by a live drive.
- **First seen:** 2026-10-21 · **Last seen:** 2026-10-21
- **Where** (line numbers at `origin/main` `fd93f92c6`):
  - `templates/workflows-js/fast-lane-ship.js`, the wrong-version block from TQ-500g-1-v (#1280,
    `1c312fd90`). All three commands go to `command-step-runner` through `wvStep` (:1951-1958).
    - :1948-1950 build the shared pieces: ``wvDir = `${worktreePath}/...` ``,
      ``wvIds = `--ac-ids ${batchIdsCsv} ` ``, and
      ``wvFlags = `--ac-root ${acStoreRoot} --test-root ${worktreePath} --base-ref HEAD` ``.
    - :1971 — ``python ${wvDir}/wrong_version_runner.py recover``
    - :1976 — ``python ${wvDir}/wrong_version_writer.py list ${wvIds}${wvFlags}``
    - :1989-1991 — ``python ${wvDir}/wrong_version_gate.py finish --work-key ${targetAc} --reply - ${wvIds}${wvFlags} <<'${wvDelim}'``
  - `templates/workflows-js/fast-lane-ship.js`, the same pattern outside that block:
    - :1233-1234 — `claimInvocation`, ``python ${gateScript} claim --ac-ids ${batchIdsCsv} --ac-root ${acStoreRoot}``.
      It goes to the same `command-step-runner` (:1232, :1295) and runs **before** the
      wrong-version step.
    - :1007-1009 (`select_connected --ac ${targetAc} --ac-root ${acStoreRoot}`, relayed through
      `status-checker`) and :1375-1376 (`release`, relayed through `python-coder`). Both are
      prose relays, so an agent may quote the paths itself, but nothing makes it do so.
  - `templates/workflows-js/build-feature.js`:2117-2121, the red-baseline gate (TQ-500f-3-ii).
    ``python ${gateScript} heavy_lane_gate --source-ac ${sourceAcIds.join(",")} --test-root ${resolvedTarget.worktree_path} --ac-root ${gateAcStoreRoot} --ticket ${worktreeTicketPath}``.
    It is relayed as prose through `status-checker` (:2122-2126). On the PR #1299 branch the same
    lines sit at :2173-2177, and #1299 leaves them unchanged.
  - `templates/workflows-js/build-ticket.js`:1703-1707, the twin of that gate, with `${ticketPath}`
    in place of `${worktreeTicketPath}`.
  - `targetAc` is the caller's `ac` argument after only `.trim()`
    (`fast-lane-ship.js`:794). The slug on :796 is sanitised. The id is not.

## Symptom

On a path with a space, for example a worktree under `.../Bybit-Trader Live/...`, the runner
receives something like:

```
python C:/.../Bybit-Trader Live/worktrees/<slug>/.leafcutter/scripts/build_orchestration/wrong_version_writer.py list --ac-ids X-1 --ac-root C:/.../Bybit-Trader Live/... --test-root ...
```

The shell splits that into `python C:/.../Bybit-Trader` plus stray arguments. Python cannot open the
script, stdout is not JSON, `wvStep` returns `null`, and `wvHalt` releases the claims and returns
`status: blocked` with `failing_phase: wrong-version`. The claim step at :1233-1234 has the same
shape and runs earlier on the same runner, so on such a path the lane may stop at claim before it
reaches the wrong-version step.

## Mechanism

1. **Commands are template strings.** Each site joins `python`, a script path, and its arguments
   with `${...}` and spaces. No value is quoted and none is checked first.
2. **The runner runs the string as given.** `command-step-runner` "runs exactly one given command,
   once". That is right for its role, but it means the workflow string *is* the shell line. The
   status-checker relays at the gate sites give no better guarantee: whether a path gets quoted
   depends on the relaying agent.
3. **The values are not plain tokens.** `worktreePath` and `acStoreRoot` come from the project's
   real location on disk, which the package does not control. `targetAc` is the caller's raw
   argument. `batchIdsCsv`, `sourceAcIds` and the ticket path are read back from the store or from
   an agent reply.

## Detection

- Static: `grep -nE 'python \$\{(wvDir|gateScript)\}' templates/workflows-js/*.js` and look for a
  `${...}` that is not inside `"..."`.
- Live: drive `/fast-lane-build` in a repo whose path contains a space. The run ends `blocked`
  at the claim or wrong-version step, and the runner's stderr names a truncated path.

## Workaround

Keep the repo, its worktree base and the AC store on a path with no spaces. Only pass AC ids made
of letters, digits, `.`, `_` and `-`.

## Suggested fix

Apply the PR #1299 (TQ-500g-1-vi) pattern to every site above:

- Double-quote every interpolated path and value: `python "${root}"/.../script.py`,
  `--ac-root "${acStoreRoot}"`, `--work-key "${targetAc}"`.
- Before building any command, check each id and the work key against `^[A-Za-z0-9._-]+$`, and
  refuse a root that contains `"`, `$`, a backtick or a newline. On a failed check, halt before any
  command runs. This is #1299's `wvBad` and its `input-check` halt.
- Port #1299's regression tests in `unit_tests/workflows/test_tq500g1vi_review.py`
  (`test_paths_with_a_space_reach_the_real_wrapper_intact`,
  `test_hostile_source_ac_id_or_work_key_halts_with_no_command`) to the fast lane and to both gate
  sites.
- **Size ratchet:** `fast-lane-ship.js` is already over the file-size ratchet
  (`KI-BO-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow`). A fix that adds lines there
  needs the user's `check-file-size` skip, or an equal shrink in the same commit.

**Related.** `KI-BO-20260927-status-checker-runs-workflow-shell-commands` covers the gate sites'
other defect: they relay shell commands through `status-checker`.
`KI-BO-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow` covers the ratchet that blocks
the fix.

**Pattern:** a command line built by joining strings, with values from outside the code pasted in
unquoted, and run by an executor that is correctly literal.
