"""
MODULE: unit_tests/agents/test_bo_400a_2_vi.py
GOAL: Red-phase tests for BO-400a-2-vi — no agent template tells its agent to
      write a level-2 (`## `) heading into its output.

The agent's output becomes its comment under the ticket's `## Comments`
section, where a level-2 heading looks like a section boundary. The fix
replaces the instructed `## Escalation` heading in architect-review,
conflict-resolver and pr-reviewer with a bold `**Escalation**` label.

The scan helper below distinguishes:
  (a) a template's OWN section headings: `## ` lines at the top level of the
      markdown, outside any fenced block. Never counted.
  (b) a heading the AGENT is told to write, found two ways:
      - an output-example fence (a fence that is NOT a language-tagged code
        block such as python/bash/json/yaml/js) whose first non-empty line
        starts with `## `;
      - prose (outside fences) with a backticked `## X` in a sentence that
        says append/add/write/... output/comment/section.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENTS_DIR = _REPO_ROOT / "templates" / "agents"
_THREE = ("architect-review", "conflict-resolver", "pr-reviewer")

# Fence info strings that mark a block as code, not as an example of agent output.
_CODE_LANGS = frozenset(
    {
        "python", "py", "bash", "sh", "shell", "zsh", "json", "jsonc", "yaml",
        "yml", "js", "javascript", "ts", "typescript", "sql", "toml", "diff",
        "ini", "html", "css", "mermaid", "powershell", "ps1",
    }
)
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)")
# "append `## X` to your output": a verb, a backticked level-2 heading directly
# after it, and the agent's own output/comment as the destination. "append a
# `## Comments` entry" (a section name used as a place) does not match.
_INSTRUCTED_HEADING_RE = re.compile(
    r"\b(?:append|add|write|emit|include)\w*\s+(?:a\s+|an\s+|the\s+)?`##\s+[^`\n]+`"
    r"(?:\s+(?:heading|section))?\s+to\s+(?:your|the)\s+(?:output|comment|response|reply)\b",
    re.IGNORECASE,
)
# An instruction that makes the agent's OWN output carry an appended section:
# "append this section", "append X to your output". An append aimed at a named
# document or payload ("append this section to the retrospective document")
# writes into a file or a caller-bound payload, not the ticket comment, so a
# later "to <something other than your>" disqualifies the line.
_APPEND_INSTRUCTION_RE = re.compile(r"\bappend\w*\b(?!.*\bto(?:\s+(?!your\b)\S|\s*$))", re.IGNORECASE)


def _split_blocks(text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str, list[str]]]]:
    """Split markdown into prose lines and fenced blocks.

    Returns (prose, blocks): prose is [(lineno, line)] outside fences; blocks is
    [(open_lineno, info_string, body_lines)]. A fence closes only on a fence
    line of the same character and at least the opening length, so a
    four-backtick fence may safely contain three-backtick lines.
    """
    prose: list[tuple[int, str]] = []
    blocks: list[tuple[int, str, list[str]]] = []
    open_marker: str | None = None
    info = ""
    start = 0
    body: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _FENCE_RE.match(line)
        if open_marker is None:
            if m:
                open_marker, info, start, body = m.group(1), m.group(2).lower(), lineno, []
            else:
                prose.append((lineno, line))
        elif m and m.group(1)[0] == open_marker[0] and len(m.group(1)) >= len(open_marker) and not m.group(2):
            blocks.append((start, info, body))
            open_marker = None
        else:
            body.append(line)
    if open_marker is not None:
        blocks.append((start, info, body))
    return prose, blocks


def scan_for_instructed_level_two_headings(path: Path) -> list[str]:
    """Return findings (strings) for each heading the template tells its agent to write."""
    prose, blocks = _split_blocks(path.read_text(encoding="utf-8"))
    findings: list[str] = []
    for lineno, info, body in blocks:
        if info in _CODE_LANGS:
            continue
        first = next((ln for ln in body if ln.strip()), "")
        if first.startswith("## ") and _section_says_append(prose, lineno):
            findings.append(f"{path.name}:{lineno}: output example fence starts with {first.strip()!r}")
    for lineno, line in prose:
        if _INSTRUCTED_HEADING_RE.search(line):
            findings.append(f"{path.name}:{lineno}: instruction to write a heading: {line.strip()!r}")
    return findings


def _section_says_append(prose: list[tuple[int, str]], fence_lineno: int) -> bool:
    """True when the prose since the last top-level heading, before the fence, says 'append'.

    A report template that a section merely shows ("## Report", returned to the
    caller) is not an instruction to append a heading to the ticket comment; an
    'append this section / append X to your output' sentence is.
    """
    context: list[str] = []
    for n, line in prose:
        if n >= fence_lineno:
            break
        if line.startswith("#"):
            context = []
        else:
            context.append(line)
    return any(_APPEND_INSTRUCTION_RE.search(ln) for ln in context)


def _instruction_problems(name: str, prose: list[tuple[int, str]]) -> list[str]:
    """Instruction lines that name the escalation and say append must name the bold label.

    pr-reviewer's instruction ("Always append this section") does not repeat the name,
    so only instruction lines that do name the escalation heading are checked here.
    """
    instruction = [
        (n, ln) for n, ln in prose
        if "escalation" in ln.lower() and re.search(r"\bappend\b", ln, re.IGNORECASE)
    ]
    return [
        f"{name}:{n}: instruction does not name the **Escalation** label: {ln.strip()!r}"
        for n, ln in instruction
        if "**Escalation**" not in ln
    ]


def _example_block_problems(name: str, n: int, body: list[str]) -> list[str]:
    """Problems in one fenced block: a '## Escalation' line, or a malformed escalation example."""
    problems: list[str] = []
    if any(ln.strip() == "## Escalation" for ln in body):
        problems.append(f"{name}:{n}: fenced example contains a '## Escalation' line")
    if any(ln.startswith("Branch:") for ln in body):
        first = next((ln for ln in body if ln.strip()), "")
        if first.strip() != "**Escalation**":
            problems.append(f"{name}:{n}: escalation example opens with {first.strip()!r}, not '**Escalation**'")
        if not any(ln.startswith("Reason:") for ln in body):
            problems.append(f"{name}:{n}: escalation example lost its Reason line")
    return problems


def _escalation_template_problems(name: str) -> list[str]:
    """All escalation-label problems for one template, as file:line strings."""
    text = (_AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    prose, blocks = _split_blocks(text)
    problems: list[str] = []
    if "**Escalation**" not in text:
        problems.append(f"{name}: the **Escalation** label appears nowhere in the template")
    problems.extend(_instruction_problems(name, prose))
    for n, _info, body in blocks:
        problems.extend(_example_block_problems(name, n, body))
    return problems


def test_escalation_section_is_a_bold_label_in_the_three_templates():
    # covers: BO-400a-2-vi
    # angle: criterion
    """AC-1: the escalation section is introduced by a bold **Escalation** label, not a `## ` heading."""
    problems = [p for name in _THREE for p in _escalation_template_problems(name)]
    assert not problems, "escalation section is still a level-2 heading:\n" + "\n".join(problems)


def test_no_agent_template_instructs_a_level_two_heading_in_output():
    # covers: BO-400a-2-vi
    # angle: boundary
    """AC-2: scanning every templates/agents/*.md finds no instruction to write a `## ` heading."""
    templates = sorted(_AGENTS_DIR.glob("*.md"))
    assert len(templates) > 10, f"expected many agent templates, scanned {len(templates)}"
    findings: list[str] = []
    for path in templates:
        findings.extend(scan_for_instructed_level_two_headings(path))
    assert not findings, "templates instruct a level-2 heading in agent output:\n" + "\n".join(findings)


def test_scan_flags_a_template_that_instructs_a_level_two_heading():
    # covers: BO-400a-2-vi
    # angle: discrimination
    """NEGATIVE CONTROL: the same scan flags a template that says append `## Escalation` to your output."""
    body = (
        "# Fake agent\n\n"
        "## Step 1 — Own Heading\n\n"
        "Whichever branch fires, append `## Escalation` to your output naming the branch.\n\n"
        "```\n## Escalation\n\nBranch: small\nReason: demo\n```\n\n"
        "```python\n## not an output example\n```\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fake-agent.md"
        path.write_text(body, encoding="utf-8")
        findings = scan_for_instructed_level_two_headings(path)
        own_only = Path(tmp) / "own-only.md"
        own_only.write_text("# T\n\n## Step 1 — Escalation Log\n\nText.\n", encoding="utf-8")
        control = scan_for_instructed_level_two_headings(own_only)
    assert len(findings) == 2, f"expected the instruction and the fenced example flagged, got {findings}"
    assert any("instruction" in f for f in findings) and any("fence" in f for f in findings)
    assert control == [], f"a template's own heading must not be flagged: {control}"
