"""The lane accepts a bundle whose layer content contains blank-line runs.

The JavaScript half of the 2026-08-31 regression. The Python-side companion
(test_bundle_blank_lines_are_not_an_empty_layer.py) proves the assembler no
longer produces an unrefused empty layer; this file proves the LANE no longer
refuses a good one.

Executed under the E2 harness against the real workflow, so it asserts on what
the run actually does -- whether the test-writer and coder are dispatched with
the bundle -- rather than on the text of the source.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import test_bo2400c_prompt_cache_wiring as _sibling  # noqa: E402

_MARKER = "<!-- CACHE_BREAKPOINT -->"

# A bundle shaped like the one that halted the live run: real content in every
# layer, marker present exactly once, and a run of 5 consecutive newlines where
# the architecture layer's trailing blank line met the "\n\n" join.
_BUNDLE_WITH_BLANK_LINE_RUN = (
    "# Architecture\n"
    "\n"
    "Some real prose about the system.\n"
    "\n"
    "<!--\n"
    "  ====================================\n"
    "-->\n"
    "\n"
    "\n"
    "\n"
    "# High-Level ACs\n"
    "\n"
    "Parent criteria text.\n"
    "\n"
    f"{_MARKER}\n"
    "\n"
    "# Prior Tests\n"
    "\n"
    "Existing coverage notes.\n"
)

# Sanity: the fixture must actually contain the run that used to trip the gate,
# otherwise this file silently stops guarding anything.
assert "\n\n\n\n" in _BUNDLE_WITH_BLANK_LINE_RUN, (
    "Fixture no longer reproduces the 4+ newline run it exists to test."
)
assert _BUNDLE_WITH_BLANK_LINE_RUN.count(_MARKER) == 1


def test_a_bundle_with_a_blank_line_run_is_usable_and_reaches_the_build_agents():
    # covers: BO-2400c-1-iii
    """A complete bundle containing 4+ consecutive newlines is not refused.

    RED before this fix: classifyContextBundle() tested /\\n{4,}/ and classified
    this as obtained_but_incomplete, halting the run before any build agent was
    dispatched. That is what happened to a real 16,442-byte bundle on
    2026-08-31.
    """
    bundle_response = {
        "obtained": True,
        "bundle": _BUNDLE_WITH_BLANK_LINE_RUN,
        "bytes": len(_BUNDLE_WITH_BLANK_LINE_RUN),
        "location": None,
        "message": "bundle assembled",
    }
    result = _sibling._run_ship(bundle_response=bundle_response)
    assert result.error == "", f"Harness error: {result.error}"

    labels = _sibling._labels_ship(result)
    assert "test-writer-connected" in labels, (
        "A complete bundle whose content merely contains blank lines must be "
        f"treated as usable and reach the test-writer. Labels: {labels}"
    )

    test_writer_call = _sibling._call(result, "test-writer-connected")
    assert test_writer_call is not None
    assert test_writer_call.prompt.startswith(_BUNDLE_WITH_BLANK_LINE_RUN), (
        "The usable bundle must be sent verbatim as the dispatch prefix."
    )


def test_a_bundle_truncated_immediately_after_the_marker_is_still_refused():
    # covers: BO-2400c-1-iii
    """Removing the newline heuristic must not remove the truncation guard.

    The transport check that survives is 'nothing follows the marker'. It is
    unambiguous -- assembly guarantees a non-empty prior_tests layer after the
    marker -- so an empty suffix means the text was cut in transit.
    """
    truncated = _BUNDLE_WITH_BLANK_LINE_RUN.split(_MARKER)[0] + _MARKER + "\n\n"
    bundle_response = {
        "obtained": True,
        "bundle": truncated,
        "bytes": len(truncated),
        "location": None,
        "message": "bundle assembled",
    }
    result = _sibling._run_ship(bundle_response=bundle_response)
    assert result.error == "", f"Harness error: {result.error}"

    labels = _sibling._labels_ship(result)
    assert "test-writer-connected" not in labels, (
        f"A bundle truncated after the marker must still halt. Labels: {labels}"
    )


def test_a_bundle_with_no_marker_is_still_refused():
    # covers: BO-2400c-1-iii
    """The marker-presence guard survives the change."""
    no_marker = _BUNDLE_WITH_BLANK_LINE_RUN.replace(_MARKER, "")
    bundle_response = {
        "obtained": True,
        "bundle": no_marker,
        "bytes": len(no_marker),
        "location": None,
        "message": "bundle assembled",
    }
    result = _sibling._run_ship(bundle_response=bundle_response)
    assert result.error == "", f"Harness error: {result.error}"

    labels = _sibling._labels_ship(result)
    assert "test-writer-connected" not in labels, (
        f"A bundle with no breakpoint marker must still halt. Labels: {labels}"
    )
