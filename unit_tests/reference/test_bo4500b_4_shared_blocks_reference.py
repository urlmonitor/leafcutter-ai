"""
MODULE: unit_tests/reference/test_bo4500b_4_shared_blocks_reference.py
GOAL: BO-4500b-4 - keep docs/reference/shared-blocks.md from drifting away from
    config/commit_step.json: every configured reason code is listed under its own family
    on the page, and the page states the configured retry ceiling.
BUSINESS CONTEXT: The page holds no copy of configuration beyond this statement; a code
    added to the configuration but missing from the page must fail here, naming the code.
ARCHITECTURE: Pure parser/checker over the page text and the config dict; the tests read
    the real page and config at test time and use modified config copies to prove the
    checker discriminates.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = _REPO_ROOT / "config" / "commit_step.json"
PAGE_PATH = _REPO_ROOT / "docs" / "reference" / "shared-blocks.md"

_FAMILIES_HEADING = "#### Reason-code families"
_CEILING_RE = re.compile(r"`max_transient_retries:\s*([^`\s]+)\s*`")
_FAMILY_RE = re.compile(r"^#####\s+(\S+)\s*$")
_CODE_RE = re.compile(r"^-\s+`([^`]+)`\s*$")


def parse_page(page_text: str) -> tuple[dict[str, list[str]], str | None]:
    """Return ({family: [codes]}, ceiling or None) as the page states them."""
    ceiling_match = _CEILING_RE.search(page_text)
    ceiling = ceiling_match.group(1) if ceiling_match else None

    families: dict[str, list[str]] = {}
    current: str | None = None
    in_section = False
    for line in page_text.splitlines():
        if line.strip() == _FAMILIES_HEADING:
            in_section = True
            continue
        if not in_section:
            continue
        if line.startswith("#") and not line.startswith("#####"):
            break  # next heading of level 4 or higher ends the section
        if line.strip() == "---":
            break
        family = _FAMILY_RE.match(line)
        if family:
            current = family.group(1)
            families.setdefault(current, [])
            continue
        code = _CODE_RE.match(line)
        if code and current is not None:
            families[current].append(code.group(1))
    return families, ceiling


def check_page(config: dict, page_text: str) -> list[str]:
    """Return the problems found comparing the page with the configuration."""
    families, ceiling = parse_page(page_text)
    problems: list[str] = []

    expected_ceiling = str(config["max_transient_retries"])
    if ceiling is None:
        problems.append("max_transient_retries: the page does not state it")
    elif ceiling != expected_ceiling:
        problems.append(
            f"max_transient_retries: page says {ceiling}, configuration says {expected_ceiling}"
        )

    for family, codes in config["reason_codes"].items():
        listed = families.get(family, [])
        for code in codes:
            if code in listed:
                continue
            elsewhere = [f for f, c in families.items() if code in c]
            if elsewhere:
                problems.append(f"{code}: page lists it under {elsewhere[0]}, configuration says {family}")
            else:
                problems.append(f"{code}: missing from the page under family {family}")
    configured = {c for codes in config["reason_codes"].values() for c in codes}
    for family, listed in families.items():
        for code in listed:
            if code not in configured:
                problems.append(f"{code}: page lists it under {family} but the configuration has no such code")
    return problems


def _real_inputs() -> tuple[dict, str]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8")), PAGE_PATH.read_text(encoding="utf-8")


def test_page_states_every_configured_reason_code_and_the_ceiling():
    # covers: BO-4500b-4
    # angle: discrimination
    """Wrong versions caught: comparing only the retry ceiling and ignoring reason codes;
    passing when the page lists fewer codes than the configuration (a code missing, or
    listed under the wrong family); passing when the ceiling differs or is absent."""
    config, page = _real_inputs()
    assert check_page(config, page) == []

    # The real page really was inspected: every configured family parsed to a non-empty list.
    families, ceiling = parse_page(page)
    assert ceiling is not None
    assert all(families.get(f) for f in config["reason_codes"])

    extra_code = copy.deepcopy(config)
    extra_code["reason_codes"]["step"].append("step_made_up_for_test")
    problems = check_page(extra_code, page)
    assert any("step_made_up_for_test" in p for p in problems)

    other_ceiling = copy.deepcopy(config)
    other_ceiling["max_transient_retries"] = config["max_transient_retries"] + 1
    problems = check_page(other_ceiling, page)
    assert any("max_transient_retries" in p for p in problems)

    moved = copy.deepcopy(config)
    code = moved["reason_codes"]["step"].pop()
    moved["reason_codes"]["check"].append(code)
    assert any(code in p for p in check_page(moved, page))
