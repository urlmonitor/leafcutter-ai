"""
MODULE: product_truth_label_checks
GOAL: Check the labels a journey carries -- its component and its tags -- against
    the project's component registry and a declared tag shape (UXP-700e-3).
BUSINESS CONTEXT: A journey's component and tags are how it is found, and both
    were free text: a typo filed a journey under a component that does not
    exist, silently. Two registries exist, spelled differently --
    docs/acceptance-criteria/index.yaml (kebab: ux-prototyping) and
    docs/components.json (underscore: ux_prototyping). A scalar `component`
    label resolves against index.yaml, per the repo's two-axis component
    convention, and that is what every existing journey already uses: resolving
    against components.json would have turned all fourteen into findings.
ARCHITECTURE: load_component_registry() is the one I/O boundary; the checks are
    pure. Findings are WARNINGS: labels were free text, and a first tightening
    warns rather than blocks (UXP-700e-3-i's migration constraint), so upgrading
    does not start failing commits in projects whose labels predate the rule.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger("product_truth_label_checks")

#: The declared shape of a tag: lowercase words joined by single hyphens. Every
#: tag in the store (44 at the time of writing) already matches it.
_TAG_SHAPE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _normalise_label(label: str) -> str:
    """Fold case and spacing, so a near miss compares equal to what it meant."""
    return re.sub(r"[\s_]+", "-", label.strip().lower())


def load_component_registry(path: Path) -> set[str] | None:
    """Return the registered component ids from the AC store's index.yaml.

    Args:
        path: The index.yaml to read.

    Returns:
        The set of registered component ids, or None when the file is absent so
        the caller can list the label check as not executed rather than guess.
    """
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except OSError:
        logger.exception("cannot read %s", path)
        raise
    except yaml.YAMLError:
        logger.exception("invalid YAML in %s", path)
        raise
    return {entry["id"] for entry in data.get("components", []) if isinstance(entry, dict) and "id" in entry}


def count_labels(flows: dict) -> int:
    """Return how many labels the journeys carry: one component each, plus their tags."""
    return sum(bool(flow.get("component")) + len(flow.get("tags") or []) for flow in flows.values())


def _check_labels(flows: dict, registered: set[str], errors: list[str], warnings: list[str]) -> int:
    """Report every journey label that does not resolve, and count those that do.

    A component label resolves when it is a registered component id. One that
    differs from a registered id only by case or spacing is reported as that id
    having been meant, not as a new label. A tag resolves when it matches the
    declared tag shape. Findings go to *warnings*; *errors* is accepted so the
    call matches the other checks and is deliberately left untouched.

    Args:
        flows: ``{flow_id -> flow}``.
        registered: Registered component ids.
        errors: Shared error list (unused, see above).
        warnings: Shared warning list; one entry per unresolved label.

    Returns:
        How many labels resolved. Zero for a record carrying no labels, so such a
        run is told apart from one in which every label resolved.
    """
    meant = {_normalise_label(component): component for component in registered}
    resolved = 0
    for flow_id, flow in flows.items():
        component = flow.get("component")
        if component in registered:
            resolved += 1
        elif isinstance(component, str) and _normalise_label(component) in meant:
            warnings.append(f"[label] {flow_id}: component {component!r} is not a registered component; "
                            f"{meant[_normalise_label(component)]!r} was meant")
        elif component:
            warnings.append(f"[label] {flow_id}: component {component!r} is not registered in "
                            f"docs/acceptance-criteria/index.yaml")
        for tag in flow.get("tags") or []:
            if isinstance(tag, str) and _TAG_SHAPE.match(tag):
                resolved += 1
            else:
                warnings.append(f"[label] {flow_id}: tag {tag!r} does not match the declared tag shape "
                                f"(lowercase words joined by hyphens)")
    return resolved


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder]: UXP-700e-3 -- new module. Component labels resolve
  against docs/acceptance-criteria/index.yaml, answering the registry question
  the AC left open by the repo's two-axis convention and by measurement (14 of
  14 journeys resolve there, 0 against docs/components.json). Tags must be
  lowercase kebab (44 of 44 existing tags already are). Findings warn rather
  than block, per UXP-700e-3-i's migration constraint. (#EPIC-TruthfulProjectRecord/43)
====================================================================
"""
