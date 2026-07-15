"""
Tests that plan-feature.js dispatches agents using canonical names only.

AC reference: ACD-1400
Root cause: create-ac-to-plan-feature rename updated the file/skill name but
missed the agent dispatch references inside the workflow script. The pipeline
arrays once referenced product-owner-v3, business-analyst-v3, and it-po-v3 —
none of which exist as real agents. These tests guard against a regression to
the obsolete *-v3 names.

Retargeted to the E2 runtime file (templates/workflows-js/plan-feature.js) —
the legacy scripts/workflows/plan-feature.js was retired during foundation
cleanup and is no longer the consumer surface.
"""

import os
import unittest

# The E2 runtime file is the sole plan-feature.js consumer surface.
_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")
)
_PLAN_FEATURE_JS = os.path.join(
    _REPO_ROOT, "templates", "workflows-js", "plan-feature.js"
)


class TestPlanFeatureCanonicalAgentNames(unittest.TestCase):
    """plan-feature.js must not reference the obsolete *-v3 agent names."""

    @classmethod
    def setUpClass(cls):
        with open(_PLAN_FEATURE_JS, "r", encoding="utf-8") as fh:
            cls.content = fh.read()

    def test_no_product_owner_v3_reference(self):
        # covers: ACD-1400
        """product-owner-v3 must not appear anywhere in plan-feature.js.

        The canonical agent name is 'product-owner'. Any occurrence of
        'product-owner-v3' indicates the dispatch table was not updated after
        the create-ac-to-plan-feature rename.
        """
        self.assertNotIn(
            "product-owner-v3",
            self.content,
            "plan-feature.js still dispatches the non-existent agent "
            "'product-owner-v3'. Replace with canonical name 'product-owner'.",
        )

    def test_no_business_analyst_v3_reference(self):
        # covers: ACD-1400
        """business-analyst-v3 must not appear anywhere in plan-feature.js.

        The canonical agent name is 'business-analyst'. Any occurrence of
        'business-analyst-v3' indicates the dispatch table was not updated
        after the create-ac-to-plan-feature rename.
        """
        self.assertNotIn(
            "business-analyst-v3",
            self.content,
            "plan-feature.js still dispatches the non-existent agent "
            "'business-analyst-v3'. Replace with canonical name "
            "'business-analyst'.",
        )

    def test_no_it_po_v3_reference(self):
        # covers: ACD-1400
        """it-po-v3 must not appear anywhere in plan-feature.js.

        The canonical agent name is 'it-po'. Any occurrence of 'it-po-v3'
        indicates the dispatch table was not updated after the
        create-ac-to-plan-feature rename.
        """
        self.assertNotIn(
            "it-po-v3",
            self.content,
            "plan-feature.js still dispatches the non-existent agent "
            "'it-po-v3'. Replace with canonical name 'it-po'.",
        )


if __name__ == "__main__":
    unittest.main()
