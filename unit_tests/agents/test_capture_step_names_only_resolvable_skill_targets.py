"""
MODULE: unit_tests/agents/test_capture_step_names_only_resolvable_skill_targets.py
GOAL: INF-700b-1 descriptor 1 (test_spec) — the shared sign-off knowledge-capture
      step (signoff SKILL.md section 7) and each v3 agent's Knowledge Loop —
      Emission block must name only skill artefacts that actually exist under
      templates/skills/. A dangling reference in this specific step is the
      failure mode INF-700b-1 exists to close: eight weeks of total silence
      because steps 2 and 3 told every agent to load `route-learning` and
      `capture-learning`, neither of which was ever committed.
BUSINESS CONTEXT: scripts/check_skill_refs.py is the real build guard for this
      class of defect. This test EXECUTES it (subprocess, real argv) against
      the real repository — never a synthetic sandbox tree — and then narrows
      its structured findings to only the lines that fall inside the specific
      step this AC governs. The narrowing is done by locating the step's own
      heading boundaries in the shipped Markdown and filtering the checker's
      reported (file, line) pairs against that range — never by grepping for
      the literal strings "route-learning" / "capture-learning". A renamed or
      newly-introduced dangling reference anywhere inside the step must still
      fail this test; a hard-coded name list would go stale the moment
      someone adds a fifth instruction.
ARCHITECTURE: unrelated dangling references that check_skill_refs.py already
      reports against this repo (`import-scanner`, `find-context-candle`,
      `trade-analysis` in research-agent.md; `route-learning` mentions in
      retrospective-agent.md and templates/skills/README.md) are out of this
      AC's scope — they are not inside the step under test — and must not
      make this test fail for the wrong reason.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CHECKER_PATH = _REPO_ROOT / "scripts" / "check_skill_refs.py"

_SIGNOFF_PATH = _REPO_ROOT / "templates" / "skills" / "signoff" / "SKILL.md"
_V3_AGENT_PATHS = [
    _REPO_ROOT / "templates" / "agents" / "product-owner.md",
    _REPO_ROOT / "templates" / "agents" / "business-analyst.md",
    _REPO_ROOT / "templates" / "agents" / "it-po.md",
]

_SIGNOFF_STEP_HEADING_RE = re.compile(r"^## .*Knowledge Capture Step")
_V3_STEP_HEADING_RE = re.compile(r"^## .*Knowledge Loop — Emission")
_ANY_H2_RE = re.compile(r"^## ")
_FINDING_LINE_RE = re.compile(r"^\s+-\s+(\S+):(\d+)\s*$")


def _step_line_range(path: Path, heading_re: re.Pattern[str]) -> tuple[int, int]:
    """Return the inclusive 1-based (start, end) line range of the step.

    The step starts at the first line matching ``heading_re`` and ends the
    line before the next ``##`` heading (or at end of file). Raises
    ``AssertionError`` if the heading cannot be found — a silently-empty
    range would make the filter below vacuously pass.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    start: int | None = None
    for lineno, line in enumerate(lines, start=1):
        if start is None:
            if heading_re.match(line):
                start = lineno
            continue
        if _ANY_H2_RE.match(line):
            return (start, lineno - 1)
    assert start is not None, f"could not locate the knowledge-capture step heading in {path}"
    return (start, len(lines))


def _parse_findings(stderr: str) -> list[tuple[Path, int]]:
    """Parse check_skill_refs.py's ``- <relpath>:<lineno>`` report lines."""
    findings: list[tuple[Path, int]] = []
    for line in stderr.splitlines():
        m = _FINDING_LINE_RE.match(line)
        if not m:
            continue
        rel_path, lineno = m.group(1), int(m.group(2))
        findings.append(((_REPO_ROOT / rel_path).resolve(), lineno))
    return findings


class TestCaptureStepNamesOnlyResolvableSkillTargets(unittest.TestCase):
    def test_capture_step_names_only_resolvable_skill_targets(self) -> None:
        # covers: INF-700b-1
        # angle: reachability
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(_CHECKER_PATH), "--repo-root", str(_REPO_ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        findings = _parse_findings(result.stderr)

        step_ranges: dict[Path, tuple[int, int]] = {
            _SIGNOFF_PATH.resolve(): _step_line_range(_SIGNOFF_PATH, _SIGNOFF_STEP_HEADING_RE),
        }
        for p in _V3_AGENT_PATHS:
            step_ranges[p.resolve()] = _step_line_range(p, _V3_STEP_HEADING_RE)

        offending = [
            (path, lineno)
            for path, lineno in findings
            if path in step_ranges and step_ranges[path][0] <= lineno <= step_ranges[path][1]
        ]

        self.assertEqual(
            [],
            offending,
            "the knowledge-capture step names a skill target check_skill_refs.py "
            "reports as missing (no instruction may resolve to a missing target, "
            "per INF-700b-1's criteria): "
            f"{offending}\n\nfull checker output:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
