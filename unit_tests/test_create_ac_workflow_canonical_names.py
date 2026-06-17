"""
Tests that create_ac_workflow.py uses canonical agent names only.

AC reference: ACD-1401
Root cause: constants AGENT_PO_V3, AGENT_BA_V3, and AGENT_ITPO_V3 in
scripts/ac_store/create_ac_workflow.py (lines 31-33) still hold the obsolete
v3 string values ("product-owner-v3", "business-analyst-v3", "it-po-v3").
These names were never renamed to canonical form when the agents were promoted.

The tests below MUST FAIL (red) until the constant values are updated to the
canonical names: "product-owner", "business-analyst", "it-po".
"""

import os
import unittest

# Resolve the path to the target source file relative to this test file so
# the test suite works regardless of which directory the runner is invoked from.
_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")
)
_CREATE_AC_WORKFLOW_PY = os.path.join(
    _REPO_ROOT, "scripts", "ac_store", "create_ac_workflow.py"
)


class TestCreateAcWorkflowCanonicalAgentNames(unittest.TestCase):
    """create_ac_workflow.py must not reference the obsolete *-v3 agent names."""

    @classmethod
    def setUpClass(cls):
        # covers: ACD-1401
        with open(_CREATE_AC_WORKFLOW_PY, "r", encoding="utf-8") as fh:
            cls.content = fh.read()

    def test_no_product_owner_v3_constant(self):
        # covers: ACD-1401
        """AGENT_PO_V3 must not hold the value 'product-owner-v3'.

        The canonical agent name is 'product-owner'. The string literal
        'product-owner-v3' appearing as a constant value in
        create_ac_workflow.py means the pipeline will dispatch a non-existent
        agent name. Replace with the canonical form 'product-owner'.
        """
        self.assertNotIn(
            "product-owner-v3",
            self.content,
            "create_ac_workflow.py still contains the string 'product-owner-v3' "
            "(likely as the value of AGENT_PO_V3 on line 31). "
            "Replace with the canonical agent name 'product-owner'.",
        )

    def test_no_business_analyst_v3_constant(self):
        # covers: ACD-1401
        """AGENT_BA_V3 must not hold the value 'business-analyst-v3'.

        The canonical agent name is 'business-analyst'. The string literal
        'business-analyst-v3' appearing as a constant value in
        create_ac_workflow.py means the pipeline will dispatch a non-existent
        agent name. Replace with the canonical form 'business-analyst'.
        """
        self.assertNotIn(
            "business-analyst-v3",
            self.content,
            "create_ac_workflow.py still contains the string 'business-analyst-v3' "
            "(likely as the value of AGENT_BA_V3 on line 32). "
            "Replace with the canonical agent name 'business-analyst'.",
        )

    def test_no_it_po_v3_constant(self):
        # covers: ACD-1401
        """AGENT_ITPO_V3 must not hold the value 'it-po-v3'.

        The canonical agent name is 'it-po'. The string literal 'it-po-v3'
        appearing as a constant value in create_ac_workflow.py means the
        pipeline will dispatch a non-existent agent name. Replace with the
        canonical form 'it-po'.
        """
        self.assertNotIn(
            "it-po-v3",
            self.content,
            "create_ac_workflow.py still contains the string 'it-po-v3' "
            "(likely as the value of AGENT_ITPO_V3 on line 33). "
            "Replace with the canonical agent name 'it-po'.",
        )


if __name__ == "__main__":
    unittest.main()
