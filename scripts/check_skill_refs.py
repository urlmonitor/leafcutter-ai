#!/usr/bin/env python3
"""
check_skill_refs.py — build guard for skill references written in template prose.

Every ``(.claude|templates)/skills/<name>`` path an agent or skill is told to
load must resolve to a real directory in ``templates/skills/``. This guard
exists because the build's only existing skill-reference check
(``build_phases.py`` ``skills_invoked`` resolution) reads the ``skills_invoked``
field of ``config/agent_registry.json`` — a machine-maintained declaration that
is rarely wrong. The form that actually rots is the hand-typed path inside a
Markdown template body, which no validator read until this one.

Six dangling references accumulated in that blind spot across at least three
epics (KI-BP-007): ``route-learning`` and ``capture-learning`` (loaded by the
``signoff`` §7 knowledge-capture step and by PO/BA/IT-PO v3),
``agent-telemetry`` (nine ``emit_event.py`` invocations in the ``building-epics``
runbook), and ``import-scanner`` / ``find-context-candle`` / ``trade-analysis``
(routing rows inherited when ``research-agent`` was copied in from a
trading-system project). None was ever committed. Every call site treats
"skill not found" as a pass, so all six were silent runtime no-ops.

Two reference classes, deliberately scored differently:
  - IMPERATIVE — the reference sits on a line that tells someone to act on it
    (``Load ...``, ``python .../script.py``, "invoke via Bash", "Read ...").
    A dangling imperative reference is a FAILURE: an agent will follow it.
  - MENTION — the path appears in descriptive prose. Reported under --verbose,
    never failed on.

DECISION HISTORY blocks (``<!-- ... -->``) are stripped before scanning. They
are the repo's convention for recording what a file used to do, so they
legitimately name deleted skills — e.g. ``plan-feature/SKILL.md`` records the
``create-ac`` migration (#184) long after ``create-ac/`` was correctly removed.
Scanning them would fail the build on accurate history.

Usage:
    python3 scripts/check_skill_refs.py [--repo-root <path>] [--verbose]

Exit codes:
    0 - every imperative skill reference resolves (or nothing to check)
    1 - one or more dangling imperative references (details printed to stderr)
    2 - the skills directory could not be read (hard error)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

# A skill path as written in prose: .claude/skills/<name> or templates/skills/<name>
_SKILL_REF_RE = re.compile(r"(?:\.claude|templates)/skills/([a-z0-9][a-z0-9._-]*)")

# HTML comment blocks — DECISION HISTORY and friends. Stripped before scanning.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Markers that make a reference an instruction rather than a description.
_IMPERATIVE_RE = re.compile(
    r"\b(load|read|invoke|run|execute|executes|python|python3|apply|bash|source)\b",
    re.IGNORECASE,
)


def load_skill_names(templates_dir: Path) -> set[str] | None:
    """Return the set of real skill directory names, or None if unreadable."""
    skills_dir = templates_dir / "skills"
    try:
        return {d.name for d in skills_dir.iterdir() if d.is_dir()}
    except OSError as exc:
        print(f"ERROR: cannot read {skills_dir}: {exc}", file=sys.stderr)
        return None


def _scan_text(text: str) -> list[tuple[int, str, bool, str]]:
    """Return (lineno, skill_name, is_imperative, line) for each reference.

    HTML comment blocks are blanked (newlines preserved, so line numbers in the
    report still match the file on disk).
    """
    def _blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    scrubbed = _COMMENT_RE.sub(_blank, text)

    hits: list[tuple[int, str, bool, str]] = []
    for lineno, line in enumerate(scrubbed.splitlines(), start=1):
        imperative = bool(_IMPERATIVE_RE.search(line))
        # One line often names both forms of the same path ("`.claude/skills/x`
        # (or `templates/skills/x`)"). That is one reference, not two.
        for name in dict.fromkeys(m.group(1) for m in _SKILL_REF_RE.finditer(line)):
            hits.append((lineno, name, imperative, line.strip()))
    return hits


def scan(templates_dir: Path, known: set[str]) -> tuple[list[dict], list[dict]]:
    """Scan every template .md file. Return (dangling_imperative, dangling_mentions)."""
    bad: list[dict] = []
    mentions: list[dict] = []
    for path in sorted(templates_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"WARNING: cannot read {path}: {exc}", file=sys.stderr)
            continue
        for lineno, name, imperative, line in _scan_text(text):
            if name in known:
                continue
            record = {"path": path, "line": lineno, "skill": name, "text": line}
            (bad if imperative else mentions).append(record)
    return bad, mentions


def _report(bad: list[dict], repo_root: Path) -> None:
    """Print dangling imperative references grouped by skill name."""
    by_skill: dict[str, list[dict]] = defaultdict(list)
    for rec in bad:
        by_skill[rec["skill"]].append(rec)

    print(
        f"FAIL: {len(bad)} imperative reference(s) to {len(by_skill)} skill(s) that do "
        f"not exist in templates/skills/.",
        file=sys.stderr,
    )
    for name in sorted(by_skill):
        recs = by_skill[name]
        print(f"\n  '{name}'  ({len(recs)} reference(s)):", file=sys.stderr)
        for rec in recs[:10]:
            rel = rec["path"].relative_to(repo_root)
            print(f"    - {rel}:{rec['line']}", file=sys.stderr)
            print(f"        {rec['text'][:120]}", file=sys.stderr)
        if len(recs) > 10:
            print(f"    ... and {len(recs) - 10} more", file=sys.stderr)
    print(
        "\nFix: author the skill under templates/skills/<name>/, repoint the "
        "reference at a skill that exists, or delete it. Do NOT leave the caller "
        "failing open — a step that warns and proceeds is indistinguishable from "
        "an absent one (see docs/known-issues/build-pipeline.md KI-BP-007).",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point. 0 = clean, 1 = dangling imperative refs, 2 = unreadable skills dir."""
    parser = argparse.ArgumentParser(description="Validate skill references in template prose.")
    parser.add_argument("--repo-root", default=str(_REPO_ROOT),
                        help=f"Repo root. Default: {_REPO_ROOT}")
    parser.add_argument("--verbose", action="store_true",
                        help="Also list non-imperative mentions of unknown skills.")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    templates_dir = repo_root / "templates"

    known = load_skill_names(templates_dir)
    if known is None:
        return 2

    bad, mentions = scan(templates_dir, known)

    if args.verbose and mentions:
        print(f"NOTE: {len(mentions)} descriptive mention(s) of unknown skills "
              f"(not failed on):")
        for rec in mentions:
            print(f"  {rec['path'].relative_to(repo_root)}:{rec['line']}  '{rec['skill']}'")

    if not bad:
        print(f"OK: every imperative skill reference resolves ({len(known)} skills known).")
        return 0

    _report(bad, repo_root)
    return 1


if __name__ == "__main__":
    sys.exit(main())
