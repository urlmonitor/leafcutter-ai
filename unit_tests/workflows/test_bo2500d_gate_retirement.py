"""
MODULE: unit_tests/workflows/test_bo2500d_gate_retirement.py
GOAL: Structural GUARD tests for the BO-2500d batch.

These are regression/guard tests — they assert structural properties that are
expected to hold by construction against the live fast lane. They are NOT
red-first TDD stubs; the properties they guard already exist in the on-disk
JS files. Their purpose is to catch regressions: if a future edit
inadvertently re-adds a forbidden opinion-only gate, introduces a second
delivery-bearing LLM verdict, lets a verdict reach the mark-done control
flow, or removes a mechanical gate, these tests will turn red.

BO-2400c-1-v migration note: templates/workflows-js/fast-lane-build.js was an
orphaned second fast-lane runner nothing invoked; it has been DELETED. Every
test below reads templates/workflows-js/fast-lane-ship.js — the lane that
actually runs — via the single _FAST_LANE_PATH constant.

ACs covered (all amended 2026-08-18/19 — see each AC's amended_by history in
docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/):
  BO-2500d-1   — The fast lane carries at most one delivery-bearing LLM
                  verdict (today: pr-reviewer), which may only withhold
                  delivery and can never confer done. No LLM validator agent
                  and no LLM fulfillment-gate agent are dispatched.
  BO-2500d-2   — The opinion-only gate agents remain present in the heavy pipeline
  BO-2500d-3   — The mechanical proof-of-done gates are the fast lane's
                  completion arbiters
  BO-2500d-1-i — Guard: dropping a mechanical gate, or letting an LLM verdict
                  substitute for one, is rejected; a veto-only reviewer with
                  all gates intact is explicitly accepted (encoded here as
                  structural presence/absence assertions per user directive
                  2026-07-21, amended 2026-08-18 to stop rejecting the
                  veto-only reviewer BO-2400f-11 shipped)

Files under test (REAL on-disk, not hand-typed):
  templates/workflows-js/fast-lane-ship.js
  templates/workflows-js/build-feature.js
  templates/workflows-js/build-ticket.js

Discrepancy note (BO-2500d-2):
  On the ac-authoring/fast-lane branch, build-feature.js and build-ticket.js
  phaseOrder contain 'pr-reviewer' and 'change-scope-reviewer' but do NOT yet
  contain 'ac-validator' or 'ac-fulfillment-gate'. Those were added in PR #375
  on a separate branch and have not been merged here. The tests for d-2 assert
  only what IS present (pr-reviewer + change-scope-reviewer). The absence of
  ac-validator and ac-fulfillment-gate from the heavy phaseOrder on this branch
  is a cross-branch artifact, not a defect in the fast-lane work itself.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve the scripts under test
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FAST_LANE_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"
_BUILD_FEATURE_PATH = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
_BUILD_TICKET_PATH = _REPO_ROOT / "templates" / "workflows-js" / "build-ticket.js"

# fast-lane-build.js (the orphan _FAST_LANE_PATH used to point at) has been
# deleted (BO-2400c-1-v). _FAST_LANE_PATH above now points at the live lane
# for every test in this module. This second constant is kept only so
# test_ac_d2_fast_lane_has_no_phase_order_array's own historical migration
# docstring (which names it explicitly) still resolves to the same file.
_FAST_LANE_SHIP_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"


# ---------------------------------------------------------------------------
# Helpers (pure — no I/O side-effects, safe to call from multiple tests)
# ---------------------------------------------------------------------------


def _read_file(path: Path) -> str:
    """Return file content as a string, or empty string if absent or unreadable."""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _extract_phase_order_text(content: str) -> str:
    """Extract the body of the phaseOrder array from JS content.

    Searches for ``const phaseOrder = [...]`` and returns the text between
    the brackets (excluding the brackets themselves).  Returns ``""`` when no
    such declaration is found (e.g. fast-lane-build.js, which does not define
    a phaseOrder).

    Args:
        content: Raw JS file content.

    Returns:
        The array body string, or ``""`` if the declaration is absent.
    """
    match = re.search(
        r"const phaseOrder\s*=\s*\[([^\]]*)\]",
        content,
        re.DOTALL,
    )
    if match:
        return match.group(1)
    return ""


def _extract_agenttype_values(content: str) -> list[str]:
    """Extract all ``agentType`` string values from non-comment JS lines.

    Specifically matches ``agentType: "..."`` or ``agentType: '...'``
    patterns, skipping pure line-comment and block-comment lines.

    Args:
        content: Raw JS file content.

    Returns:
        List of string values assigned to ``agentType`` keys.
    """
    values: list[str] = []
    for line in content.split("\n"):
        stripped = line.strip()
        # Skip pure comment lines
        if (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
        ):
            continue
        for m in re.finditer(r'agentType\s*:\s*["\']([^"\']+)["\']', stripped):
            values.append(m.group(1))
    return values


def _strip_comment_lines(content: str) -> str:
    """Return content with pure comment lines removed, preserving line order.

    Ported from unit_tests/workflows/test_bo2400a_runner_structure.py's helper
    of the same name (BO-2500d migration to the live fast-lane-ship.js runner).
    Raw `.find()` / regex positions computed on the RESULT reflect the actual
    code sequence, rather than being skewed by a header/JSDoc comment that
    mentions an implementation detail (e.g. 'python-coder' in the file's own
    architecture summary) out of real execution order.

    Args:
        content: Raw JS file content.

    Returns:
        The content with comment-only lines removed, newline-joined.
    """
    kept = []
    for line in content.split("\n"):
        stripped = line.strip()
        if (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
        ):
            continue
        kept.append(line)
    return "\n".join(kept)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class _JsFileTestBase(unittest.TestCase):
    """Shared helper: assert a JS file exists and return its content."""

    def _require_file(self, path: Path, label: str) -> str:
        """Assert the JS file exists and is non-empty; return its content.

        Args:
            path:  Absolute path to the JS file.
            label: Human-readable label used in assertion messages.

        Returns:
            File content as a string.
        """
        self.assertTrue(
            path.exists(),
            f"{label} does not exist at {path}. "
            "This structural guard test cannot run without the target file.",
        )
        content = _read_file(path)
        self.assertGreater(
            len(content.strip()),
            50,
            f"{label} is empty or nearly empty — the file exists but has no "
            "substantial content.",
        )
        return content


# ---------------------------------------------------------------------------
# TestFastLaneExcludesOpinionOnlyGates — BO-2500d-1
# ---------------------------------------------------------------------------


class TestFastLaneExcludesOpinionOnlyGates(_JsFileTestBase):
    """BO-2500d-1: the fast lane carries at most one delivery-bearing LLM verdict.

    AMENDMENT (2026-08-18/19, see BO-2500d-1.yaml amended_by): the original rule
    tested here ("no LLM review agent at all") was retired because BO-2400f-11
    (PR #485, confirmed intended by BrainCandy) deliberately put pr-reviewer into
    the fast lane at Phase 4.5. The amended criteria forbid an LLM VALIDATOR agent
    and an LLM FULFILLMENT-GATE agent, and permit AT MOST ONE LLM agent whose
    verdict bears on whether the change is delivered — today that is pr-reviewer,
    and its verdict may only withhold delivery, never confer done. The only
    completion arbiters are the mechanical proof-of-done gates (verified in
    BO-2500d-3 tests).

    These are regression guards — the property holds by construction.  If they
    fail, either a forbidden opinion-only agent (validator / fulfillment-gate /
    change-scope-reviewer) was re-added, a second delivery-bearing verdict was
    introduced, or the reviewer's verdict became reachable from the mark-done
    control flow.
    """

    # The two agent kinds BO-2500d-1 explicitly forbids outright (LLM validator,
    # LLM fulfillment-gate), plus change-scope-reviewer, a third opinion-only gate
    # historically excluded and still absent (see the individual
    # test_ac_d1_fast_lane_excludes_* tests below, which remain green and
    # untouched by this amendment).
    NON_REVIEWER_OPINION_AGENTS = (
        "ac-validator",
        "ac-fulfillment-gate",
        "change-scope-reviewer",
    )
    # The one LLM agent BO-2500d-1 permits to carry a delivery-bearing verdict —
    # confirmed intended: pr-reviewer at Phase 4.5 of fast-lane-ship.js (PR #485).
    DELIVERY_VERDICT_AGENT = "pr-reviewer"

    def test_ac_d1_pr_reviewer_is_the_sole_delivery_verdict_and_cannot_confer_done(
        self,
    ) -> None:
        # covers: BO-2500d-1
        # angle: criterion
        """RENAMED from test_ac_d1_fast_lane_excludes_pr_reviewer.

        The retired assertion ("fast-lane-ship.js must not reference
        'pr-reviewer'") tested the pre-amendment rule. BO-2500d-1 was amended
        2026-08-18 to permit AT MOST ONE LLM agent whose verdict bears on
        delivery, and the live lane confirmed-intentionally dispatches exactly
        that one — pr-reviewer, at Phase 4.5 (PR #485). This test asserts the
        amended property directly, in two parts:

        1. Exactly one agent from the opinion/verdict family (pr-reviewer,
           ac-validator, ac-fulfillment-gate, change-scope-reviewer) is
           dispatched, and it is pr-reviewer — proving "at most one" as an
           equality against the confirmed-intended live shape.
        2. The LOAD-BEARING HALF: no identifier derived from that verdict
           (reviewResult / reviewVerdictUsable / reviewHighFindings /
           reviewMediumFindings / reviewLowSuppressedCount) is referenced
           anywhere in the Commit-phase code block that constructs and issues
           the mark-done dispatch. This is the structural proof that the
           verdict can only withhold delivery (by returning early, before
           Phase 5) and can never be read to CONFER done.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-ship.js")
        code_only = _strip_comment_lines(content)

        opinion_family = self.NON_REVIEWER_OPINION_AGENTS + (
            self.DELIVERY_VERDICT_AGENT,
        )
        agent_types = _extract_agenttype_values(code_only)
        opinion_dispatches = [at for at in agent_types if at in opinion_family]
        self.assertEqual(
            opinion_dispatches,
            [self.DELIVERY_VERDICT_AGENT],
            "fast-lane-ship.js must dispatch EXACTLY ONE agent from the "
            f"opinion/verdict family {opinion_family}, and it must be "
            f"'{self.DELIVERY_VERDICT_AGENT}'. Found: {opinion_dispatches} "
            "(BO-2500d-1: at most one LLM verdict bears on delivery).",
        )

        commit_phase_match = re.search(
            r'phase\("Commit"\);(.*?)phase\("Pull Request"\)',
            code_only,
            re.DOTALL,
        )
        if commit_phase_match is None:
            self.fail(
                "Could not locate the Commit-phase block (between "
                'phase("Commit") and phase("Pull Request")) in fast-lane-ship.js '
                "— verify the phase markers still exist (BO-2500d-1)."
            )
        commit_phase_block = commit_phase_match.group(1)
        verdict_identifiers = (
            "reviewResult",
            "reviewVerdictUsable",
            "reviewHighFindings",
            "reviewMediumFindings",
            "reviewLowSuppressedCount",
        )
        leaked = [
            ident
            for ident in verdict_identifiers
            if re.search(rf"\b{ident}\b", commit_phase_block)
        ]
        self.assertEqual(
            leaked,
            [],
            f"The Commit-phase block (mark-done + commit dispatch) must NEVER "
            f"reference a review-verdict-derived identifier. Found: {leaked}. "
            "An LLM verdict may withhold delivery (by halting BEFORE this "
            "block, in the Review phase guards) but must never be read here "
            "to confer done (BO-2500d-1).",
        )

    def test_ac_d1_fast_lane_excludes_ac_validator(self) -> None:
        # covers: BO-2500d-1
        """fast-lane-build.js must not reference 'ac-validator'."""
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertNotIn(
            "ac-validator",
            content,
            "fast-lane-build.js must NOT reference 'ac-validator' — "
            "it is an opinion-only LLM gate excluded from the fast lane (BO-2500d-1).",
        )

    def test_ac_d1_fast_lane_excludes_ac_fulfillment_gate(self) -> None:
        # covers: BO-2500d-1
        """fast-lane-build.js must not reference 'ac-fulfillment-gate'."""
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertNotIn(
            "ac-fulfillment-gate",
            content,
            "fast-lane-build.js must NOT reference 'ac-fulfillment-gate' — "
            "it is an opinion-only LLM gate excluded from the fast lane (BO-2500d-1).",
        )

    def test_ac_d1_fast_lane_excludes_change_scope_reviewer(self) -> None:
        # covers: BO-2500d-1
        """fast-lane-build.js must not reference 'change-scope-reviewer'."""
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertNotIn(
            "change-scope-reviewer",
            content,
            "fast-lane-build.js must NOT reference 'change-scope-reviewer' — "
            "it is an opinion-only gate excluded from the fast lane (BO-2500d-1).",
        )

    def test_ac_d1_no_non_reviewer_opinion_agent_by_name(self) -> None:
        # covers: BO-2500d-1
        # angle: criterion
        """RENAMED from test_ac_d1_no_opinion_only_agent_by_name.

        The retired version combined all four opinion-only agents — including
        pr-reviewer — into one omnibus "must be absent" check. Under the
        amendment pr-reviewer is the one permitted delivery-bearing verdict,
        so it is deliberately excluded from this omnibus; its own presence and
        load-bearing constraints are covered by
        test_ac_d1_pr_reviewer_is_the_sole_delivery_verdict_and_cannot_confer_done
        above. This omnibus now covers exactly the three agents the amended
        criteria still forbid outright: no LLM validator agent, no LLM
        fulfillment-gate agent, and (retained) no change-scope-reviewer.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-ship.js")
        present = [ag for ag in self.NON_REVIEWER_OPINION_AGENTS if ag in content]
        self.assertEqual(
            present,
            [],
            f"fast-lane-ship.js must contain NONE of the still-forbidden "
            f"opinion-only agents. Found: {present} (BO-2500d-1). "
            "Remove them — only the mechanical gates and the single "
            "pr-reviewer verdict are permitted in the fast lane.",
        )

    def test_ac_d1_no_validator_agenttype_and_at_most_one_review_agenttype(
        self,
    ) -> None:
        # covers: BO-2500d-1
        # angle: criterion
        """RENAMED from test_ac_d1_no_generic_review_or_validator_agenttype.

        The retired assertion forbade ANY agentType containing 'review' or
        'validator'. Under the amendment, 'validator' is still forbidden by
        role/kind (the AC's own wording: excluded by role, not hard-coded
        name), but 'review' can no longer be a blanket exclusion — pr-reviewer
        IS a 'review'-kind agentType and is now the one permitted verdict.
        The property worth proving instead: no 'validator'-kind agentType
        exists at all, and at most one 'review'-kind agentType is dispatched
        (catching a second reviewer/opinion agent added under a novel name,
        even one this file's hard-coded name lists do not enumerate).
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-ship.js")
        agent_types = _extract_agenttype_values(content)
        validator_dispatches = [at for at in agent_types if "validator" in at.lower()]
        self.assertEqual(
            validator_dispatches,
            [],
            f"fast-lane-ship.js must NOT dispatch any agent whose agentType "
            f"contains 'validator'. Found: {validator_dispatches} (BO-2500d-1).",
        )
        review_dispatches = [at for at in agent_types if "review" in at.lower()]
        self.assertEqual(
            review_dispatches,
            [self.DELIVERY_VERDICT_AGENT],
            "fast-lane-ship.js must dispatch AT MOST ONE agentType containing "
            f"'review', and it must be '{self.DELIVERY_VERDICT_AGENT}'. Found: "
            f"{review_dispatches}. A second review-kind agentType (even under "
            "a novel name) would violate BO-2500d-1's 'at most one delivery-"
            "bearing verdict' rule.",
        )

    def test_ac_d1_only_non_reviewer_opinion_agenttypes_are_absent(self) -> None:
        # covers: BO-2500d-1
        # angle: criterion
        """RENAMED from test_ac_d1_only_non_opinion_agenttypes_dispatched.

        The retired version treated pr-reviewer as forbidden alongside the
        other three opinion-only agents, so it failed once pr-reviewer's
        dispatch was (correctly) present. Under the amendment, pr-reviewer is
        the one permitted delivery-bearing verdict — see
        test_ac_d1_pr_reviewer_is_the_sole_delivery_verdict_and_cannot_confer_done
        for its own dedicated coverage (presence AND the load-bearing
        never-confers-done half). This test now asserts only that none of the
        three STILL-forbidden opinion-only agentTypes (ac-validator,
        ac-fulfillment-gate, change-scope-reviewer) is dispatched.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-ship.js")
        agent_types = _extract_agenttype_values(content)
        forbidden_set = set(self.NON_REVIEWER_OPINION_AGENTS)
        violations = [at for at in agent_types if at in forbidden_set]
        self.assertEqual(
            violations,
            [],
            f"fast-lane-ship.js agentType dispatches include still-forbidden "
            f"opinion-only agents: {violations}. Only mechanical gates, coder "
            f"agentTypes, and the single pr-reviewer verdict are permitted in "
            f"the fast lane (BO-2500d-1).",
        )


# ---------------------------------------------------------------------------
# TestHeavyPipelineRetainsGates — BO-2500d-2
# ---------------------------------------------------------------------------


class TestHeavyPipelineRetainsGates(_JsFileTestBase):
    """BO-2500d-2: build-feature.js and build-ticket.js still contain opinion-only gates.

    Removing the opinion-only agents from the fast lane (BO-2500d-1) must NOT
    remove them from the heavy pipeline.  This test class guards that the heavy
    phaseOrder retains pr-reviewer and change-scope-reviewer.

    Discrepancy note: on this branch (ac-authoring/fast-lane) neither
    build-feature.js nor build-ticket.js includes 'ac-validator' or
    'ac-fulfillment-gate' in phaseOrder — those were added on a separate branch
    (PR #375).  The tests here assert only what IS present on this branch.
    """

    def _get_phase_order_text(self, content: str, label: str) -> str:
        """Extract the phaseOrder array body and assert it is non-empty."""
        text = _extract_phase_order_text(content)
        self.assertGreater(
            len(text),
            0,
            f"{label}: could not extract phaseOrder array.  "
            "Check that the file defines 'const phaseOrder = [...]'.",
        )
        return text

    def test_ac_d2_build_feature_retains_pr_reviewer(self) -> None:
        # covers: BO-2500d-2
        """build-feature.js phaseOrder must still contain 'pr-reviewer'.

        Removing pr-reviewer from the fast lane (BO-2500d-1) must not remove it
        from the heavy pipeline.  This test guards that the heavy phaseOrder
        retains the LLM review gate.

        If this test FAILS, pr-reviewer was removed from build-feature.js
        phaseOrder — restore it; the heavy path must keep LLM review.
        """
        content = self._require_file(_BUILD_FEATURE_PATH, "build-feature.js")
        phase_order_text = self._get_phase_order_text(content, "build-feature.js")
        self.assertIn(
            '"pr-reviewer"',
            phase_order_text,
            "build-feature.js phaseOrder must retain '\"pr-reviewer\"' — "
            "the heavy pipeline must not lose the LLM review gate (BO-2500d-2).",
        )

    def test_ac_d2_build_ticket_retains_pr_reviewer(self) -> None:
        # covers: BO-2500d-2
        """build-ticket.js phaseOrder must still contain 'pr-reviewer'."""
        content = self._require_file(_BUILD_TICKET_PATH, "build-ticket.js")
        phase_order_text = self._get_phase_order_text(content, "build-ticket.js")
        self.assertIn(
            '"pr-reviewer"',
            phase_order_text,
            "build-ticket.js phaseOrder must retain '\"pr-reviewer\"' — "
            "the heavy pipeline must not lose the LLM review gate (BO-2500d-2).",
        )

    def test_ac_d2_build_feature_retains_change_scope_reviewer(self) -> None:
        # covers: BO-2500d-2
        """build-feature.js phaseOrder must still contain 'change-scope-reviewer'."""
        content = self._require_file(_BUILD_FEATURE_PATH, "build-feature.js")
        phase_order_text = self._get_phase_order_text(content, "build-feature.js")
        self.assertIn(
            '"change-scope-reviewer"',
            phase_order_text,
            "build-feature.js phaseOrder must retain '\"change-scope-reviewer\"' — "
            "the heavy pipeline must keep this scope-integrity gate (BO-2500d-2).",
        )

    def test_ac_d2_build_ticket_retains_change_scope_reviewer(self) -> None:
        # covers: BO-2500d-2
        """build-ticket.js phaseOrder must still contain 'change-scope-reviewer'."""
        content = self._require_file(_BUILD_TICKET_PATH, "build-ticket.js")
        phase_order_text = self._get_phase_order_text(content, "build-ticket.js")
        self.assertIn(
            '"change-scope-reviewer"',
            phase_order_text,
            "build-ticket.js phaseOrder must retain '\"change-scope-reviewer\"' — "
            "the heavy pipeline must keep this scope-integrity gate (BO-2500d-2).",
        )

    def test_ac_d2_fast_lane_has_no_phase_order_array(self) -> None:
        # covers: BO-2500d-2
        """fast-lane-ship.js must NOT define a phaseOrder array.

        Migration note (BO-2400c-1-v): this is the ONE method in this class
        re-pointed at the live lane (templates/workflows-js/fast-lane-ship.js).
        Every OTHER `_FAST_LANE_PATH` user in this file covers BO-2500d-1,
        -1-i, or -3, which are `work_status: in_progress` (self-corrected
        2026-08-19) — not `done`. BO-2500d-1 in particular asserts the fast
        lane contains NO LLM review agent, but fast-lane-ship.js deliberately
        dispatches `pr-reviewer` at Phase 4.5 (shipped in PR #485 on the
        user's explicit instruction, see its own "Review" phase and
        `agentType: "pr-reviewer"`). Re-pointing those other methods would
        make them fail on a deliberate, intentional design decision — so they
        are left untouched, still pointed at the orphan, and are expected to
        go on being red/broken once the orphan is deleted (tracked
        separately; not this ticket's scope). Only `work_status: done`
        BO-2500d-2 is migrated here, and confirmed by direct grep during
        migration that fast-lane-ship.js contains no `phaseOrder` substring
        at all.

        The two phase-order sets (fast lane vs. heavy pipeline) must be
        independently defined so that a change to one cannot silently mutate the
        other (BO-2500d-2).  The fast lane does not define a phaseOrder array —
        its dispatches are inlined directly.  If a phaseOrder were added to
        fast-lane-ship.js it could be accidentally shared with or confused for
        the heavy pipeline's set.
        """
        content = self._require_file(_FAST_LANE_SHIP_PATH, "fast-lane-ship.js")
        phase_order_text = _extract_phase_order_text(content)
        self.assertEqual(
            phase_order_text,
            "",
            "fast-lane-ship.js must NOT define a 'const phaseOrder = [...]' "
            "array — its phase sequence is inlined (flat dispatches), "
            "independently of the heavy pipeline's phaseOrder.  A shared "
            "phaseOrder would couple the two pipelines (BO-2500d-2).",
        )

    def test_ac_d2_heavy_pipeline_pr_reviewer_before_commit(self) -> None:
        # covers: BO-2500d-2
        """In both heavy-pipeline files, 'pr-reviewer' appears before 'commit' in phaseOrder.

        This guards the ordering contract: the LLM review gate must run before
        the commit phase in the heavy pipeline.  If the phaseOrder is rearranged
        so that commit precedes pr-reviewer, this test catches it.
        """
        for path, label in [
            (_BUILD_FEATURE_PATH, "build-feature.js"),
            (_BUILD_TICKET_PATH, "build-ticket.js"),
        ]:
            content = self._require_file(path, label)
            phase_order_text = self._get_phase_order_text(content, label)
            pr_pos = phase_order_text.find('"pr-reviewer"')
            commit_pos = phase_order_text.find('"commit"')
            if pr_pos == -1 or commit_pos == -1:
                # Individual presence tests above will already have caught this.
                continue
            self.assertLess(
                pr_pos,
                commit_pos,
                f"{label}: 'pr-reviewer' must appear BEFORE 'commit' in phaseOrder — "
                "the review gate must run before commit in the heavy pipeline "
                "(BO-2500d-2).",
            )


# ---------------------------------------------------------------------------
# TestFastLaneMechanicalGatesPresent — BO-2500d-3
# ---------------------------------------------------------------------------


class TestFastLaneMechanicalGatesPresent(_JsFileTestBase):
    """BO-2500d-3: fast-lane-build.js has the mechanical proof-of-done gates.

    The deterministic proof-of-done gates (red-baseline verification,
    green+coverage verification) must be present as the completion arbiters
    in the fast lane.
    """

    RED_BASELINE_PATTERNS = (
        "verify_red_baseline",
        "verifyRedBaseline",
        "red_baseline",
        "redBaseline",
    )
    GREEN_COVERAGE_PATTERNS = (
        "verify_green_and_coverage",
        "verifyGreenAndCoverage",
        "green_and_coverage",
        "greenAndCoverage",
    )

    def test_ac_d3_fast_lane_references_verify_red_baseline(self) -> None:
        # covers: BO-2500d-3
        """fast-lane-build.js must reference the verify_red_baseline gate.

        The red-baseline gate (BO-2400a-3) is one of the two mechanical
        proof-of-done arbiters that stand in for the removed opinion-only gates
        in the fast lane.  Its presence is required by BO-2500d-3.

        If this test FAILS, the red-baseline mechanical gate was removed from
        fast-lane-build.js — restore it before removing any opinion-only gate.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        has_ref = any(p in content for p in self.RED_BASELINE_PATTERNS)
        self.assertTrue(
            has_ref,
            "fast-lane-build.js must reference the red-baseline mechanical gate "
            f"using one of: {', '.join(self.RED_BASELINE_PATTERNS)} (BO-2500d-3).",
        )

    def test_ac_d3_fast_lane_references_verify_green_and_coverage(self) -> None:
        # covers: BO-2500d-3
        """fast-lane-build.js must reference the verify_green_and_coverage gate.

        The green+coverage gate (BO-2400a-4) is the second mechanical
        proof-of-done arbiter that stands in for the removed opinion-only gates.
        Its presence is required by BO-2500d-3.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        has_ref = any(p in content for p in self.GREEN_COVERAGE_PATTERNS)
        self.assertTrue(
            has_ref,
            "fast-lane-build.js must reference the green+coverage mechanical gate "
            f"using one of: {', '.join(self.GREEN_COVERAGE_PATTERNS)} (BO-2500d-3).",
        )

    def test_ac_d3_both_mechanical_gates_present(self) -> None:
        # covers: BO-2500d-3
        """Both mechanical proof-of-done gates must be present in fast-lane-build.js.

        The fast lane requires BOTH the red-baseline gate AND the green+coverage
        gate as its completion arbiters (BO-2500d-3).  Having only one is
        insufficient — the second must also be present.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        has_red = any(p in content for p in self.RED_BASELINE_PATTERNS)
        has_green = any(p in content for p in self.GREEN_COVERAGE_PATTERNS)
        self.assertTrue(
            has_red and has_green,
            f"fast-lane-build.js must reference BOTH mechanical gates. "
            f"red_baseline present: {has_red}, "
            f"green_and_coverage present: {has_green}. "
            "Both are required as completion arbiters of the fast lane (BO-2500d-3).",
        )

    def test_ac_d3_red_baseline_gate_appears_before_coder(self) -> None:
        # covers: BO-2500d-3
        # angle: criterion
        """verify_red_baseline must appear before the coder dispatch in fast-lane-ship.js.

        The sequencing contract: test-writer dispatch -> red-baseline gate ->
        coder dispatch -> green+coverage gate.  The coder must NOT be dispatched
        before the red-baseline check has been defined/referenced.

        FIX (was comparing RAW string positions, which false-failed on
        fast-lane-ship.js for two independent decoy reasons):

        1. `python-coder` appears in real, non-comment code BEFORE the
           red-baseline gate at least twice for reasons unrelated to the
           actual Phase 4 coder dispatch: the `RELEASE_EXECUTOR_AGENT_TYPE =
           "python-coder"` constant, and the earlier Resolve-phase
           context-bundle dispatch (`agentType: "python-coder"` at the
           context-bundle call site). A bare substring search for
           "python-coder" finds one of these decoys, not the real dispatch.
        2. The file's header JSDoc also mentions both 'python-coder' and
           'verify_red_baseline' in its architecture summary, in an order
           that need not match real control flow.

        Fixed the same way test_bo2400a_runner_structure.py's sibling test
        fixes it: strip comment-only lines via `_strip_comment_lines()` so
        JSDoc/header mentions cannot participate, and anchor the coder
        position on `label: "coder-connected"` — the unique `label:` field on
        the ONE agent() call that is the real Phase 4 coder dispatch (see
        `agentType: "python-coder"` / `label: "coder-connected"` together at
        that call site) — rather than a bare 'python-coder' substring that
        also matches the release-executor constant and the context-bundle
        dispatch.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-ship.js")
        code_only = _strip_comment_lines(content)
        red_positions = [
            code_only.find(p)
            for p in self.RED_BASELINE_PATTERNS
            if code_only.find(p) != -1
        ]
        coder_dispatch_anchor = 'label: "coder-connected"'
        coder_pos = code_only.find(coder_dispatch_anchor)
        if not red_positions or coder_pos == -1:
            # Missing presence tests above already catch this.
            return
        first_red_pos = min(red_positions)
        self.assertLess(
            first_red_pos,
            coder_pos,
            "The red-baseline gate reference must appear (in real, non-comment "
            "control flow) BEFORE the coder agent dispatch "
            f"({coder_dispatch_anchor!r}) in fast-lane-ship.js — the coder "
            "must not run before the red baseline is enforced (BO-2500d-3).",
        )

    def test_ac_d3_green_coverage_gate_appears_after_coder(self) -> None:
        # covers: BO-2500d-3
        """The greenCoverageInvocation variable must be defined after the coder agentType dispatch.

        The sequencing contract: coder dispatch → green+coverage gate.
        The green+coverage invocation string is constructed AFTER the coder
        agent() call in fast-lane-build.js, confirming the gate runs post-coder.

        Uses code-only anchors to avoid false hits in the file header comment:
          - coder position: ``agentType: "python-coder"`` (the actual dispatch)
          - gate position:  ``greenCoverageInvocation`` (the const variable definition)

        Both strings appear only in non-comment code sections, so
        ``content.find()`` reliably finds the code-level positions.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        # Use the agentType dispatch string as the coder anchor — it appears
        # only in the actual agent() call, not in comments or meta.phases.
        coder_anchor = 'agentType: "python-coder"'
        # Anchor on the green+coverage gate RESULT being consumed as an arbiter.
        # In the corrected runner the invocation string is embedded in the coder
        # prompt (so it is necessarily defined BEFORE the dispatch); the gate acts
        # as an arbiter AFTER the coder via a guard on its result (coverage_ok).
        # Consumption-after-coder is the property BO-2500d-3 actually requires —
        # source-definition position of the invocation string is not meaningful.
        gate_anchor = "coverage_ok"
        coder_pos = content.find(coder_anchor)
        # Search for the gate-result reference AFTER the coder dispatch, so an
        # early doc/meta mention of coverage_ok cannot satisfy the arbiter check.
        gate_pos = content.find(gate_anchor, coder_pos) if coder_pos != -1 else -1
        if coder_pos == -1:
            self.fail(
                "Could not find coder dispatch anchor "
                f"'{coder_anchor}' in fast-lane-build.js — "
                "verify the file still dispatches python-coder (BO-2500d-3)."
            )
        if gate_pos == -1:
            self.fail(
                f"Could not find gate-result anchor '{gate_anchor}' in fast-lane-build.js — "
                "verify the green+coverage gate result is consumed as an arbiter "
                "(BO-2500d-3)."
            )
        self.assertGreater(
            gate_pos,
            coder_pos,
            f"'{gate_anchor}' (pos {gate_pos}) must appear AFTER the coder "
            f"dispatch '{coder_anchor}' (pos {coder_pos}) in fast-lane-build.js — "
            "the green+coverage gate result must be consumed as an arbiter after "
            "the coder runs (BO-2500d-3).",
        )

    def test_ac_d3_pr_body_names_both_mechanical_gates_as_delivery_arbiters(
        self,
    ) -> None:
        # covers: BO-2500d-3
        # angle: criterion
        """RENAMED from test_ac_d3_gates_passed_summary_names_both_mechanical_gates.

        DECISION (recorded honestly rather than inventing a passing target):
        fast-lane-ship.js has NO `gates_passed` array return field —
        grep-confirmed absent from the whole file. Each gate FAILURE path
        instead returns a singular `gate: "<name>"` field naming only the one
        gate that did NOT pass (e.g. `gate: "verify_red_baseline"` at the
        red-baseline halt, `gate: "verify_green_and_coverage"` at the
        coverage halt) — there is no success-path summary array naming both
        gates together as a machine-readable list. Re-aiming the old
        assertion at a `gates_passed` string that does not exist would be
        exactly the prohibited "relax the assertion / assert a shape the code
        doesn't have" move.

        The real, observable place both mechanical gate names ARE surfaced
        together — as the substance of what gated a delivered change — is the
        `prBody` string fast-lane-ship.js assembles in the Pull Request phase
        (the artifact that ships to the human reviewing the change):
        "Gates: verify_red_baseline + verify_green_and_coverage + pr-reviewer
        (all green)". This test pins that real string instead.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-ship.js")
        code_only = _strip_comment_lines(content)
        self.assertNotIn(
            "gates_passed",
            code_only,
            "fast-lane-ship.js unexpectedly now defines a 'gates_passed' "
            "field — if a structured array now exists, assert against IT "
            "instead of prBody; this failure means the DECISION recorded in "
            "this test's docstring is stale and the test needs updating.",
        )
        pr_body_match = re.search(
            r"const prBody\s*=(.*?)const prResult", code_only, re.DOTALL
        )
        if pr_body_match is None:
            self.fail(
                "Could not locate the 'const prBody = ... const prResult' "
                "assignment in fast-lane-ship.js — verify the Pull Request phase "
                "still builds this string (BO-2500d-3)."
            )
        pr_body_text = pr_body_match.group(1)
        self.assertIn(
            "verify_red_baseline",
            pr_body_text,
            "prBody must name 'verify_red_baseline' as one of the gates that "
            "gated this delivered change (BO-2500d-3).",
        )
        self.assertIn(
            "verify_green_and_coverage",
            pr_body_text,
            "prBody must name 'verify_green_and_coverage' as one of the "
            "gates that gated this delivered change (BO-2500d-3).",
        )


# ---------------------------------------------------------------------------
# TestFastLaneMechanicalGateRetentionGuard — BO-2500d-1-i
# ---------------------------------------------------------------------------


class TestFastLaneMechanicalGateRetentionGuard(_JsFileTestBase):
    """BO-2500d-1-i: guard that dropping a mechanical gate is caught immediately.

    Per BO-2500d-1-i, removing an opinion-only gate before its mechanical
    replacement exists must be rejected.  These tests enforce that invariant
    from the structural side: as long as BOTH mechanical gates are present in
    fast-lane-build.js AND the opinion-only agents are absent, the precondition
    is satisfied.

    If a future edit removes a mechanical gate (making it impossible to enforce
    the precondition), these tests fail — signalling that the removal was
    made before a replacement was established, which is exactly what BO-2500d-1-i
    prohibits.

    User directive 2026-07-21: encode BO-2500d-1-i as structural presence
    assertions on fast-lane-build.js (not as behavioral tests of a validator
    function, which does not yet exist).
    """

    def test_ac_d1i_guard_verify_red_baseline_not_removed(self) -> None:
        # covers: BO-2500d-1-i
        """Guard: verify_red_baseline must not be removed from fast-lane-build.js.

        If this test FAILS, the red-baseline mechanical gate has been dropped
        from fast-lane-build.js.  Per BO-2500d-1-i, a mechanical gate may not
        be removed before its replacement is present and validated.  Restore
        verify_red_baseline or establish a replacement gate before removing it.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertIn(
            "verify_red_baseline",
            content,
            "GUARD (BO-2500d-1-i): 'verify_red_baseline' was removed from "
            "fast-lane-build.js.  A mechanical gate may not be dropped before "
            "its replacement is established and present in the fast lane.  "
            "Restore it or add its replacement first.",
        )

    def test_ac_d1i_guard_verify_green_and_coverage_not_removed(self) -> None:
        # covers: BO-2500d-1-i
        """Guard: verify_green_and_coverage must not be removed from fast-lane-build.js.

        If this test FAILS, the green+coverage mechanical gate has been dropped.
        Per BO-2500d-1-i, restore it or establish a replacement before removing.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertIn(
            "verify_green_and_coverage",
            content,
            "GUARD (BO-2500d-1-i): 'verify_green_and_coverage' was removed from "
            "fast-lane-build.js.  A mechanical gate may not be dropped before "
            "its replacement is established and present in the fast lane.  "
            "Restore it or add its replacement first.",
        )

    def test_ac_d1i_guard_both_mechanical_gates_present(self) -> None:
        # covers: BO-2500d-1-i
        """Guard: both mechanical gates must be simultaneously present.

        The 'removal before replacement' prohibition (BO-2500d-1-i) requires
        that whenever any opinion-only gate is absent from the fast lane, its
        mechanical replacement IS present.  This test asserts the positive
        form: both mechanical gates (red-baseline, green+coverage) are present.

        Combined with the opinion-only absence tests (BO-2500d-1), these two
        sets together enforce the full BO-2500d-1-i invariant structurally.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        red_patterns = (
            "verify_red_baseline",
            "verifyRedBaseline",
            "red_baseline",
            "redBaseline",
        )
        green_patterns = (
            "verify_green_and_coverage",
            "verifyGreenAndCoverage",
            "green_and_coverage",
            "greenAndCoverage",
        )
        has_red = any(p in content for p in red_patterns)
        has_green = any(p in content for p in green_patterns)
        self.assertTrue(
            has_red and has_green,
            f"GUARD (BO-2500d-1-i): fast-lane-build.js must contain BOTH "
            f"mechanical gates simultaneously. "
            f"red_baseline present: {has_red}, "
            f"green_and_coverage present: {has_green}. "
            "Having only one means the other was removed before a replacement "
            "was established — this is exactly what BO-2500d-1-i prohibits.",
        )

    def test_ac_d1i_guard_non_reviewer_opinion_gates_not_reintroduced(self) -> None:
        # covers: BO-2500d-1-i
        # angle: criterion
        """RENAMED from test_ac_d1i_guard_opinion_gates_not_reintroduced.

        The retired version included pr-reviewer in the forbidden set, which
        made this guard fail on the live lane's own intentional design (PR
        #485). BO-2500d-1-i was amended 2026-08-18 to explicitly state that
        rejecting the veto-only reviewer as such is over-broad: "what is
        rejected is substitution, not review." The guard this test encodes
        must therefore only watch for the two agent kinds the amended AC
        forbids outright (LLM validator, LLM fulfillment-gate) plus the third
        opinion-only gate historically excluded (change-scope-reviewer) — NOT
        pr-reviewer, whose presence and non-substitution behaviour is guarded
        separately (see TestFastLaneExcludesOpinionOnlyGates above and the
        commit-phase leak check in particular).

        Together with the 'both mechanical gates present' guard, these two
        tests enforce the BO-2500d-1-i invariant bidirectionally:
          - the still-forbidden opinion-only gates are absent from the fast lane
          - mechanical replacement gates are present in the fast lane
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-ship.js")
        non_reviewer_opinion_agents = (
            "ac-validator",
            "ac-fulfillment-gate",
            "change-scope-reviewer",
        )
        reintroduced = [ag for ag in non_reviewer_opinion_agents if ag in content]
        self.assertEqual(
            reintroduced,
            [],
            f"GUARD (BO-2500d-1-i): the following still-forbidden opinion-only "
            f"gates were re-introduced into fast-lane-ship.js: {reintroduced}. "
            "They must remain absent — the fast lane's mechanical gates "
            "('verify_red_baseline', 'verify_green_and_coverage') plus the "
            "single veto-only pr-reviewer verdict are the whole of what is "
            "permitted. Removing a mechanical gate, or letting any verdict "
            "substitute for one, would violate BO-2500d-1-i.",
        )


if __name__ == "__main__":
    unittest.main()
