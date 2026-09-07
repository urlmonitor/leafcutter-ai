"""
MODULE: test_bo_2200c_5_producer_consumer_format
GOAL: RED regression tests for KI-ACD-002 — the generator
      (scripts/ac_store/generate_ticket_from_ac.py) and the consumer
      (templates/agents/documentation-verifier.md) disagree on the wire
      format of the '### documentation-expert' Agent Contracts checklist
      line, and a third, independent defect in genre resolution turns a
      deliberate "no documentation required" declaration into a phantom
      documentation obligation.

WHY unit_tests/test_bo_2200c_5.py DOES NOT CATCH THIS (per BO-2200c-5.yaml's
own reopening notes — read before editing anything):

    That file's tests assert only that a '- [ ] AC-N:' line is present and
    that it "contains a /" (see its docstrings: "keys on ... '- [ ] AC-N:'
    (checkbox with integer N)"). They never touch the FIELD STRUCTURE inside
    the line — the pipe-delimited '<genre> | <target_path> | <constraint>'
    shape documentation-verifier.md's Step 2 actually requires. A line with
    zero pipe characters satisfies every assertion in that file while being
    rejected outright by the verifier in production. BO-2200c-5.yaml's own
    notes name this exactly: "Asserting the emitted line 'contains a /' is
    not sufficient -- BO-2200c-2 does exactly that and passes on
    'docs/(unspecified genre)/acd-400b-6.md'."

Two independent, real defects are pinned here:

  1. PRODUCER/CONSUMER FORMAT DISAGREEMENT (KI-ACD-002, primary).
     Producer (generate_ticket_from_ac.py:2064):
         lines.append(f"- [ ] AC-{i}: [{genre}] {doc_path} — {constraint}")
     Consumer (documentation-verifier.md Step 2, lines ~130-158):
         "parse the target documentation path as the SECOND
         PIPE-DELIMITED FIELD ... If a line has no pipe separators ...
         emit (status: blocker)".
     The producer's line has ZERO pipe characters. Every real doc-required
     ticket the generator has ever produced is rejected by the verifier's
     documented algorithm.

  2. EMPTY-documentation_triggers TREATED AS MISSING (KI-ACD-002, third
     occurrence). `_resolve_genres_from_parent` treats a parent L1's
     EXPLICIT, DELIBERATE `documentation_triggers: []` identically to a
     parent that could not be resolved at all — it warns and returns
     `["(unspecified genre)"]`, and the caller emits a contract line anyway.
     An empty list is the store's documented way of saying "this change
     requires no documentation" (see BP-900g.yaml's own
     `documentation_rationale` field, copied verbatim into this test's fixture
     below) — not an omission to paper over.

Both tests run the REAL producer function
(`_build_agent_contracts_section` / `_build_agents_map` / `_find_ac_by_id`
from `scripts/ac_store/generate_ticket_from_ac.py`) over REAL, unmodified
on-disk AC records (copied byte-for-byte via `shutil.copy2` — never
hand-typed — per the project's Fixture Authenticity Rule), scoped to a small
temp AC store so `_find_ac_by_id`'s recursive store scan stays fast (the full
~3,500-record store makes that scan take 60-120s, which is a real,
independent performance property of the store, not something this test
should have to pay for).

TICKET: none — this is a direct red-baseline authoring task (test-writer
    dispatched without a ticket; see the task brief), not a ticket-driven
    TDD pass.
AC: BO-2200c-5 (REOPENED 2026-08-25; work_status: todo; covered_by: [])
Known issue: KI-ACD-002 (docs/known-issues/ac-driven-dev.md, updated 2026-08-25)
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_ticket_from_ac as gen  # noqa: E402

# ---------------------------------------------------------------------------
# Real, on-disk AC records used as fixtures (copied verbatim — never
# hand-typed; see the Fixture Authenticity Rule).
# ---------------------------------------------------------------------------

_AC_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"

# TQ-400a (parent, documentation_triggers: [how-to, component-diagram]) and
# its leaf TQ-400a-5 (assigned_agent: documentation-expert; doc_links include
# docs/how-to/done-proof-enforcement.md) — a real doc-required AC pair.
_TQ_400A_DIR = _AC_ROOT / "testing-quality" / "TQ-400-durable-done-proof"
_TQ_400A_PARENT_SRC = _TQ_400A_DIR / "TQ-400a.yaml"
_TQ_400A_LEAF_SRC = _TQ_400A_DIR / "TQ-400a-5.yaml"
_TQ_400A_LEAF_ID = "TQ-400a-5"
_TQ_400A_REAL_DOC_PATH = "docs/how-to/done-proof-enforcement.md"

# BP-900g (parent, documentation_triggers: [] — DELIBERATE, per its own
# documentation_rationale field) and its leaf BP-900g-1.
_BP_900G_DIR = _AC_ROOT / "build_pipeline" / "BP-900-deployment-completeness"
_BP_900G_PARENT_SRC = _BP_900G_DIR / "BP-900g.yaml"
_BP_900G_LEAF_SRC = _BP_900G_DIR / "BP-900g-1.yaml"
_BP_900G_LEAF_ID = "BP-900g-1"


# ---------------------------------------------------------------------------
# The verifier's DOCUMENTED Step 2 parse rule, reimplemented verbatim from
# templates/agents/documentation-verifier.md so a test can check whether the
# generator's REAL output actually satisfies the algorithm the verifier is
# instructed to run. There is no executable verifier module to import — it is
# an LLM agent prompt — so encoding its documented algorithm is the only way
# to test the producer/consumer contract mechanically.
# ---------------------------------------------------------------------------

_AC_LINE_REGEX = re.compile(r"^-\s\[[ x]\]\s*AC-\d+:\s*(.*)$")


def _verifier_parse_required_docs(doc_expert_subsection_text: str) -> list[str]:
    """Reimplements documentation-verifier.md Step 2's parse rule verbatim.

    Algorithm (templates/agents/documentation-verifier.md, "Step 2 — Parse
    Required Docs"):
      1. Collect every line matching '- [ ] AC-N:' or '- [x] AC-N:'.
      2. Parse the target documentation path as the SECOND PIPE-DELIMITED
         field of the remainder after 'AC-N:' --
             <genre> | <target_path> | <content_constraint>
      3. "If a line has no pipe separators or an empty second field": emit
         `(status: blocker)` -- "Agent Contracts line is malformed (no
         pipe-delimited target_path)". This function raises ValueError with
         that same documented message instead, so a test can observe the
         verifier's real, documented failure mode without needing to invoke
         an LLM.

    Args:
        doc_expert_subsection_text: The '### documentation-expert' subsection
            body (everything after the heading, up to the next '###' or end).

    Returns:
        The list of resolved target_path values, one per collected line.

    Raises:
        ValueError: with the verifier's own documented blocker message, when
            any collected line has no pipe separators or an empty second
            field, or when zero lines are found at all.
    """
    required_docs: list[str] = []
    for raw_line in doc_expert_subsection_text.splitlines():
        line = raw_line.strip()
        match = _AC_LINE_REGEX.match(line)
        if not match:
            continue
        remainder = match.group(1)
        fields = remainder.split("|")
        if len(fields) < 2 or not fields[1].strip():
            raise ValueError(
                "Agent Contracts line is malformed (no pipe-delimited target_path):\n"
                f"  {line}\n"
                "Expected format: - [ ] AC-N: <genre> | <target_path> | <content_constraint>"
            )
        required_docs.append(fields[1].strip())

    if not required_docs:
        raise ValueError(
            "Agent Contracts ### documentation-expert block has no parseable AC "
            "lines with target paths. At least one AC-N line with a target_path "
            "is required."
        )
    return required_docs


def _extract_doc_expert_subsection(section: str) -> str:
    """Extract the '### documentation-expert' subsection body from a full
    '## Agent Contracts' section string (everything after the heading line,
    up to the next '###' heading or end of string).

    This is the STRUCTURAL locate step both documentation-expert Contract-
    Aware Mode and documentation-verifier perform before parsing individual
    lines — it is not itself in dispute; the dispute is what happens to the
    lines once located (see _verifier_parse_required_docs above).
    """
    match = re.search(
        r"^### documentation-expert\s*\n(.+?)(?=^### |\Z)",
        section,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        return ""
    return match.group(1)


def _copy_real_ac(src: Path, dest_dir: Path) -> None:
    """Copy a real, on-disk AC YAML file byte-for-byte into `dest_dir`.

    Uses shutil.copy2 (verbatim bytes) rather than any re-serialisation, so
    the fixture is provably identical to the record the store actually
    contains -- never a hand-typed reproduction of it.
    """
    shutil.copy2(src, dest_dir / src.name)


# ---------------------------------------------------------------------------
# Test 1 — producer output vs. the verifier's documented parse rule
# (KI-ACD-002, primary defect).
# ---------------------------------------------------------------------------


class TestProducerOutputSatisfiesVerifierDocumentedParseRule(unittest.TestCase):
    """BO-2200c-5: round-trip the REAL generator's output through the
    verifier's DOCUMENTED Step 2 parse rule.

    RED before a fix: the producer's line ('[genre] path — constraint', zero
    pipes) is rejected by the verifier's documented algorithm ('<genre> |
    <target_path> | <content_constraint>', pipe-delimited) with the verifier's
    own 'malformed (no pipe-delimited target_path)' blocker.
    """

    def test_ac_bo2200c5_producer_output_satisfies_verifier_documented_parse_rule(
        self,
    ) -> None:
        # covers: BO-2200c-5
        """Run the REAL producer (_build_agent_contracts_section) over the
        REAL, on-disk TQ-400a-5 AC record (assigned_agent: documentation-
        expert; doc_links include docs/how-to/done-proof-enforcement.md;
        parent TQ-400a has documentation_triggers: [how-to,
        component-diagram]) and feed its ACTUAL output through the verifier's
        documented parse rule.

        KI-ACD-002: the producer's real output for this AC is
        '- [ ] AC-1: [how-to] docs/how-to/done-proof-enforcement.md — ...'
        (zero pipe characters). The verifier's documented algorithm requires
        pipe-delimited fields and emits `(status: blocker)` for a line with
        none. Every real doc-required ticket the generator produces fails
        this parse today.
        """
        with tempfile.TemporaryDirectory() as tmp:
            ac_root = Path(tmp)
            _copy_real_ac(_TQ_400A_PARENT_SRC, ac_root)
            _copy_real_ac(_TQ_400A_LEAF_SRC, ac_root)

            found = gen._find_ac_by_id(ac_root, _TQ_400A_LEAF_ID)
            self.assertIsNotNone(
                found, f"Fixture setup failed: {_TQ_400A_LEAF_ID} not found in {ac_root}"
            )
            _, leaf_ac = found

            # Real computed agents map for this AC's real change_target/
            # risk_surface (docs/internal) — confirmed to equal
            # {'documentation-expert': 'needed', ...} against the live
            # config/guardrail_gates.yaml and config/agent_registry.json.
            agents_map = gen._build_agents_map(
                "documentation-expert",
                change_targets=["docs"],
                risk_surface="internal",
                files_touched=["docs/how-to/done-proof-enforcement.md"],
                has_authored_test_spec=True,
            )
            self.assertEqual(
                agents_map.get("documentation-expert"),
                "needed",
                "Test precondition: documentation-expert must be 'needed' in the "
                f"real computed agents map for a docs/internal AC. Got: {agents_map}",
            )

            section = gen._build_agent_contracts_section(
                leaf_ac, _TQ_400A_LEAF_ID, agents_map, ac_root=ac_root
            )

        doc_expert_text = _extract_doc_expert_subsection(section)
        self.assertTrue(
            doc_expert_text,
            f"Fixture setup failed: no '### documentation-expert' subsection in "
            f"the real producer output.\nFull section:\n{section}",
        )

        try:
            required_docs = _verifier_parse_required_docs(doc_expert_text)
        except ValueError as exc:
            self.fail(
                "documentation-verifier's DOCUMENTED Step 2 parse rule rejected "
                "the REAL generator's output as malformed:\n"
                f"  {exc}\n\n"
                "Real producer output (### documentation-expert subsection):\n"
                f"{doc_expert_text}\n\n"
                "KI-ACD-002: the producer emits "
                "'- [ ] AC-N: [genre] path — constraint' (bracket + em-dash, "
                "zero pipe separators). The verifier's documented algorithm "
                "requires '<genre> | <target_path> | <content_constraint>' and "
                "blockers on any line with no pipe separators. Neither side has "
                "changed to agree with the other; every real doc-required "
                "ticket fails this parse."
            )

        self.assertIn(
            _TQ_400A_REAL_DOC_PATH,
            required_docs,
            f"The verifier's parsed target_path(s) {required_docs!r} do not "
            f"include the AC's real documented path {_TQ_400A_REAL_DOC_PATH!r}. "
            "A parse that 'succeeds' by accident (e.g. by mis-splitting the "
            "em-dash) but resolves the wrong path is equally a contract "
            "violation between producer and consumer."
        )


# ---------------------------------------------------------------------------
# Test 2 — empty parent documentation_triggers must suppress the contract
# line entirely, not degrade to an "(unspecified genre)" placeholder line
# (KI-ACD-002, third defect).
# ---------------------------------------------------------------------------


class TestEmptyParentTriggersEmitsNoContractLine(unittest.TestCase):
    """BO-2200c-5 / KI-ACD-002 (third occurrence): a parent L1's explicit,
    deliberate `documentation_triggers: []` must not produce a phantom
    documentation obligation.

    RED before a fix: `_resolve_genres_from_parent` treats the empty list
    identically to "parent could not be resolved" and returns
    ["(unspecified genre)"], which the caller renders as a real
    '- [ ] AC-N:' contract line anyway.
    """

    def test_ac_bo2200c5_empty_parent_documentation_triggers_emits_no_contract_line(
        self,
    ) -> None:
        # covers: BO-2200c-5
        """Run the REAL producer over the REAL, on-disk BP-900g (parent,
        documentation_triggers: [], with an explicit documentation_rationale
        stating this is deliberate: "Internal build-time deploy-integrity
        guardrail — surfaces only as a build error; no new user-facing
        capability or command is introduced.") and its real leaf BP-900g-1.

        agents_map forces documentation-expert: 'needed' directly (mirroring
        the established pattern in unit_tests/test_bo_2200c_3.py for isolating
        this exact genre-resolution code path) so the test targets
        `_resolve_genres_from_parent` / `_build_agent_contracts_section`
        specifically, independent of whether BP-900g-1's own change_target/
        risk_surface would otherwise route documentation-expert as needed.

        RED (current defect): the real output contains
        '- [ ] AC-1: [(unspecified genre)] ... — ...' — a documentation
        contract line for a document the governing parent AC explicitly says
        must not exist.
        """
        with tempfile.TemporaryDirectory() as tmp:
            ac_root = Path(tmp)
            _copy_real_ac(_BP_900G_PARENT_SRC, ac_root)
            _copy_real_ac(_BP_900G_LEAF_SRC, ac_root)

            found = gen._find_ac_by_id(ac_root, _BP_900G_LEAF_ID)
            self.assertIsNotNone(
                found, f"Fixture setup failed: {_BP_900G_LEAF_ID} not found in {ac_root}"
            )
            _, leaf_ac = found

            parent_found = gen._find_ac_by_id(ac_root, "BP-900g")
            self.assertIsNotNone(parent_found, "Fixture setup failed: BP-900g not found")
            _, parent_ac = parent_found
            self.assertEqual(
                parent_ac.get("documentation_triggers"),
                [],
                "Test precondition: BP-900g.yaml's real documentation_triggers "
                f"must be an empty list. Got: {parent_ac.get('documentation_triggers')!r}. "
                "If this fails, the real store record changed underneath this "
                "test, not the code under test.",
            )
            self.assertTrue(
                parent_ac.get("documentation_rationale"),
                "Test precondition: BP-900g.yaml must carry a "
                "documentation_rationale explaining why no documentation is "
                "required — this is the store's declared basis for treating "
                "the empty list as deliberate, not an omission.",
            )

            section = gen._build_agent_contracts_section(
                leaf_ac,
                _BP_900G_LEAF_ID,
                {"documentation-expert": "needed"},
                ac_root=ac_root,
            )

        self.assertNotIn(
            "(unspecified genre)",
            section,
            "The generator emitted an '(unspecified genre)' contract line for "
            "an AC whose parent L1 (BP-900g) DELIBERATELY declares "
            "documentation_triggers: [] — with an explicit "
            "documentation_rationale saying no new documentation is "
            "introduced. An empty list is the store's documented way of "
            "saying 'no documentation required', not a missing value to "
            "paper over with a placeholder.\n\n"
            f"Real producer output:\n{section}",
        )
        self.assertNotRegex(
            section,
            r"^- \[ \] AC-\d+:",
            "The generator must emit NO '### documentation-expert' contract "
            "checklist line at all when the parent's documentation_triggers "
            "is deliberately empty — not a placeholder line naming an "
            "'(unspecified genre)' document. A phantom contract line routes "
            "documentation-expert and documentation-verifier to enforce a "
            "document the governing AC says must not exist.\n\n"
            f"Real producer output:\n{section}",
        )


if __name__ == "__main__":
    unittest.main()
