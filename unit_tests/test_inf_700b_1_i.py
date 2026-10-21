"""
MODULE: test_inf_700b_1_i
GOAL: RED test for AC INF-700b-1-i on the shipped prompt text: the no-learning branch of the
    capture step records a nothing-to-record capture attempt and never synthesises `text`.
AC: INF-700b-1-i (source_ac); ADR-034 Amendment 2 (A2.3, A2.5).

REAL-ARTIFACT NOTE: the prose is read from the DEPLOYED shared reference layout
    (``shared_reference_layout``, ``@pytest.mark.shared_layout_reader``), never from the source
    tree, so a deploy-manifest gap would show. The layout is only read.

The no-learning branch is located by the markers the shipped text already uses: ``**No path**``
(signoff section 7) and ``**On "no":**`` (the three v3 emission blocks), ending at the matching
``**Yes path**`` / ``**On "yes":**`` marker. Keep those markers when rewording.
"""
# @ac-tag: INF-700b-1-i

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SURFACES = {
    "signoff section 7": None,
    "product-owner": "agents/product-owner.md",
    "business-analyst": "agents/business-analyst.md",
    "it-po": "agents/it-po.md",
}
# The heading in agent-telemetry SKILL.md that holds the one nothing-to-record command; signoff §7 names it.
_TELEMETRY_HEADING = "Nothing-to-record capture attempt"
_NO_BRANCH = re.compile(
    r"(?:\*\*No path\*\*|\*\*On [\"“']no[\"”']:\*\*)(?P<body>.*?)"
    r"(?=\*\*Yes path\*\*|\*\*On [\"“']yes[\"”']:\*\*)",
    re.DOTALL,
)
_SYNTHESIS = (
    re.compile(r"--text\s+([\"'])[^\"'\n]*<(?:agent|component|destination|entry[-_ ]kind|ticket)>[^\"'\n]*\1", re.I),
    re.compile(
        r"\b(?:synthesi[sz]e|fill|build|compose|derive|generate|default|fall back|placeholder)\b"
        r"[^.\n]{0,60}\btext\b[^.\n]{0,80}\b(?:from|using|with|of)\b[^.\n]{0,60}"
        r"\b(?:agent|component|destination|entry[-_ ]kind|ticket|descriptive)\b",
        re.I,
    ),
)


def _surface_text(layout: Path, name: str) -> str:
    root = Path(layout) / ".leafcutter"
    assert root.is_dir(), f"the shared layout has no deployed .leafcutter at {root}"
    rel = _SURFACES[name]
    if rel is None:
        text = (root / "skills" / "signoff" / "SKILL.md").read_text(encoding="utf-8")
        start = text.index("## §7 Knowledge Capture Step")
        return text[start : text.index("## §8", start)]
    text = (root / rel).read_text(encoding="utf-8")
    match = re.search(r"^## (?:S|§)\d+ Knowledge Loop — Emission.*?(?=^## |\Z)", text,
                      re.MULTILINE | re.DOTALL)
    assert match, f"deployed {rel} has no 'Knowledge Loop — Emission' block"
    return match.group(0)


def _telemetry_section(layout: Path) -> str:
    """The deployed agent-telemetry SKILL.md section that carries the one nothing-to-record command."""
    text = (Path(layout) / ".leafcutter" / "skills" / "agent-telemetry" / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(_TELEMETRY_HEADING)}\s*$(.*?)(?=^## |\Z)", text,
                      re.MULTILINE | re.DOTALL)
    assert match, f"deployed agent-telemetry SKILL.md has no '## {_TELEMETRY_HEADING}' section"
    return match.group(1)


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("surface", list(_SURFACES))
def test_capture_step_declares_no_placeholder_text_fallback(shared_reference_layout, surface):
    # covers: INF-700b-1-i
    # angle: real_artifact
    """The no-learning branch names the nothing-to-record attempt, not a knowledge record.

    Red until the shipped text (a) gives the no-learning branch an ``emit_event.py ... --event
    capture_attempt ... --outcome nothing-to-record`` command, (b) keeps ``emit_knowledge.py`` and
    ``--text`` out of that branch, and (c) never tells the agent to build `text` from the record's
    descriptive fields: every ``--text`` argument on the surface is exactly ``'<learning>'``.
    Wrong versions caught: a no-learning branch that still calls emit_knowledge.py with a templated
    text; a branch that is only the old "proceed" with no attempt record.
    """
    text = _surface_text(shared_reference_layout, surface)
    branch = _NO_BRANCH.search(text)
    assert branch, f"{surface}: could not find the no-learning branch (No path / On \"no\") before the yes branch"
    body = branch.group("body")
    problems: list[str] = []
    if _SURFACES[surface] is None:
        # signoff section 7 points at agent-telemetry instead of carrying the command (|| true vs BO-210c-1-iii)
        if "emit_event.py" in body:
            problems.append("signoff section 7's no-learning branch still carries an inline emit_event.py command")
        if "agent-telemetry" not in body or _TELEMETRY_HEADING not in body:
            problems.append(f"signoff section 7's no-learning branch does not name the agent-telemetry skill "
                            f"and its '{_TELEMETRY_HEADING}' section")
        section = _telemetry_section(shared_reference_layout)
        if not all(token in section for token in ("emit_event.py", "capture_attempt", "nothing-to-record")):
            problems.append("the agent-telemetry section carries no nothing-to-record command")
    elif not all(token in body for token in ("emit_event.py", "capture_attempt", "nothing-to-record")):
        problems.append("the no-learning branch names no `emit_event.py --event capture_attempt "
                        "--outcome nothing-to-record` command")
    for forbidden in ("emit_knowledge.py", "--text"):
        if forbidden in body:
            problems.append(f"the no-learning branch still carries {forbidden!r}")
    for argument in re.findall(r"--text\s+(\S+)", text):
        if argument != "'<learning>'":
            problems.append(f"a --text argument other than '<learning>': {argument!r}")
    for pattern in _SYNTHESIS:
        found = pattern.search(text)
        if found:
            problems.append(f"instruction to synthesise text from descriptive fields: {found.group(0)!r}")
    assert not problems, f"{surface}: " + " | ".join(problems)
