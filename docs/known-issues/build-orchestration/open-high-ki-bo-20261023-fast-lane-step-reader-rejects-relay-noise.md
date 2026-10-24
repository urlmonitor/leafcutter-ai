---
title: "KI-BO-20261023-fast-lane-step-reader-rejects-relay-noise — the fast lane reads every command step's answer with a whole-text JSON.parse, so a correct answer relayed with one log line or an 'exit: N' line around it halts the lane"
description: "high — fast-lane-ship.js's wvStep reads a command step's answer with JSON.parse(reply.stdout). Its executor is an agent whose shell tool returns stdout and stderr merged, and wrong_version_writer.py logs 'base ref HEAD: N names declared, M derived' to stderr on every list call that derives names. So on any AC with derived wrong-version names, the list answer is read as null and the lane halts fail-closed. The same defect halted three of three tickets on /build-feature on 2026-10-23; TQ-500f-3-v fixed build-feature.js, build-ticket.js and build-epic.js, and left the fast lane out of scope because it is owned elsewhere."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-v.yaml
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow.md
---

# KI-BO-20261023-fast-lane-step-reader-rejects-relay-noise — the fast lane's step reader rejects relay noise

> Filed 2026-10-23. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. Nothing is wrongly committed, because the reader fails closed. But on any AC
  whose wrong-version names are derived, the lane halts at the list step every time, after the
  test-writer and coder have already done their work.
- **Status:** open, no AC of its own. TQ-500f-3-v fixed the same reader in the three heavy-lane
  routes and named the fast lane out of scope, because the fast lane is owned elsewhere.
- **Occurrences:** 0 live in the fast lane. Found 2026-10-23 by reading the code while fixing
  the identical defect, which halted three of three tickets live on `/build-feature` (run
  `wf_f982c0ab-e94`, ~4.2M tokens of correct work).
- **First seen:** 2026-10-23 · **Last seen:** 2026-10-23
- **Where:** `templates/workflows-js/fast-lane-ship.js`, `wvStep`, `const out = JSON.parse(reply.stdout);`
  (:1778 at `fee64bd1d`). It serves the recover, list and finish steps.

## Symptom

`Wrong-version list step did not pass: null`, with the runner's relayed `stdout` reading:

```
base ref HEAD: 0 names declared, 14 derived
{"owed": [...], "error": null}
```

## Mechanism

1. `wrong_version_writer.py` (`_wvw_list.py:75`) logs its base-ref line through `logging`, to
   **stderr**. The script is right to do so.
2. The step runs through `command-step-runner`, an agent. Its shell tool returns stdout and stderr
   merged, so the log line arrives inside what the agent relays as `stdout`.
3. `JSON.parse` of the whole text throws, `wvStep` returns `null`, and the list step halts.

The same mechanism, through an appended `exit: 0` line, rejected a **passed** red-baseline gate on
`/build-feature`.

## Workaround

None inside the fast lane. `/build-feature` reads these replies correctly since TQ-500f-3-v.

## Suggested fix

Port TQ-500f-3-v's `parseStepJson` to `fast-lane-ship.js` and call it in `wvStep`. The rule: the
whole trimmed text if it is one JSON object; otherwise the one distinct line that is a JSON
object; anything else is `null`, so the caller still fails closed. Port the paired tests in
`unit_tests/workflows/test_step_json_relay_noise.py`, which assert both the noisy answer being read
and the no-answer cases N1-N6 still halting. `fast-lane-ship.js` is over the file-size ratchet
(`KI-BO-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow`), so the fix needs an equal
shrink in the same commit, or the owner's skip.

**Pattern:** a step reader that assumes the relayed text is exactly the command's stdout, when the
relay is an agent's shell tool that merges streams.
