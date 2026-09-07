"""Turn whole-store guardrail-hook output into an actionable, per-owner report.

MODULE: scripts/ac_store/whole_store_report.py
COVERS: ACS-200h

The whole-store CI job (`ac-store-valid-whole-store`) applies the AC guardrail
hooks to EVERY record rather than to one pull request's diff. On a store with a
standing backlog that produces hundreds of findings, and a raw dump of hundreds
of lines is not something anybody acts on — it reads as noise, gets scrolled
past, and the job it belongs to gets ignored and eventually switched off.

So this reporter groups findings by the thing that decides WHO fixes them — the
store component the record lives under — and states one concrete, finishable
ask: clear your own component, or take any ten. A backlog nobody can see the
edge of does not get burned down; a leaderboard with a next step does.

Reads hook output on stdin or from a file; writes the report to stdout. Exit
code is always 0 on a successful parse: this reporter describes a backlog, it
does not adjudicate one. The CI job's own blocking posture is set in the
workflow, not here.

DECISION HISTORY
- 2026-09-02 [python-coder]: Created for ACS-200h. Grouping is by component
  rather than by rule kind as the PRIMARY axis, deliberately: the rule kind
  tells you what is wrong, but the component tells you whether it is YOURS,
  and only the second one makes a reader act. Kind is reported as a secondary
  breakdown. (#ACS-200h)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

#: A guardrail-hook finding line, e.g.
#:   "  docs/acceptance-criteria/ac-store/ACS-1.yaml: /abs/ACS-1.yaml: message"
#: The absolute-path repetition is optional — not every hook emits it.
_FINDING_RE = re.compile(
    r"^\s+(?P<rel>docs/acceptance-criteria/[^\s:]+\.yaml):\s*"
    r"(?:(?P<abs>/[^\s:]+\.yaml):\s*)?"
    r"(?P<message>.+)$"
)

#: Findings are grouped by the path segment directly under the store root,
#: which is the component directory (e.g. "build-orchestration").
_STORE_ROOT = "docs/acceptance-criteria"

#: How many findings a reader is asked to take when they do not own a component
#: outright. Small enough to finish in one sitting, large enough to move a
#: four-figure backlog if several people do it.
_TAKE_ANY = 10


def _component_of(rel_path: str) -> str:
    """Return the store component a finding's record belongs to.

    Args:
        rel_path: Repo-relative path to the AC YAML file.

    Returns:
        The component directory name, or "(unknown)" when the path is not
        shaped like a store record.
    """
    parts = Path(rel_path).parts
    try:
        idx = parts.index("acceptance-criteria")
    except ValueError:
        return "(unknown)"
    return parts[idx + 1] if len(parts) > idx + 1 else "(unknown)"


def _normalise_kind(message: str) -> str:
    """Collapse a finding message to a stable, countable rule-kind label.

    Strips the record-specific tail so that the same rule violated by 400
    records counts as one kind rather than 400.

    Args:
        message: The raw finding message from a guardrail hook.

    Returns:
        A truncated, digit-stripped label suitable for grouping.
    """
    head = message.split(" — ")[0].split(". ")[0]
    return re.sub(r"\d+", "N", head).strip()[:88]


def parse_findings(lines: list[str]) -> list[tuple[str, str]]:
    """Extract (relative_path, message) pairs from raw hook output.

    Args:
        lines: Raw output lines from one or more guardrail hooks.

    Returns:
        One tuple per finding, in the order encountered. Non-finding lines
        (hook banners, pass/fail summaries, blank lines) are skipped.
    """
    findings: list[tuple[str, str]] = []
    for line in lines:
        match = _FINDING_RE.match(line.rstrip("\n"))
        if match is not None:
            findings.append((match.group("rel"), match.group("message").strip()))
    return findings


def _bar(count: int, largest: int, width: int = 28) -> str:
    """Return a proportional ASCII bar for a component's finding count."""
    if largest <= 0:
        return ""
    return "#" * max(1, round(width * count / largest))


def build_report(findings: list[tuple[str, str]], component: str | None = None) -> str:
    """Render the actionable report.

    Args:
        findings: Parsed (relative_path, message) pairs.
        component: When given, restrict the report to that component and list
            each of its findings individually rather than summarising.

    Returns:
        The full report text, ready to print.
    """
    if component is not None:
        own = [(p, m) for p, m in findings if _component_of(p) == component]
        if not own:
            return (
                f"AC store — whole-store check\n\n"
                f"No findings for component {component!r}. Nothing to do here.\n"
            )
        out = [
            "AC store — whole-store check",
            "",
            f"{len(own)} finding(s) in {component}:",
            "",
        ]
        out.extend(f"  {path}\n      {message}" for path, message in own)
        return "\n".join(out) + "\n"

    total = len(findings)
    if total == 0:
        return (
            "AC store — whole-store check (ACS-200h)\n\n"
            "The whole store passes every guardrail rule. Nothing to fix.\n\n"
            "This job can now be made BLOCKING — see its comment in ci.yml.\n"
        )

    by_component = Counter(_component_of(p) for p, _ in findings)
    by_kind = Counter(_normalise_kind(m) for _, m in findings)
    largest = max(by_component.values())

    out = [
        "=" * 72,
        "AC store — whole-store check (ACS-200h)   INFORMATIONAL, NOT BLOCKING",
        "=" * 72,
        "",
        f"{total} finding(s) across {len(by_component)} component(s).",
        "",
        "This job does not fail your build. It exists because the required",
        "per-PR check only ever sees the records a pull request touched, so a",
        "record can sit invalid for weeks with every check green. That is what",
        "you are looking at: a standing backlog, not something you just broke.",
        "",
        "WHAT TO DO — pick whichever applies to you:",
        "",
        "  1. Fix the findings in the component YOU own. Find yours below and",
        f"     list them with:  python {Path(__file__).name} --component <name>",
        "",
        f"  2. If you do not own one of these, take any {_TAKE_ANY} findings and fix",
        "     them. They are mostly mechanical.",
        "",
        "Every fix moves the store toward the point where this job becomes",
        "BLOCKING and the backlog stops being able to grow again.",
        "",
        "-" * 72,
        "BY COMPONENT — who owns the work",
        "-" * 72,
    ]
    for name, count in by_component.most_common():
        out.append(f"  {count:>5}  {_bar(count, largest):<28}  {name}")

    out += [
        "",
        "-" * 72,
        "BY RULE — what is actually wrong",
        "-" * 72,
    ]
    for kind, count in by_kind.most_common():
        out.append(f"  {count:>5}  {kind}")

    out += [
        "",
        "-" * 72,
        f"REMAINING: {total}. Target: 0, at which point this job flips to blocking.",
        "-" * 72,
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        0 on success; 2 when the input file cannot be read.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Summarise whole-store AC guardrail findings by owning component, "
            "with a concrete next step. Reads hook output from a file or stdin."
        )
    )
    parser.add_argument(
        "--input",
        default=None,
        help="File containing raw hook output. Defaults to stdin.",
    )
    parser.add_argument(
        "--component",
        default=None,
        help="List every finding for one component instead of summarising.",
    )
    args = parser.parse_args(argv)

    if args.input:
        try:
            lines = Path(args.input).read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            print(f"ERROR: cannot read {args.input}: {exc}", file=sys.stderr)
            return 2
    else:
        lines = sys.stdin.read().splitlines()

    print(build_report(parse_findings(lines), component=args.component))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
