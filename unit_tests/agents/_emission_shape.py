"""
MODULE: unit_tests/agents/_emission_shape.py
GOAL: Shared, declaration-driven parity-checking helpers for INF-400b-2-ii.

This is TEST-SUPPORT code, not a production module and not a test module
itself (pytest does not collect it — its filename does not match
``test_*.py``). It backs the six INF-400b-2-ii descriptors:

  1. unit_tests/agents/test_all_documented_emission_shapes_declare_the_same_key_set.py
  2. tests/knowledge/test_the_28_shipped_records_conform_to_the_documented_shape.py
  3. unit_tests/agents/test_a_divergence_planted_in_one_surface_is_reported.py
  4. unit_tests/agents/test_an_unparseable_emission_object_fails_rather_than_passes.py
  5. unit_tests/agents/test_a_newly_declared_emission_surface_is_discovered_not_ignored.py
  6. unit_tests/agents/test_each_restating_surface_references_the_normative_source_resolvably.py

DECLARATION-DRIVEN SURFACE DISCOVERY (not path enumeration):
A parity check hard-coded to today's four file paths cannot see a fifth
emission surface added later — that is the exact shape of the defect this AC
repairs. ``discover_emission_surfaces`` instead queries two declared sources:

  1. ``config/agent_registry.json`` — every agent entry whose ``description``
     field names the v3 ticket-creation pipeline is a restating surface. This
     is a real, already-shipped field (see product-owner/business-analyst/
     it-po registry entries), not an invented marker.
  2. ``templates/skills/signoff/SKILL.md`` — always included; it is the one
     normative source per INF-400b-2-ii's ``delivers_to`` contract.

Both ``registry_path`` and ``repo_root`` are injectable so tests can prove the
discovery step generalizes to a declared surface it was never told about by
name (descriptor 5), without touching the real registry file.

OPTIONAL-FIELD CONTRACT:
INF-400b-2-ii's ``delivers_to.contract`` names exactly one field as optional
across every producer: ``ticket``. That is a fact asserted by the AC itself
(and restated in SKILL.md section 7 step 4's prose), not something this
helper invents — ``OPTIONAL_KEYS`` exists to encode that one contract fact,
not to accumulate ad hoc exceptions.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_REGISTRY_PATH = REPO_ROOT / "config" / "agent_registry.json"
NORMATIVE_SKILL_RELPATH = "templates/skills/signoff/SKILL.md"
DEPLOYED_SKILL_RELPATH = ".claude/skills/signoff/SKILL.md"

# The single field INF-400b-2-ii's delivered contract names as optional.
OPTIONAL_KEYS = frozenset({"ticket"})

_V3_DESCRIPTION_MARKER = "v3"

_JSON_FENCE_RE = re.compile(r"```json\s*(.*?)```", re.DOTALL)


class EmissionBlockError(ValueError):
    """Raised when a declared surface's emission object cannot be parsed.

    Covers both "no fenced knowledge_captured JSON block found" and "a block
    was found but is not valid JSON" — callers must treat both as failures,
    never as a silent pass (INF-400b-2-ii descriptor 4).
    """


@dataclass(frozen=True)
class EmissionSurface:
    label: str
    path: Path
    is_normative: bool = False


@dataclass(frozen=True)
class ParityResult:
    ok: bool
    required_key_sets: dict[str, frozenset[str]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Surface discovery
# ---------------------------------------------------------------------------


def discover_emission_surfaces(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    repo_root: Path = REPO_ROOT,
) -> list[EmissionSurface]:
    """Return every declared knowledge_captured emission surface.

    Always includes the normative signoff skill, plus one restating surface
    per registry agent entry whose ``description`` names the v3 pipeline.
    ``template_path`` is resolved against ``repo_root``; an absolute
    ``template_path`` in the registry overrides ``repo_root`` entirely
    (``Path.__truediv__`` semantics), which is how descriptor 5's synthetic
    surface points at a temp-directory file without needing a temp repo_root.
    """
    with open(registry_path, encoding="utf-8") as fh:
        registry = json.load(fh)

    surfaces: list[EmissionSurface] = [
        EmissionSurface(
            label="signoff-skill (normative)",
            path=repo_root / NORMATIVE_SKILL_RELPATH,
            is_normative=True,
        )
    ]
    for agent in registry.get("agents", []):
        description = agent.get("description") or ""
        if _V3_DESCRIPTION_MARKER not in description.lower():
            continue
        template_path = agent.get("template_path")
        if not template_path:
            continue
        surfaces.append(
            EmissionSurface(
                label=agent.get("id", str(template_path)),
                path=repo_root / template_path,
            )
        )
    return surfaces


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def extract_emission_object(path: Path) -> dict[str, Any]:
    """Parse the fenced ``knowledge_captured`` JSON object out of ``path``.

    Raises ``EmissionBlockError`` — never returns a fallback value — when the
    file cannot be read, no fenced block mentions ``knowledge_captured``, or
    the matching block is not valid JSON.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EmissionBlockError(f"{path}: could not be read ({exc})") from exc

    candidates = _JSON_FENCE_RE.findall(text)
    kc_candidates = [c for c in candidates if "knowledge_captured" in c]
    if not kc_candidates:
        raise EmissionBlockError(f"{path}: no knowledge_captured emission block found")

    # Use the first matching block; every shipped surface carries exactly one.
    try:
        obj = json.loads(kc_candidates[0])
    except json.JSONDecodeError as exc:
        raise EmissionBlockError(
            f"{path}: knowledge_captured emission block is not valid JSON ({exc})"
        ) from exc

    if not isinstance(obj, dict):
        raise EmissionBlockError(f"{path}: emission block did not parse to a JSON object")

    return obj


def required_keys(emission_object: dict[str, Any]) -> frozenset[str]:
    """Return the required (non-optional) key set of a parsed emission object."""
    return frozenset(k for k in emission_object if k not in OPTIONAL_KEYS)


# ---------------------------------------------------------------------------
# Parity check
# ---------------------------------------------------------------------------


def check_parity(surfaces: list[EmissionSurface]) -> ParityResult:
    """Assert every surface's required key set agrees with the normative one.

    Fails closed: any surface whose emission object cannot be parsed makes
    the whole result ``ok=False`` — it is never silently skipped or counted
    as conformant (INF-400b-2-ii descriptor 4).
    """
    parsed: dict[str, frozenset[str]] = {}
    problems: list[str] = []

    for surface in surfaces:
        try:
            obj = extract_emission_object(surface.path)
        except EmissionBlockError as exc:
            problems.append(f"{surface.label}: {exc}")
            continue
        parsed[surface.label] = required_keys(obj)

    if problems:
        return ParityResult(ok=False, required_key_sets=parsed, problems=problems)

    normative_label = next((s.label for s in surfaces if s.is_normative), None)
    baseline = parsed.get(normative_label) if normative_label else None
    if baseline is None:
        baseline = next(iter(parsed.values()), frozenset())

    for label, keys in parsed.items():
        if keys != baseline:
            problems.append(
                f"{label}: required keys {sorted(keys)} != normative {sorted(baseline)}"
            )

    return ParityResult(ok=not problems, required_key_sets=parsed, problems=problems)


# ---------------------------------------------------------------------------
# Cross-reference check (descriptor 6)
# ---------------------------------------------------------------------------


def find_normative_references(text: str) -> tuple[str | None, str | None]:
    """Return (checkout_ref, deployed_ref) path strings found in ``text``.

    Either element is ``None`` when that reference is absent. Callers must
    then resolve the returned path string against the repo root and check
    real existence — a reference that merely names a plausible-looking path
    without the target existing is not "resolvable".
    """
    checkout_match = re.search(re.escape(NORMATIVE_SKILL_RELPATH), text)
    deployed_match = re.search(re.escape(DEPLOYED_SKILL_RELPATH), text)
    checkout_ref = checkout_match.group(0) if checkout_match else None
    deployed_ref = deployed_match.group(0) if deployed_match else None
    return checkout_ref, deployed_ref
