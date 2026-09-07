"""
MODULE: check_outcome
GOAL: Declare, in exactly one place, the machine-readable outcome vocabulary
    that commit_guardian pre-commit checks emit when a check could not
    perform its inspection at all, as distinct from a genuine clean pass.
BUSINESS CONTEXT: Before GE-120a-1, a check that could not reach a
    prerequisite it needed (e.g. a shared helper module absent from a
    partially-deployed working copy) printed a single fail-open WARNING line
    to stderr and returned the SAME exit code as a genuine clean pass. A
    caller reading only the exit code — pre-commit itself, the GE-120b-4
    fleet-wide sweep, or the GE-120c-1 harness — could not tell "nothing was
    wrong" apart from "the check never actually ran." GE-120a-2 additionally
    permits an "announce" disposition for a could-not-check outcome that
    still exits 0, so exit status alone can never carry this distinction.
    This module gives every check a single, shared vocabulary to emit on
    stdout that a caller can detect with a plain ``str.startswith("RESULT: ")``
    check, independent of exit code and without parsing prose.
ARCHITECTURE: A leaf module with no imports beyond the standard library, so
    every check in this directory can import it unconditionally once
    build.py has deployed the whole templates/scripts/commit_guardian/ tree
    alongside it (ADR-001 template/deployed parity). Checks that may run
    from a working copy where even this module is not guaranteed to be
    present (e.g. an isolated test fixture that copies only the check
    script) MUST still degrade gracefully — see the
    ``check_ac_parent_covered_by.py`` import-with-fallback pattern this
    module's own values are declared to keep in sync with.

DOC_LINKS:
  - docs/reference/ac-schema.md

DECISION HISTORY:
  - 2026-08-25 [python-coder/GE-120e-1-i]: Added OUTCOME_NOTHING_TO_INSPECT.
    GE-120e-1-i requires that a check deriving its OWN authored change set
    (as opposed to the whole staged tree) report an empty derived set as an
    explicit "nothing of the author's to inspect" outcome, distinguishable
    from OUTCOME_COULD_NOT_CHECK ("a check that never looked") and from
    OUTCOME_OK ("ran and found nothing wrong"). Per that AC's own
    it_requirements ("REUSE GE-120a-1'S OUTPUT VOCABULARY FOR THE
    DISTINCTION ... add it to GE-120a-1's vocabulary ... rather than
    inventing a parallel one"), this value is added HERE rather than to a
    new module. Consumers: check_contract_shrinking.py and
    check_doc_frontmatter.py, both of which derive an authored (merge-
    scoped) change set that can legitimately come back empty.
    (#EPIC-TrustThatAGreenCheckActuallyChecked/29)
  - 2026-08-25 [python-coder/GE-120a-1]: Created as the shared could-not-check
    outcome vocabulary GE-120a-1's it_requirements calls for ("Declare the
    outcome vocabulary ONCE in a shared module... that every check imports").
    Only OUTCOME_OK and OUTCOME_COULD_NOT_CHECK are defined here; a third
    OUTCOME_DEGRADED value is GE-120a-1-ii's concern, not this ticket's.
    (#EPIC-TrustThatAGreenCheckActuallyChecked/01)
"""

from __future__ import annotations

import sys

OUTCOME_OK = "ok"
OUTCOME_COULD_NOT_CHECK = "could_not_check"
# GE-120e-1-i: an empty authored (self-derived) change set is a distinct,
# explicitly represented outcome -- NOT a signal to fall back to the whole
# staged tree, and NOT the same value as OUTCOME_COULD_NOT_CHECK. See the
# DECISION HISTORY entry above and check_contract_shrinking.py /
# check_doc_frontmatter.py for the two consumers this was added for.
OUTCOME_NOTHING_TO_INSPECT = "nothing_to_inspect"

_RESULT_PREFIX = "RESULT: "


def emit_result(outcome: str) -> None:
    """Print the machine-readable result line to stdout.

    The line has the fixed shape ``RESULT: <outcome>`` so a caller can
    detect it with ``line.startswith("RESULT: ")`` without parsing prose,
    independent of the process exit code.

    Args:
        outcome: One of the OUTCOME_* constants declared in this module.
    """
    print(f"{_RESULT_PREFIX}{outcome}", file=sys.stdout)
