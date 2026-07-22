"""
MODULE: test_bo_1000c_1a
GOAL: Verify that finalize-feature.js appends each progress line (start-of-step
    and per-step-outcome) to a durable, pollable run-progress journal at the
    moment it is emitted — append-as-you-go, not flushed only once at the
    end of the run (AC BO-1000c-1a).

    These tests parse finalize-feature.js as text, following the pattern
    established in test_bo_1000a_1.py and test_bo_1000b_1.py. Because the
    implementation does not yet exist, all tests below are EXPECTED TO FAIL
    (red) until python-coder implements the journal-append mechanism.

TICKET: 12_TICKET-20260720-BO-1000c-1a.md
AC: BO-1000c-1a
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _extract_function_body(js: str, func_name: str) -> str:
    """Extract the body of a named function definition (from { to matching }).

    Handles nested braces and string literals so inner closing braces
    don't confuse the depth counter.

    Returns the body string (including the outer braces) or an empty string
    when the function is not found.
    """
    pattern = re.compile(rf'\bfunction\s+{re.escape(func_name)}\s*\(')
    match = pattern.search(js)
    if not match:
        return ""
    # Advance to the opening brace of the function body.
    i = match.end()
    while i < len(js) and js[i] != '{':
        if js[i] == ')' and i > match.end():
            pass  # still in parameter list
        i += 1
    if i >= len(js):
        return ""
    depth = 0
    start = i
    in_string = False
    string_char: str = ""
    while i < len(js):
        ch = js[i]
        if in_string:
            if ch == "\\" and i + 1 < len(js):
                i += 2
                continue
            if ch == string_char:
                in_string = False
        else:
            if ch in ('"', "'", "`"):
                in_string = True
                string_char = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return js[start : i + 1]
        i += 1
    return ""  # Unmatched brace — return empty


# ---------------------------------------------------------------------------
# Patterns for the journal-write mechanism.
# A "journal append" can be implemented via:
#   - a helper function like appendJournal() or writeProgressLine()
#   - a direct fs.appendFileSync() / fs.appendFile() call
#   - a shell-out that appends a line to a file
# The tests below accept any of these forms.
# ---------------------------------------------------------------------------

# Matches a journal-append helper *definition* or a direct appendFileSync call.
_JOURNAL_APPEND_DEFINITION = re.compile(
    r"function\s+appendJournal\s*\("
    r"|const\s+appendJournal\s*=\s*(?:async\s*)?\("
    r"|function\s+writeProgressLine\s*\("
    r"|const\s+writeProgressLine\s*=\s*(?:async\s*)?\("
    r"|function\s+journalAppend\s*\("
    r"|const\s+journalAppend\s*=\s*(?:async\s*)?\("
    r"|fs\.appendFileSync\s*\("   # direct Node.js call
    r"|appendFileSync\s*\("       # after destructure import
)

# Matches a call to a journal-append helper (any of the naming variants).
_JOURNAL_APPEND_CALL = re.compile(
    r"\bappendJournal\s*\("
    r"|\bwriteProgressLine\s*\("
    r"|\bjournalAppend\s*\("
    r"|\bfs\.appendFileSync\s*\("
    r"|\bappendFileSync\s*\("
)

# Matches evidence that the journal lives at a file path keyed to the run.
# The path must reference the worktree/run context so external callers can
# locate it deterministically.
_JOURNAL_PATH_DEFINITION = re.compile(
    r"\bjournalPath\b"
    r"|\bJOURNAL_PATH\b"
    r"|\bprogressJournalPath\b"
    r"|\brun_progress_path\b"
    r"|\brunProgressPath\b"
    r"|\bprogress_journal\b"
)

# Matches a reference to the worktree root / run ID inside the journal path
# construction — confirming the path is keyed to this specific run.
_PATH_KEYED_TO_RUN = re.compile(
    r"worktree_root|worktreeRoot|runId|run_id|epicArg"
    r"|preflightInfo"
    r"|run[-_]progress"
    r"|\.journal\.jsonl"
    r"|progress\.jsonl"
    r"|journal\.jsonl"
)

# Matches append-mode file writes (as opposed to overwrite-mode).
_APPEND_MODE_WRITE = re.compile(
    r"appendFileSync\s*\("   # inherently append-mode
    r"|appendFile\s*\("      # async variant (also inherently append)
    r"['\"]a['\"]"           # 'a' flag in fs.open / createWriteStream
)

# Anti-pattern: overwriting the journal with writeFileSync would destroy
# previously written entries, violating the emission-order contract.
_OVERWRITE_JOURNAL_ANTI_PATTERN = re.compile(
    r"writeFileSync\s*\(\s*journal"
    r"|writeFile\s*\(\s*journal"
)


# ---------------------------------------------------------------------------
# AC-1: That same line is appended, at the moment it is emitted, to a durable
#       run-progress record (BO-1000c-1a)
# ---------------------------------------------------------------------------

class TestProgressLineAppendedToJournalAtMomentItIsEmitted(unittest.TestCase):
    """AC-1: Each progress line is appended to the journal at the same point
    it is emitted, not buffered and flushed at the end.
    """

    def test_ac1_journal_append_mechanism_defined_in_js(self):
        # covers: BO-1000c-1a
        """finalize-feature.js must define or import a journal-append mechanism —
        either a named helper (appendJournal, writeProgressLine, etc.) or a direct
        fs.appendFileSync call — so that individual progress lines can be durably
        written as they are emitted.

        Must be implemented to make this test green:
          In finalize-feature.js, define a helper such as:
            function appendJournal(line) { ... }
          or use fs.appendFileSync() directly, at the point where narrate() and
          outcome() emit their progress lines.
        """
        js = _js_text()
        self.assertTrue(
            bool(_JOURNAL_APPEND_DEFINITION.search(js)),
            msg=(
                "finalize-feature.js does not define or call a journal-append "
                "mechanism (appendJournal, writeProgressLine, fs.appendFileSync, "
                "appendFileSync). AC BO-1000c-1a requires a durable append at the "
                "moment each progress line is emitted. Implement the mechanism and "
                "call it from narrate() and outcome()."
            ),
        )

    def test_ac1_journal_append_called_inside_narrate_function_body(self):
        # covers: BO-1000c-1a
        """The journal-append call must appear inside the narrate() function body
        so that start-of-step lines are written to the journal at the moment they
        are emitted — before any agent() dispatch in that step.

        Must be implemented to make this test green:
          In finalize-feature.js, modify the narrate() function to call
          appendJournal (or equivalent) alongside log(), e.g.:
            function narrate(progressText, description) {
              const line = progressText + ': ' + description;
              log(line);
              appendJournal(line);
            }
        """
        js = _js_text()
        narrate_body = _extract_function_body(js, "narrate")
        self.assertTrue(
            narrate_body,
            msg=(
                "Could not extract the body of function narrate() from "
                "finalize-feature.js. Ensure narrate() is defined as "
                "'function narrate(...) { ... }'."
            ),
        )
        self.assertTrue(
            bool(_JOURNAL_APPEND_CALL.search(narrate_body)),
            msg=(
                "The narrate() function body does not contain a journal-append "
                "call (appendJournal, writeProgressLine, fs.appendFileSync, etc.). "
                "AC BO-1000c-1a requires start-of-step lines to be appended to the "
                "durable journal at the moment they are emitted — add the journal "
                f"call inside narrate(). Extracted body:\n{narrate_body}"
            ),
        )

    def test_ac1_journal_append_called_inside_outcome_function_body(self):
        # covers: BO-1000c-1a
        """The journal-append call must appear inside the outcome() function body
        so that per-step outcome lines are written to the journal at the moment
        they are emitted — after the step's work completes.

        Must be implemented to make this test green:
          In finalize-feature.js, modify the outcome() function to call
          appendJournal (or equivalent) alongside log(), e.g.:
            function outcome(progressText, description) {
              const entry = { step: progressText, outcome: description };
              stepOutcomes.push(entry);
              const line = progressText + ': ' + description;
              log(line);
              appendJournal(line);
            }
        """
        js = _js_text()
        outcome_body = _extract_function_body(js, "outcome")
        self.assertTrue(
            outcome_body,
            msg=(
                "Could not extract the body of function outcome() from "
                "finalize-feature.js. Ensure outcome() is defined as "
                "'function outcome(...) { ... }'."
            ),
        )
        self.assertTrue(
            bool(_JOURNAL_APPEND_CALL.search(outcome_body)),
            msg=(
                "The outcome() function body does not contain a journal-append "
                "call (appendJournal, writeProgressLine, fs.appendFileSync, etc.). "
                "AC BO-1000c-1a requires per-step outcome lines to be appended to "
                "the durable journal at the moment they are emitted — add the "
                f"journal call inside outcome(). Extracted body:\n{outcome_body}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-1 (durable / externally readable): A caller outside the background run
#       can read the journal while the run is in flight.
# ---------------------------------------------------------------------------

class TestJournalReadableByExternalCallerWhileRunInFlight(unittest.TestCase):
    """AC-1 (durable): The journal must be a durable, file-based record at a
    path an external caller can locate deterministically — not an in-memory
    structure visible only to the running workflow process.
    """

    def test_ac1_journal_path_variable_defined(self):
        # covers: BO-1000c-1a
        """finalize-feature.js must declare a journal-path variable — a file
        path where the run-progress journal is written. This makes the journal
        accessible to external pollers (BO-1000c-1b) without parsing log output.

        Must be implemented to make this test green:
          In finalize-feature.js, declare a variable such as:
            const journalPath = <path keyed to worktree/run>;
          and use it in the journal-append helper.
        """
        js = _js_text()
        self.assertTrue(
            bool(_JOURNAL_PATH_DEFINITION.search(js)),
            msg=(
                "finalize-feature.js does not declare a journal-path variable "
                "(journalPath, progressJournalPath, runProgressPath, etc.). "
                "AC BO-1000c-1a requires the journal to live at a deterministic "
                "path so that an external caller (e.g. the launcher/relay in "
                "BO-1000c-1b) can locate and read it while the run is in flight. "
                "Declare and use a named journal-path variable."
            ),
        )

    def test_ac1_journal_path_keyed_to_run_context(self):
        # covers: BO-1000c-1a
        """The journal path must incorporate the worktree root, run ID, or
        similar run-specific context — AND that run-specific context must be
        referenced in the VICINITY of the journal path declaration, not merely
        somewhere in the file.

        Must be implemented to make this test green:
          First declare a journal path variable (journalPath, etc.), then
          construct it from the worktree root or a run ID, e.g.:
            const journalPath = path.join(worktreeRoot, 'run-progress.jsonl');
          The run-context reference (worktreeRoot, worktree_root, epicArg,
          preflightInfo, etc.) must appear within 300 characters of the
          journal-path variable declaration.
        """
        js = _js_text()

        # Step 1: journal path variable must exist.
        journal_path_match = _JOURNAL_PATH_DEFINITION.search(js)
        self.assertIsNotNone(
            journal_path_match,
            msg=(
                "finalize-feature.js does not declare a journal-path variable "
                "(journalPath, progressJournalPath, runProgressPath, etc.). "
                "AC BO-1000c-1a requires the journal to live at a deterministic "
                "path so that an external caller can locate it while the run is "
                "in flight. Declare and use a named journal-path variable."
            ),
        )

        # Step 2: run-specific context must appear near the path declaration.
        vicinity_start = max(0, journal_path_match.start() - 300)
        vicinity_end = min(len(js), journal_path_match.end() + 300)
        vicinity = js[vicinity_start:vicinity_end]
        self.assertTrue(
            bool(_PATH_KEYED_TO_RUN.search(vicinity)),
            msg=(
                "A journal-path variable was found, but the run-specific context "
                "(worktree_root, worktreeRoot, runId, epicArg, preflightInfo, "
                "journal.jsonl, progress.jsonl, etc.) does not appear within "
                "300 characters of the declaration. AC BO-1000c-1a requires the "
                "journal path to be keyed to the worktree/run so that the launcher "
                "can locate it deterministically. Reference the worktree root or "
                "run ID when constructing the path."
            ),
        )


# ---------------------------------------------------------------------------
# AC-2: The record preserves the emission order of the lines.
# ---------------------------------------------------------------------------

class TestJournalPreservesEmissionOrder(unittest.TestCase):
    """AC-2: The journal must preserve the emission order of the progress lines.
    Append-mode writes guarantee ordering; overwriting the file destroys it.
    """

    def test_ac2_journal_uses_append_mode_not_overwrite(self):
        # covers: BO-1000c-1a
        """The journal-write mechanism must use an append-mode write (not
        write/overwrite mode) so that previously written lines are never
        clobbered and emission order is preserved.

        Must be implemented to make this test green:
          Use fs.appendFileSync(), fs.appendFile(), or open with flag 'a'
          when writing to the journal — NOT fs.writeFileSync() (which would
          overwrite the journal and destroy the emission order).
        """
        js = _js_text()
        self.assertTrue(
            bool(_APPEND_MODE_WRITE.search(js)),
            msg=(
                "finalize-feature.js does not contain an append-mode file write "
                "(fs.appendFileSync, fs.appendFile, or open flag 'a'). "
                "AC BO-1000c-1a AC-2 requires the journal to preserve emission "
                "order — this is only guaranteed by append-mode writes, never by "
                "overwriting the file. Use fs.appendFileSync() or equivalent."
            ),
        )

    def test_ac2_no_overwrite_of_journal_file(self):
        # covers: BO-1000c-1a
        """The finalize workflow must NOT overwrite the journal file with
        writeFileSync (which would erase previously appended entries and
        break the emission-order guarantee).

        This test passes when no writeFileSync/writeFile call directly
        targets the journal path variable.

        Must be implemented to make this test green:
          Do NOT use fs.writeFileSync(journalPath, ...) or
          fs.writeFile(journalPath, ...). Use only append-mode writes.
        """
        js = _js_text()
        self.assertFalse(
            bool(_OVERWRITE_JOURNAL_ANTI_PATTERN.search(js)),
            msg=(
                "finalize-feature.js contains a writeFileSync or writeFile call "
                "that targets the journal — this would overwrite the journal and "
                "destroy the emission order. Replace with fs.appendFileSync() or "
                "fs.appendFile() to satisfy AC BO-1000c-1a AC-2."
            ),
        )

    def test_ac2_journal_append_call_count_covers_both_narrate_and_outcome(self):
        # covers: BO-1000c-1a
        """Emission order is preserved only if EVERY emitted line is journalled —
        both start-of-step (narrate) and per-step-outcome (outcome) lines.
        This test confirms the journal-append mechanism is referenced in both
        function bodies (or in a shared helper called by both).

        Must be implemented to make this test green:
          Ensure that appendJournal (or equivalent) is called from both
          narrate() and outcome(), so that EVERY progress line reaches the
          journal in the order it is emitted.
        """
        js = _js_text()
        narrate_body = _extract_function_body(js, "narrate")
        outcome_body = _extract_function_body(js, "outcome")

        narrate_has_journal = bool(
            _JOURNAL_APPEND_CALL.search(narrate_body) if narrate_body else None
        )
        outcome_has_journal = bool(
            _JOURNAL_APPEND_CALL.search(outcome_body) if outcome_body else None
        )

        errors = []
        if not narrate_has_journal:
            errors.append("narrate() body: no journal-append call found")
        if not outcome_has_journal:
            errors.append("outcome() body: no journal-append call found")

        self.assertEqual(
            errors,
            [],
            msg=(
                "Journal-append calls are missing in one or more progress-emission "
                "functions:\n"
                + "\n".join(f"  - {e}" for e in errors)
                + "\n\nAC BO-1000c-1a AC-2 requires EVERY emitted line (both "
                "start-of-step via narrate() and per-step-outcome via outcome()) "
                "to be appended to the journal in emission order. Add "
                "appendJournal() calls to both functions."
            ),
        )


# ---------------------------------------------------------------------------
# AC-2 (incremental): The journal is written incrementally, not flushed only
#       once at the end of the run.
# ---------------------------------------------------------------------------

class TestJournalWrittenIncrementallyNotOnlyAtEnd(unittest.TestCase):
    """AC-2 (incremental): The journal is written incrementally over the
    course of the run — each line is flushed at the time it is emitted,
    so an external poller can read entries while the run is still in flight.
    """

    def test_ac2_journal_append_not_deferred_to_end_of_workflow(self):
        # covers: BO-1000c-1a
        """The journal-append call must appear in narrate() or outcome()
        (i.e. per-step emission sites), NOT only in a single end-of-workflow
        accumulation flush after all steps complete.

        If the journal-append helper is called ONLY in an end-of-run block
        (e.g. only after the Step 7 outcome() call, or only in a final
        'stepOutcomes.forEach(appendJournal)' block), the AC is NOT satisfied —
        an external poller cannot read entries while the run is in flight.

        Must be implemented to make this test green:
          Ensure appendJournal() is called inline in narrate() and outcome()
          (the same place log() is called), not deferred to after all steps.
          The stepOutcomes[] array exists for downstream summary consumers —
          it is NOT a substitute for per-emission journal writes.
        """
        js = _js_text()

        # The journal-append mechanism must be called from within narrate() or
        # outcome() — the per-emission functions — not solely deferred.
        narrate_body = _extract_function_body(js, "narrate")
        outcome_body = _extract_function_body(js, "outcome")

        narrate_has_inline_journal = bool(
            _JOURNAL_APPEND_CALL.search(narrate_body) if narrate_body else None
        )
        outcome_has_inline_journal = bool(
            _JOURNAL_APPEND_CALL.search(outcome_body) if outcome_body else None
        )

        at_least_one_inline = narrate_has_inline_journal or outcome_has_inline_journal

        self.assertTrue(
            at_least_one_inline,
            msg=(
                "Neither narrate() nor outcome() contains an inline journal-append "
                "call. The journal-append mechanism may only exist in a deferred "
                "end-of-workflow accumulation block (e.g. a forEach over stepOutcomes). "
                "AC BO-1000c-1a requires the journal to be written INCREMENTALLY — "
                "at the moment each line is emitted — so that an external poller "
                "can read entries while the run is in flight. Move the journal-append "
                "call inside narrate() and outcome()."
            ),
        )

    def test_ac2_stepOutcomes_array_is_not_the_only_journal_mechanism(self):
        # covers: BO-1000c-1a
        """The existing stepOutcomes[] array is an IN-MEMORY accumulation used
        by BO-1000b-2 (end-of-run summary) and BO-1000c-1a (live journal relay).
        It is NOT a durable journal on its own — it cannot be read by an external
        process while the workflow is running.

        This test confirms that a SEPARATE, FILE-BASED journal mechanism exists
        alongside (not instead of) stepOutcomes[].

        Must be implemented to make this test green:
          Keep stepOutcomes[] for downstream summary consumers AND add a
          file-based journal-append call in narrate() and/or outcome() that
          writes each line to disk at the moment of emission.
        """
        js = _js_text()

        # stepOutcomes[] must still exist (for downstream consumers).
        has_step_outcomes = "stepOutcomes" in js
        # A file-based journal mechanism must ALSO exist.
        has_file_journal = bool(_JOURNAL_APPEND_DEFINITION.search(js))

        self.assertTrue(
            has_step_outcomes,
            msg=(
                "stepOutcomes[] is missing from finalize-feature.js. "
                "This array is required by BO-1000b-2 (end-of-run summary). "
                "Keep it alongside the new file-based journal mechanism."
            ),
        )
        self.assertTrue(
            has_file_journal,
            msg=(
                "finalize-feature.js only has the stepOutcomes[] in-memory "
                "accumulation — no file-based journal-append mechanism was found. "
                "AC BO-1000c-1a requires a DURABLE, file-based journal that can be "
                "read by an external process while the run is in flight. "
                "Add fs.appendFileSync() or an appendJournal() helper alongside "
                "stepOutcomes[]."
            ),
        )


if __name__ == "__main__":
    unittest.main()
