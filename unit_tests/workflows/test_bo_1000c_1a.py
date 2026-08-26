"""BO-1000c-1a — in-flight run-progress visibility for background finalize.

REDEFINED 2026-08-18. This file was previously a presence-only suite: ten tests
that read finalize-feature.js as text and asserted that an `appendJournal`
helper, a `journalPath` variable and an `fs.appendFileSync` call were present in
the source. Every one of them passed for the entire life of the defect, because
the strings really were there. None of them ever executed the mechanism, and the
mechanism never once ran: `appendJournal()` loaded Node's `fs` module through the
CommonJS module loader, and the E2 engine injects only
agent/parallel/pipeline/phase/log/args/workflow/budget into a workflow body — no
module loader (ADR-030). The `require('fs')` call threw on every invocation, a
surrounding try/catch logged a WARNING, and the run reported success. The AC read
`work_status: done` throughout.

That is the M1 failure mode from docs/reference/false-green-mechanisms.md in its
purest form, and it is worth being precise about why the old tests could not have
caught it: they asserted that code *exists*, which was true, as a stand-in for the
code *working*, which was false. No amount of adding more presence assertions
would have helped.

The criterion has been redefined onto the journal the engine already writes at
<transcriptDir>/journal.jsonl — a {"type":"started"} / {"type":"result"} record
pair per agent() dispatch. See BO-1000c-1a's `amended_by` entry for the full
decision record, including the rejected alternatives.

Scope of THIS file: the absence guard below, which needs nothing but the source
text. The executed dispatch-coverage tests that make up the rest of the
redefined contract require a vm-sandboxed workflow harness that does not exist
on main yet; they land with that harness rather than here, so that this change
stays reviewable as a deletion.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


class TestCustomFilesystemJournalMechanismIsFullyRemoved(unittest.TestCase):
    """A filesystem-backed journal append that *cannot* happen must not be a
    live code path at all — not merely fail loudly instead of silently.

    This is the one assertion in this file that reads source text directly, and
    it is deliberately an ABSENCE check rather than a presence claim. The
    distinction matters, and it is the reason this test is legitimate where the
    ten it replaces were not: a presence assertion stays green on dead code,
    which is exactly what happened here for weeks. An absence assertion cannot —
    it fails the moment the known-broken pattern reappears, whether or not the
    reintroduced version is wrapped in a swallowing try/catch, and whether or not
    it is ever reached at runtime.

    It exists to catch a REGRESSION that no executed test can detect: a
    reintroduced `require('fs')` journal write that is functionally inert would
    not change any observable dispatch, so a behavioural suite would stay green
    while the defect returned.
    """

    def test_no_module_loader_or_custom_journal_helper_remains(self):
        # covers: BO-1000c-1a
        """finalize-feature.js must contain neither a require(...) call nor the
        removed appendJournal helper nor its journalPath variable.
        """
        source = _js_text()
        self.assertNotIn(
            "require(",
            source,
            msg=(
                "finalize-feature.js contains a require(...) call. This script's "
                "top-level body runs under the E2 engine's ADR-030 contract, which "
                "injects no module loader — any require(...) here either throws "
                "unconditionally in production or, if wrapped in a try/catch, "
                "silently swallows that throw. The latter is the exact defect that "
                "kept BO-1000c-1a marked done while it had never written a line."
            ),
        )
        self.assertNotIn(
            "appendJournal",
            source,
            msg=(
                "finalize-feature.js still references appendJournal, the removed "
                "on-disk journal helper. In-flight visibility now comes from the E2 "
                "engine's own per-agent journal.jsonl; do not reintroduce a custom "
                "filesystem-backed journal helper."
            ),
        )
        self.assertNotIn(
            "journalPath",
            source,
            msg=(
                "finalize-feature.js still declares a journalPath variable. The "
                "custom on-disk journal was removed entirely, not relocated."
            ),
        )


if __name__ == "__main__":
    unittest.main()
