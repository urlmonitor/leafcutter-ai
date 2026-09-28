"""
MODULE: unit_tests/ac_store/_tkt_500f_generators.py
GOAL: Drive the REAL AC-to-ticket generators for the TKT-500f-5 / TKT-500f-6
      test families and hand back the resulting ticket as an inspectable object.
BUSINESS CONTEXT: The cluster's subject is that two generators must not drift,
      so the tests have to exercise both for real — the direct path and the
      goal path — rather than one of them plus a mock of the other.
ARCHITECTURE / PATCHING POSTURE: nothing here patches anything. Commit
      8b2b899ae split scripts/goal_to_epic.py into 14 sibling modules under
      scripts/ac_store/; after that split a ``patch("goal_to_epic.X")`` stops
      intercepting, because each name is defined AND called inside its own
      sibling and resolved through that module's globals — ten such patches
      passed while silently executing the real code. This module sidesteps the
      hazard entirely by invoking the real entry points:

        * direct path  — generate_ticket_from_ac.main() with real argv;
        * goal path    — epic_tickets.generate_tickets_for_leaves(), which
                         shells out to generate_ticket_from_ac.py for real.

COVERS: (support module — no test functions live here)
"""

from __future__ import annotations

import io
import logging
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from _tkt_500f_fixtures import write_ac_store  # noqa: F401  (path setup runs on import)

import epic_tickets  # noqa: E402
from generate_ticket_from_ac import main as generator_main  # noqa: E402


# ---------------------------------------------------------------------------
# Generated-ticket value object
# ---------------------------------------------------------------------------


@dataclass
class Generated:
    """One generated ticket plus everything the generator said while producing it.

    Attributes:
        text: The full ticket text (frontmatter + body). For the write paths
            these are the bytes read back off disk.
        frontmatter: The parsed YAML frontmatter, or ``{}`` when unparseable.
        warnings: Every WARNING-or-higher log record emitted during generation,
            concatenated with anything the generator wrote to stderr. Both
            channels are captured because the AC says only "records a warning";
            the it_requirements prefer the project logger, but a stderr write is
            still a recorded warning and must not read as silence.
        exit_code: ``main()``'s return value, or the ``SystemExit`` code.
        written_path: Path the ticket was written to, or ``None`` for a dry run
            and for a generation that wrote nothing. Only valid as a presence
            marker — the temporary directory is gone by the time a caller sees
            it, so read :attr:`text` for content.
    """

    text: str = ""
    frontmatter: dict = field(default_factory=dict)
    warnings: str = ""
    exit_code: int | None = None
    written_path: Path | None = None

    def has_test_requirements_heading(self) -> bool:
        """Return True when the body carries a ``## Test Requirements`` heading.

        Returns:
            bool: Whether the heading appears as its own line.
        """
        return any(
            line.strip() == "## Test Requirements" for line in self.text.splitlines()
        )

    def agents(self) -> dict:
        """Return the frontmatter ``agents:`` map.

        Returns:
            dict: Agent-name -> status, or ``{}`` when absent.
        """
        agents = self.frontmatter.get("agents")
        return agents if isinstance(agents, dict) else {}

    def phase_agents(self) -> set[str]:
        """Return the agent names the ticket dispatches as phases.

        An agent explicitly marked ``not_needed`` is listed but never
        dispatched, so it is not a phase agent of this ticket.

        Returns:
            set[str]: Agent names whose status is anything but ``not_needed``.
        """
        return {
            name
            for name, status in self.agents().items()
            if str(status).strip() != "not_needed"
        }

    def signoff_agents(self) -> set[str]:
        """Return the agent names listed as checkboxes under ``## Sign-offs``.

        Returns:
            set[str]: Agent names parsed from the sign-off checkbox list.
        """
        names: set[str] = set()
        in_section = False
        for line in self.text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                in_section = stripped == "## Sign-offs"
                continue
            if in_section and stripped.startswith("- ["):
                body = stripped.split("]", 1)[-1].strip()
                if body:
                    names.add(body.split()[0].strip("`"))
        return names


def parse_frontmatter(text: str) -> dict:
    """Parse the leading ``---``-delimited YAML frontmatter block of *text*.

    Scans for the closing delimiter line-by-line rather than splitting on
    ``---``, so a body containing a horizontal rule cannot corrupt the parse.

    Args:
        text: Full ticket text.

    Returns:
        dict: The parsed frontmatter, or ``{}`` when absent or unparseable.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            try:
                parsed = yaml.safe_load("\n".join(lines[1:idx]))
            except yaml.YAMLError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
    return {}


def extract_requirements_section(text: str) -> str | None:
    """Return the ``## Test Requirements`` section body of *text*.

    Args:
        text: Full ticket text.

    Returns:
        str | None: Everything between the heading and the next ``## `` heading,
        stripped; ``None`` when the heading is absent.
    """
    collected: list[str] = []
    in_section = False
    for line in text.splitlines():
        if line.strip().startswith("## "):
            if in_section:
                break
            in_section = line.strip() == "## Test Requirements"
            continue
        if in_section:
            collected.append(line)
    if not in_section:
        return None
    return "\n".join(collected).strip()


# ---------------------------------------------------------------------------
# Entry-point invocation
# ---------------------------------------------------------------------------


class _WarningCollector(logging.Handler):
    """Root-logger handler that accumulates WARNING-or-higher messages."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Append *record*'s formatted message to the collected list.

        Args:
            record: The log record being emitted.
        """
        self.messages.append(record.getMessage())


def _run_generator_main(argv: list[str]) -> tuple[str, str, int | None]:
    """Invoke ``generate_ticket_from_ac.main`` with real argv, capturing output.

    Args:
        argv: Argument vector, exactly as the CLI would receive it.

    Returns:
        tuple: (stdout text, combined warning text, exit code).
    """
    collector = _WarningCollector()
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.addHandler(collector)
    if previous_level > logging.WARNING or previous_level == logging.NOTSET:
        root_logger.setLevel(logging.WARNING)

    out, err = io.StringIO(), io.StringIO()
    code: int | None
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = generator_main(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    finally:
        root_logger.removeHandler(collector)
        root_logger.setLevel(previous_level)

    return out.getvalue(), "\n".join([*collector.messages, err.getvalue()]), code


def generate_dry_run(ac: dict, ac_id: str) -> Generated:
    """Generate a ticket via ``main(--dry-run)`` and return it un-written.

    Args:
        ac: The fixture AC record.
        ac_id: The AC id to generate from.

    Returns:
        Generated: The ticket text, frontmatter, warnings and exit code.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ac_root = write_ac_store(Path(tmpdir) / "acs", ac_id, ac)
        text, warnings, code = _run_generator_main(
            ["--ac", ac_id, "--ac-root", str(ac_root), "--dry-run"]
        )
    return Generated(
        text=text,
        frontmatter=parse_frontmatter(text),
        warnings=warnings,
        exit_code=code,
    )


def _write_path_argv(ac_id: str, ac_root: Path, tickets_root: Path) -> list[str]:
    """Return the argv for a real (non-preview) generation.

    Args:
        ac_id: The AC id to generate from.
        ac_root: The throwaway AC store root.
        tickets_root: Directory the ticket is written into.

    Returns:
        list[str]: Argument vector for ``main()``.
    """
    return [
        "--ac", ac_id,
        "--ac-root", str(ac_root),
        "--tickets-root", str(tickets_root),
        "--location-kind", "standalone",
    ]


def generate_written(ac: dict, ac_id: str) -> Generated:
    """Generate a ticket via the REAL write path and read the artifact back.

    This is the real-effect round-trip: the generator writes an actual file to a
    temporary tickets root and the bytes are read back off disk, rather than
    asserting on a string the test itself assembled.

    Args:
        ac: The fixture AC record.
        ac_id: The AC id to generate from.

    Returns:
        Generated: ``written_path`` is ``None`` when the generator wrote nothing.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ac_root = write_ac_store(tmp / "acs", ac_id, ac)
        tickets_root = tmp / "tickets"
        tickets_root.mkdir()
        _, warnings, code = _run_generator_main(
            _write_path_argv(ac_id, ac_root, tickets_root)
        )
        written = sorted(tickets_root.rglob("*.md"))
        text = written[0].read_text(encoding="utf-8") if written else ""
        path = written[0] if written else None
    return Generated(
        text=text,
        frontmatter=parse_frontmatter(text),
        warnings=warnings,
        exit_code=code,
        written_path=path,
    )


def generate_for_absent_ac(ac_id: str) -> Generated:
    """Drive the write path against an EMPTY store — a genuinely failed generation.

    The contrast arm for TKT-500f-6-iii-a's failure angle: this is what "the
    generator did not produce a ticket" looks like, so a deliberately
    section-less ticket can be shown to look like something else.

    Args:
        ac_id: An AC id that does not exist in the (empty) store.

    Returns:
        Generated: ``written_path`` is ``None`` when nothing was written.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ac_root = tmp / "acs"
        (ac_root / "fixture-component").mkdir(parents=True)
        tickets_root = tmp / "tickets"
        tickets_root.mkdir()
        _, warnings, code = _run_generator_main(
            _write_path_argv(ac_id, ac_root, tickets_root)
        )
        written = sorted(tickets_root.rglob("*.md"))
    return Generated(
        warnings=warnings,
        exit_code=code,
        written_path=written[0] if written else None,
    )


def generate_via_goal_path(ac: dict, ac_id: str) -> Generated:
    """Generate a ticket through the GOAL path — the other of the two generators.

    Drives ``epic_tickets.generate_tickets_for_leaves``, which shells out to
    ``generate_ticket_from_ac.py`` as a real subprocess with ``--location-kind
    epic_member``. Nothing is mocked, so this exercises the genuine second
    emission point the TKT-500f-6 no-drift rule is about.

    Args:
        ac: The fixture AC record.
        ac_id: The AC id to generate from.

    Returns:
        Generated: The ticket as the goal path produced it on disk.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ac_root = write_ac_store(tmp / "acs", ac_id, ac)
        tickets_root = tmp / "tickets"
        tickets_root.mkdir()
        paths = epic_tickets.generate_tickets_for_leaves([ac_id], ac_root, tickets_root)
        path = Path(paths[0]) if paths else None
        text = path.read_text(encoding="utf-8") if path and path.exists() else ""
    return Generated(
        text=text,
        frontmatter=parse_frontmatter(text),
        exit_code=0,
        written_path=path,
    )


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [TKT-500f-5 / -6 cluster/test-writer]: Split out of
  _tkt_500f_support.py against the 400-line .py limit. Generated.written_path is
  documented as a presence marker only: it points inside a TemporaryDirectory
  that is already gone when the caller sees it, and a test that re-read it
  failed with FileNotFoundError rather than the AssertionError it meant to
  report — which also slipped past pytest_ac_enforcement's xfail, since that
  plugin masks assertion failures rather than arbitrary exceptions.
====================================================================
"""
