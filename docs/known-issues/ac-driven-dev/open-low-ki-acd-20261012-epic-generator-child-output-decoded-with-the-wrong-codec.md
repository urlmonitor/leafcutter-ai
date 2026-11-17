---
title: "KI-ACD-20261012-epic-generator-child-output-decoded-with-the-wrong-codec — on Windows goal_to_epic decodes each generator subprocess's output as UTF-8 while the child writes cp1252, so the generator's stderr is lost and a non-ASCII character on its stdout would stop the run"
description: "medium — _call_generate_ticket_from_ac() runs generate_ticket_from_ac.py with text=True, encoding='utf-8', but the child writes its pipes in the locale codec, cp1252 on a default Windows install. An em-dash (0x97) in a warning raises UnicodeDecodeError in subprocess's reader thread and nulls that stream. Observed 2026-10-12 during a 48-ticket --ids run. Even when decoding works, the generator's stderr is never shown."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260927-subprocess-text-decode-uses-locale-codec-repo-wide.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-017.md
---

# KI-ACD-20261012-epic-generator-child-output-decoded-with-the-wrong-codec — on Windows goal_to_epic decodes each generator subprocess's output as UTF-8 while the child writes cp1252, so the generator's stderr is lost and a non-ASCII character on its stdout would stop the run

- **Severity:** medium. What was observed is noise plus lost diagnostics: a reader-thread
  traceback in the run's output, and that ticket's stderr gone. The crash described under
  "Latent" below was reproduced in isolation and has not been seen in a real run. Windows only.
- **Status:** open, no AC.
- **Occurrences:** 1 (2026-10-12, `goal_to_epic.py --ids` with 48 ids, scaffolding
  `EPIC-RightJobRightAgent`, PR #1145). The run printed
  `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97` from a subprocess reader thread.
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:** `scripts/ac_store/epic_tickets.py` `_call_generate_ticket_from_ac()` (`:118-180`):
  the `subprocess.run(..., capture_output=True, text=True, encoding="utf-8", check=True)` call
  (`:144-168`), the stdout parse (`:174-176`) and the `except` clause (`:169`). Also
  `scripts/ac_store/epic_cli.py` `_run_ids_mode()`, whose `except` clauses are at `:162-170`.
  Verified on origin/main `a104d934`.

## Mechanism

1. The child, `generate_ticket_from_ac.py`, writes to its pipes in the locale codec. On a
   default Windows install that is cp1252. On the observing machine
   `locale.getpreferredencoding(False)` returned `cp1252` and `sys.flags.utf8_mode` was 0 under
   Python 3.14.2, with `PYTHONUTF8` and `PYTHONIOENCODING` unset. Nothing in the generator or in
   `epic_*.py` reconfigures the streams (no `reconfigure`, no environment override).
2. The parent decodes both pipes as UTF-8. The generator's messages use em-dashes, and `—` is
   byte `0x97` in cp1252, which is not a valid UTF-8 start byte.
3. On Windows, `subprocess` reads each pipe on its own thread (`_readerthread`). The decode error
   is raised in that thread and printed as `Exception in thread ...`. That stream's result
   becomes `None`. The child still exits 0, so `check=True` passes and the run continues.

Reproduced in isolation on the same machine. A child that prints `Written: tickets/x.md` to
stdout and a warning containing `—` to stderr gave return code 0, stdout intact, `stderr: None`,
and the same `0x97` traceback.

## Consequences

- **Observed.** A traceback in the middle of the run, and the loss of that ticket's stderr.
- **By design, regardless of codec.** On success `_call_generate_ticket_from_ac()` never reads
  `result.stderr`. It returns the path from the `Written:` line and discards everything else, so
  no generator warning reaches the person running `goal_to_epic`, whether or not decoding
  succeeds.
- **Latent: a crash.** The same mechanism applies to stdout. A non-ASCII character in the
  absolute ticket path on the `Written:` line, such as an accented letter in a directory name,
  leaves `result.stdout` as `None`. Then `result.stdout.splitlines()` (`:174`) raises
  `AttributeError`. `_call_generate_ticket_from_ac()` catches only `SubprocessError`/`OSError`,
  and `_run_ids_mode()` catches only `ZeroLeafError`, `CyclicDependencyError`,
  `CalledProcessError`, `OSError` and `RuntimeError`, so neither handles it. The run would stop
  with a traceback after the earlier tickets were already written into the inbox, and before the
  repoint and loose-ticket cleanup ran. Reproduced in isolation (`stdout: None`, then
  `AttributeError`). Not observed in a real run.

This is the inverse of `KI-CG-20260927-subprocess-text-decode-uses-locale-codec-repo-wide`. There
the parent decodes UTF-8 child output with the locale codec. Here the parent forces UTF-8 on a
child that writes the locale codec. The KI-CG sweep counts calls with no `encoding=`, so it does
not find this site.

## Workaround

Set `PYTHONUTF8=1` (or `PYTHONIOENCODING=utf-8`) in the environment before running
`goal_to_epic.py` on Windows. The generator subprocess inherits it. Checked with the isolated
reproduction above: under `PYTHONUTF8=1` both streams came back intact, em-dash included.

## Fix direction

- Make the child's codec explicit. Pass `env={**os.environ, "PYTHONIOENCODING": "utf-8"}` (or
  run it with `-X utf8`). Decode with `errors="replace"` so that one stray byte cannot null a
  stream.
- Surface the child's stderr, at least its WARNING lines, prefixed with the AC id, on success as
  well as on failure.
- The `KI-ACD-017` fix direction, calling the generator in-process against one shared store
  index, removes the pipe altogether and would close this as a side effect.
- Regression test: a child that writes `—` in cp1252 to both streams. Assert that no reader-thread
  exception is raised, that stderr is preserved, and that the `Written:` path is still parsed.

**Related.** `KI-BP-20260910-1240` (the same run's other Windows default: CRLF writes, recorded
there as Occurrence 7). `KI-ACD-017` (the same subprocess boundary is why the run is slow).

**Pattern:** a pipe whose two ends each chose an encoding, and chose differently.
