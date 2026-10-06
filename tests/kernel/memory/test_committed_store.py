"""
MODULE: tests.kernel.memory.test_committed_store
GOAL: The committed decision store (docs/decisions of this checkout) is valid: every record passes
    the schema and the semantic rules, the generated index is current, the first record (the
    decision that chose this format) is present and human-approved, and the knowledge map reads it.
BUSINESS CONTEXT: "Validated at commit" without a new pre-commit hook (ADR-059): the normal test
    suite and CI run the same validation as `python -m kernel decisions validate` over the real
    store, so a hand-edited record or a stale index cannot reach main unnoticed.
ARCHITECTURE: Reads the real repository files; writes nothing. The knowledge-map check runs the
    real `scripts/knowledge_query.py` over the real `config/paths.json` (the `docs` surface
    covers docs/decisions/; a dedicated surface needs an acceptance criterion, see ADR-059).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

from kernel.config import load_kernel_config
from kernel.memory.index import INDEX_NAME, parse_index
from kernel.memory.validate import validate_store
from tests.kernel.memory.support import CHECKOUT, schema, vocabulary

FIRST = "dec-ef8ddcb79d668a67"
STORE = CHECKOUT / "docs" / "decisions"


class TestCommittedStore(unittest.TestCase):
    """The real store."""

    def test_the_committed_store_validates_and_its_index_is_current(self) -> None:
        # covers: DK-600d-2
        report = validate_store(STORE, schema=schema(), vocab=vocabulary())
        self.assertTrue(report.ok, [p.as_dict() for p in report.problems])

    def test_the_store_folder_comes_from_config(self) -> None:
        self.assertEqual(CHECKOUT / load_kernel_config().memory.decisions_dir, STORE)

    def test_the_first_record_is_the_decision_that_chose_the_format(self) -> None:
        report = validate_store(STORE, schema=schema(), vocab=vocabulary(), check_index=False)
        record = report.records[FIRST]
        self.assertEqual(record.title, "Kernel-contract YAML per decision")
        self.assertEqual(record.approval.approved_by, "human:user")
        self.assertEqual(record.approval.approved_at, "2026-10-01T14:48:31Z")
        self.assertEqual(record.provenance.langfuse_trace_id, "c93592ca1a813365b7d48d5a8363c66d")
        self.assertEqual(len(record.evidence), 20)
        self.assertTrue(all(e.source_version and e.source_version.commit for e in record.evidence))
        self.assertTrue(all(len(e.content_hash) == 64 for e in record.evidence))

    def test_the_index_lists_every_record_file(self) -> None:
        entries = parse_index((STORE / INDEX_NAME).read_text(encoding="utf-8"))
        files = sorted(p.name for p in STORE.glob("dec-*.yaml"))
        self.assertEqual(sorted(e.file for e in entries), files)

    def test_the_knowledge_map_reads_the_records_through_the_docs_surface(self) -> None:
        done = subprocess.run(  # noqa: S603 - fixed argv, repo script
            [sys.executable, str(CHECKOUT / "scripts" / "knowledge_query.py"), "--format", "json",
             "--edges", "--project-root", str(CHECKOUT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            timeout=120, env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(done.returncode, 0, done.stderr)
        document = json.loads(done.stdout)
        nodes = {n["id"]: n for n in document["nodes"] if n["id"].startswith("dec-")}
        self.assertIn(FIRST, nodes)
        self.assertEqual(nodes[FIRST]["title"], "Kernel-contract YAML per decision")
        self.assertNotIn("'", nodes[FIRST]["description"][:1])  # a one-line, unquoted description
        targets = {e["target"] for e in document["edges"] if e["source"] == FIRST}
        self.assertEqual(targets, {"decision_kernel", "knowledge_management"})  # component edges

    def test_the_docs_surface_covers_the_store_folder(self) -> None:
        paths = json.loads((CHECKOUT / "config" / "paths.json").read_text(encoding="utf-8"))
        self.assertEqual(paths["surfaces"]["docs"]["path"], "docs/")
        self.assertIn("components", paths["surfaces"]["docs"]["edge_fields"])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The first record is asserted field by field against the facts of
#   run-2fbb4ef43b1345f6 so the filed record cannot drift from the decision it records.
#   (#KernelDecisionStore)
# ====================================================================
