"""Validated opaque JSON for source-bearing payloads and durable continuations.
MODULE: kernel.contracts.verbatim
GOAL: Preserve exact nested source quotations while retaining JSON-only validation.
BUSINESS CONTEXT: Trimming supplied source content changes its quoted evidence identity.
ARCHITECTURE: Recursive JSON type used only at opaque transport boundaries; labels retain normal validation.
"""
from typing import Annotated, Union
from typing_extensions import TypeAliasType
from pydantic import Field, StrictBool, StrictInt, StringConstraints

VerbatimString = Annotated[str, StringConstraints(strict=True, strip_whitespace=False)]
VerbatimJson = TypeAliasType(
    "VerbatimJson",
    Union[dict[VerbatimString, "VerbatimJson"], list["VerbatimJson"], VerbatimString,
          StrictInt, Annotated[float, Field(strict=True, allow_inf_nan=False)], StrictBool, None],
)

# DECISION HISTORY
# - 2026-10-01 23:00 [python-coder]: Preserve quoted source bytes through JSON-only research checkpoints. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500f-4)
