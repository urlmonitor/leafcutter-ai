"""
MODULE: test_bo_400e_4
GOAL: Thin entry point for the BO-400e-4 behavioral suite -- several tickets
    in the identical state, carried by ONE run, all get the same answer, and
    it is the strict one.
BUSINESS CONTEXT: docs/acceptance-criteria/build-orchestration/BO-400-
    ticket-status-source-of-truth/BO-400e-4.yaml's ``test_command`` runs
    ``python -m unittest discover -s unit_tests/prompt_assembly -p
    test_bo_400e_4.py`` (an exact-match filename pattern, not a glob) and its
    ``covered_by`` names ``unit_tests/prompt_assembly/test_bo_400e_4.py``
    exactly; the epic ticket (04_TICKET-20260914-BO-400e-4.md) also
    references this exact filename throughout its audit trail. This file's
    name and location are therefore load-bearing and must not change. See
    test_bo_400e_4_fixtures for the full ADR-048 (docs/architecture/adrs/
    ADR-048-order-independent-per-ticket-completion.md) rationale this suite
    verifies.
ARCHITECTURE: Pure re-export facade -- no test logic lives in this file.
    Follows the build_phases.py / build_phases_docs.py precedent
    (GE-127a-1 crossing refusal / GE-127b-1 ratchet file-size split): the
    original file keeps its name and is kept under the 400-line limit by
    moving the actual test bodies to sibling modules. unittest's TestLoader
    discovers TestCase subclasses via ``dir(module)``, so importing a class
    here into this module's namespace makes it discoverable and runnable
    from THIS file exactly as if it were still defined here. The five test
    classes' real bodies live in:
      - test_bo_400e_4_fixtures      -- shared constants + _FourTicketOneRunCase
      - test_bo_400e_4_ordering      -- the load-bearing case + order-independence
      - test_bo_400e_4_repeatability -- same four tickets, second run
      - test_bo_400e_4_reachability  -- REQUIRED real-workflow-run reachability
      - test_bo_400e_4_batching      -- ADR-048 Section 3 no-batching half
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_bo_400e_4_batching import (  # noqa: E402
    TestEachClosingTicketGetsItsOwnCompletionWriteDispatchNeverBatched,
)
from test_bo_400e_4_fixtures import (  # noqa: E402, F401
    ALL_LABELS,
    EPIC_SUBDIR,
    IDENTICAL_LABELS,
    IDENTICAL_PHASES,
    OUTSTANDING_PHASE,
    TICKET_NAMES,
    _FourTicketOneRunCase,
)
from test_bo_400e_4_ordering import (  # noqa: E402
    TestAnswersDoNotVaryWithTheOrderTheRunReachesTheFourTickets,
    TestFourTicketsInOneRunReceiveOneAnswerThreeRefusedOneWritten,
)
from test_bo_400e_4_reachability import (  # noqa: E402
    TestOneAnswerPerConditionIsReachableFromARealWorkflowRun,
)
from test_bo_400e_4_repeatability import (  # noqa: E402
    TestASecondRunOverTheSameFourTicketsProducesTheSameFourAnswers,
)

__all__ = [
    "ALL_LABELS",
    "EPIC_SUBDIR",
    "IDENTICAL_LABELS",
    "IDENTICAL_PHASES",
    "OUTSTANDING_PHASE",
    "TICKET_NAMES",
    "TestASecondRunOverTheSameFourTicketsProducesTheSameFourAnswers",
    "TestAnswersDoNotVaryWithTheOrderTheRunReachesTheFourTickets",
    "TestEachClosingTicketGetsItsOwnCompletionWriteDispatchNeverBatched",
    "TestFourTicketsInOneRunReceiveOneAnswerThreeRefusedOneWritten",
    "TestOneAnswerPerConditionIsReachableFromARealWorkflowRun",
]


if __name__ == "__main__":
    unittest.main()
