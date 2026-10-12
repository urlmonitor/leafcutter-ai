"""
MODULE: tests.kernel.grounding.test_claim_needs_cap
GOAL: Behavioural tests that every human-added option gets its own `need.claim.<option>` search
    (up to a claim cap of its own, `research.max_claim_needs`, default 25), that the gap-need cap
    `research.max_targeted_needs` bounds gap needs only, and that an added option left out by the
    claim cap is named in the research limitations.
BUSINESS CONTEXT: In run run-de1c989117414c1c the owner added 21 options, but claims and gaps
    shared `max_targeted_needs` (2): only 2 options were searched and the other 19 were scored on
    evidence nobody looked for, with nothing in the result saying so.
ARCHITECTURE: Research is run through ResearchExecutor with mandated needs (no planning Jev
    call). Needs are read back from the retrieval_request.v1 children, and limitations from the
    waiting result's continuation state (where `afford_needs` already puts "need ... not
    researched" limitations); the fix reports the claim-cap limitations through that same seam.
"""

from __future__ import annotations

from typing import Any

from kernel.config import KernelConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.payloads import (
    OptionContext,
    ResearchRequestPayload,
    RetrievalRequestPayload,
)
from tests.kernel.capabilities.support import invocation
from tests.kernel.capabilities.test_research_graph import QUESTION, ResearchCase
from tests.kernel.grounding.test_research_targeting import NEEDS


def _config(research: dict | None = None) -> KernelConfig:
    """Return the default config with research overrides."""
    base = load_kernel_config()
    return base.model_copy(update={"research": base.research.model_copy(update=research or {})})


def _added(count: int) -> list[OptionContext]:
    """Return `count` human-added options opt.added.1 .. opt.added.<count>."""
    return [OptionContext(option_id=f"opt.added.{n}", title=f"Added option {n}",
                          description=f"claim number {n}", human_added=True)
            for n in range(1, count + 1)]


class ClaimCase(ResearchCase):
    """Run research on a mandated-needs request; read back claim/gap children and limitations."""

    def run_it(self, config: KernelConfig | None, options: list[OptionContext],
               gaps: list[str]) -> tuple[dict[str, RetrievalRequestPayload], str]:
        """Return (children keyed by need id, all limitations of the planning step joined)."""
        payload = ResearchRequestPayload(question=QUESTION, evidence_needs=NEEDS,
                                         evidence_needs_only=True, option_context=options,
                                         gaps=gaps)
        inv = invocation("research", schema_ids.RESEARCH_REQUEST, payload.model_dump(mode="json"))
        result = self.run_research(inv, self.ctx(config))
        kids = [RetrievalRequestPayload.model_validate(r.payload) for r in result.requests]
        state: dict[str, Any] = result.continuation_state or {}
        limitations = " | ".join([*state.get("limitations", []), *result.limitations])
        return {k.need.id: k for k in kids}, limitations


class TestClaimNeedsHaveTheirOwnCap(ClaimCase):
    """Claim needs are capped by max_claim_needs; gap needs stay capped by max_targeted_needs."""

    def test_21_added_options_all_get_a_claim_need_and_gaps_keep_their_own_cap(self) -> None:
        # angle: criterion
        gaps = [f"missing fact number {n}" for n in range(3)]
        kids, limitations = self.run_it(None, _added(21), gaps)
        claims = sorted(k for k in kids if k.startswith("need.claim."))
        self.assertEqual(claims, sorted(f"need.claim.opt.added.{n}" for n in range(1, 22)))
        self.assertEqual(sorted(k for k in kids if k.startswith("need.gap.")),
                         ["need.gap.1", "need.gap.2"])  # max_targeted_needs (2) caps gaps only
        self.assertNotIn("opt.added", limitations)  # nothing was left out

    def test_a_small_claim_cap_keeps_that_many_claims_and_names_each_left_out_option(self) -> None:
        # angle: failure
        kids, limitations = self.run_it(_config({"max_claim_needs": 5}), _added(8), [])
        self.assertEqual(sorted(k for k in kids if k.startswith("need.claim.")),
                         [f"need.claim.opt.added.{n}" for n in range(1, 6)])
        for left_out in ("opt.added.6", "opt.added.7", "opt.added.8"):
            self.assertIn(left_out, limitations)
        for kept in ("opt.added.1", "opt.added.5"):
            self.assertNotIn(kept, limitations)


class TestClaimCapConfig(ClaimCase):
    """The claim cap is real configuration with a default that covers a typical addition."""

    def test_the_research_config_exposes_max_claim_needs_defaulting_to_25(self) -> None:
        # angle: real_artifact
        cfg = load_kernel_config()
        self.assertEqual(getattr(cfg.research, "max_claim_needs", None), 25)
        self.assertEqual(cfg.research.max_targeted_needs, 2)  # the gap cap is unchanged
