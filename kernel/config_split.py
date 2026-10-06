"""
MODULE: kernel.config_split
GOAL: Validate the `split` configuration section: the off switch, the bundle threshold and the
    part bounds of the split of a bundled request.
BUSINESS CONTEXT: ADR-053 and ADR-067: a request that holds several separate questions is offered
    as a split a person approves. The threshold is biased against false positives, and no bound
    is hard-coded in node code, so every tunable is reviewed in one file and recorded in traces.
ARCHITECTURE: A frozen pydantic section like the others in kernel.config. No field carries
    a field default (the repo convention is none: the default JSON is the single source, and ships
    enabled=false while DK-400 is built in three epics); every value comes from
    config/kernel_config.default.json.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class SplitConfig(BaseModel):
    """Settings of the split of a bundled request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The off switch: false restores today's behaviour exactly (no bundle question, no split).
    enabled: bool
    #: A subject counts as bundled only at or above this Jev probability.
    bundle_threshold: Probability
    #: Most parts one split may hold.
    max_parts: int = Field(ge=2)
    #: Most parts one run may hold across all its splits (a split needs at least 2 left).
    max_parts_per_run: int = Field(ge=2)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 [python-coder]: Section added for DK-400a-1; enabled ships false in E1 and E2.
#   (#TICKET-20261006-DK-400a-1)
# ====================================================================
