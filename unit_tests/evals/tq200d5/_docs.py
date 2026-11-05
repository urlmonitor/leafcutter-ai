"""MODULE: unit_tests/evals/tq200d5/_docs.py

GOAL: Read the two documents the TQ-200d-5 family writes (scripts/evals/README.md and
    docs/how-to/run-a-live-agent-eval.md) so the doc-drift tests can hold them to the code.
ARCHITECTURE: Pure text helpers: a section by heading, sentences, the "says the instructions or input go on
    the command line" detector, the commands of the how-to. Each detector is probed with good and bad
    sentences by the tests that use it, so a detector that matches everything or nothing is caught.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from unit_tests.evals.tq200d5._fake import EVALS, REPO

README = EVALS / "README.md"
HOW_TO = REPO / "docs" / "how-to" / "run-a-live-agent-eval.md"
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
_COMMAND_LINE = re.compile(r"command[- ]line|argv|argument", re.I)
_SUBJECT = re.compile(r"instruction|template|system prompt|row input|input|prompt", re.I)
_NEGATION = re.compile(r"\b(not|never|no|neither|nor|without|instead|rather than|cannot|can't|limit|cap|exceed\w*|over|longer|"
                       r"too long|avoid\w*|stays? short|only|file|stdin|beyond)\b", re.I)
_INLINE_FLAG = re.compile(r"(?<![\w-])--(?:append-)?system-prompt(?!-file)\b|(?<![\w-])-p\s+<")


def text_of(path: Path) -> str:
    """The file's text; the failure names the missing document."""
    assert path.is_file(), f"{path.relative_to(REPO)} does not exist"
    return path.read_text(encoding="utf-8")


def section(text: str, title: str) -> str:
    """The body of the section headed *title* (any level), up to the next heading of the same or a higher level."""
    heads = list(_HEADING.finditer(text))
    for i, head in enumerate(heads):
        if head.group(2).strip().lower() == title.lower():
            end = next((h.start() for h in heads[i + 1:] if len(h.group(1)) <= len(head.group(1))), len(text))
            return text[head.end():end]
    pytest.fail(f"no section headed {title!r}; headings are {[h.group(2) for h in heads]}")


def sentences(text: str) -> list[str]:
    """Sentences of the prose (fenced code blocks dropped), split on full stops and line breaks."""
    prose = re.sub(r"```.*?```", " ", text, flags=re.S)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n\s*\n|\n(?=[-*#|])", prose) if s.strip()]


def claims_command_line_delivery(sentence: str) -> bool:
    """True when a sentence says the instructions or the row input travel on the command line."""
    if _INLINE_FLAG.search(sentence) and not re.search(r"\b(not|never|no longer|instead of)\b", sentence, re.I):
        return True
    return bool(_COMMAND_LINE.search(sentence) and _SUBJECT.search(sentence) and not _NEGATION.search(sentence))


def command_line_claims(text: str) -> list[str]:
    return [s for s in sentences(text) if claims_command_line_delivery(s)]


def frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "the how-to has no frontmatter"
    return yaml.safe_load(text.split("\n---", 1)[0][4:])


def eval_agents() -> dict:
    return json.loads((EVALS / "agent_eval_config.json").read_text(encoding="utf-8"))["agents"]


def run_lines(text: str) -> list[str]:
    """Every line that shows a run_agent_eval.py command."""
    return [line for line in text.splitlines() if "run_agent_eval.py" in line]


def agent_names(text: str) -> set[str]:
    """Every ``--agent <name>`` in the text."""
    return set(re.findall(r"--agent[ =]([A-Za-z0-9_.-]+)", text))


def flags_shown(text: str) -> set[str]:
    """Every ``--option`` on a run_agent_eval.py command line of the text."""
    return {flag for line in run_lines(text) for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", line)}
