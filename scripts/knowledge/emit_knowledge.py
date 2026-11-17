"""
MODULE: emit_knowledge
GOAL: Validate an agent-supplied ``entry_kind`` against the single declared
    vocabulary and append a ``knowledge_captured`` event to the
    knowledge-emission sink -- or decline non-fatally when the entry_kind is
    out of vocabulary.
BUSINESS CONTEXT: AC INF-400c-5 requires enforcement to live at the point an
    event is emitted, not only at the harvester: "a free-hand JSON append by
    an agent is how the 15 uncontrolled values arose" (it_requirements). This
    CLI is the emission helper the four shipped emit sites (signoff SKILL.md
    Section 7, and the product-owner/business-analyst/it-po v3 templates)
    call instead of hand-writing a ``knowledge_captured`` JSON line.
    AC INF-400c-5-iii additionally requires a rejection to be reported to the
    agent (naming the rejected value and candidate members) without failing
    the agent's run, and to be counted distinctly from a run that emitted
    nothing (via a separate ``--rejection-log`` sink).
ARCHITECTURE: Standalone CLI script (stdlib plus the sibling modules deployed
    beside it: ``entry_kind_vocabulary`` and ``sink_resolution``) for the
    Knowledge System component (docs/architecture/components/
    knowledge-system.md), mirroring the existing standalone-script convention
    of ``harvest_learnings.py`` and
    ``templates/skills/agent-telemetry/scripts/emit_event.py``. Reads its
    vocabulary from ``config/entry_kind_vocabulary.json`` via the shared
    ``entry_kind_vocabulary`` module so validation logic lives in one place
    (AC INF-400c-5-i), and reads the sink from the build-time declaration via
    ``sink_resolution`` (ADR-069).

Usage
-----
    python scripts/knowledge/emit_knowledge.py \\
        --agent AGENT --component COMPONENT --destination PATH \\
        --entry-kind KIND --text TEXT [--ticket TICKET] \\
        [--sink SINK_PATH] [--vocabulary VOCAB_PATH] [--rejection-log PATH]
    python scripts/knowledge/emit_knowledge.py --print-sink

``--print-sink`` is read-only: it prints the absolute sink a run without
``--sink`` would write to and exits 0 (the same bytes as
``harvest_learnings.py --print-sink``). With an absent, unusable or stale
declaration it prints the reason on stderr, prints nothing on stdout, creates
nothing and exits 1. It writes no event.

``--sink`` is optional (AC INF-700b-1, ADR-034 Amendment 1). Without it the
sink is the install's declared ``knowledge_emission_sink``, resolved through
``sink_resolution`` (ADR-069 usable-stream rule and stale-root rule) -- never a
CWD-relative default and never a path literal. When the declaration is absent,
unusable or stale nothing is created: a warning naming the reason goes to
stderr and the run exits 0. When the root is live but the log directory is
missing, only the log directory is created -- never the enduring root. An
explicit ``--sink`` or ``--rejection-log`` is honoured exactly as given.

The entry_kind ``unclassified`` is a defined non-value: it is recorded as
given, with no rejection and without joining the vocabulary.

Capture-attempt ledger (ADR-034 Amendment 2)
--------------------------------------------
After a SUCCESSFUL append the helper runs the deployed
``skills/agent-telemetry/scripts/emit_event.py`` once (``--event capture_attempt
--outcome recorded``, no ``--log``). ``--text`` that is empty, or empty once the
record's own agent, component, destination, entry_kind and ticket values and all
non-alphanumerics are removed, is refused: nothing is appended, the reason goes
to stderr, exit is 0 and one ``nothing-to-record`` attempt is written. If the
append itself fails (OSError), a stderr warning names the sink and the error,
exit is 0 and one ``failed`` attempt is written with ``--missing-target`` set to
the sink path. A
vocabulary rejection and ``--print-sink`` write no attempt. If emit_event.py is
missing or fails, a stderr warning is printed and the knowledge append stands.

Exit codes
----------
1   Only ``--print-sink`` with no usable declaration (see above).
0   Always otherwise, in both the accepted and the rejected case. This helper is
    best-effort and must never be fatal to the calling agent (AC
    INF-400c-5-iii): an out-of-vocabulary entry_kind is reported on stdout,
    counted (when ``--rejection-log`` is given), and the run continues.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from entry_kind_vocabulary import (
    default_vocabulary_path,
    load_vocabulary,
    resolve_canonical,
)
from sink_resolution import (
    deployed_output_root,
    read_usable_stream,
    refusal_message,
    stale_declaration_message,
)

UNCLASSIFIED = "unclassified"
_SINK_KEY = "knowledge_emission_sink"

logger = logging.getLogger("emit_knowledge")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="emit_knowledge",
        # No flag abbreviations: `--sin /x` must not silently mean `--sink /x`,
        # or a surface could carry its own sink past check_sink_parity.py.
        allow_abbrev=False,
        description=(
            "Validate an entry_kind against the declared vocabulary and "
            "append a knowledge_captured event to the emission sink."
        ),
    )
    # The five event fields are required unless --print-sink is given; that is
    # enforced after parsing (see _require_event_fields), not by argparse.
    parser.add_argument("--agent", help="Name of the emitting agent.")
    parser.add_argument("--component", help="Component the learning concerns.")
    parser.add_argument("--destination", help="The knowledge surface path the event targets.")
    parser.add_argument("--entry-kind", dest="entry_kind", help="The entry_kind to validate.")
    parser.add_argument("--text", help="The learning body text.")
    parser.add_argument(
        "--print-sink",
        dest="print_sink",
        action="store_true",
        help=(
            "Read-only: print the absolute declared sink and exit 0, or print "
            "the reason on stderr and exit 1. Writes no event, creates nothing."
        ),
    )
    parser.add_argument("--ticket", default=None, help="Optional ticket reference.")
    parser.add_argument(
        "--sink",
        type=Path,
        default=None,
        help=(
            "Optional path to the JSONL knowledge-emission sink (default: the "
            "build-time declared knowledge_emission_sink)."
        ),
    )
    parser.add_argument(
        "--vocabulary",
        type=Path,
        default=None,
        help="Path to the declared entry_kind vocabulary JSON (default: build-time location).",
    )
    parser.add_argument(
        "--rejection-log",
        dest="rejection_log",
        type=Path,
        default=None,
        help=(
            "Optional path to a separate rejection-count sink. A run that "
            "rejects nothing never creates this file."
        ),
    )
    args = parser.parse_args(argv)
    if not args.print_sink:
        missing = [
            flag
            for flag, value in (
                ("--agent", args.agent),
                ("--component", args.component),
                ("--destination", args.destination),
                ("--entry-kind", args.entry_kind),
                ("--text", args.text),
            )
            if value is None
        ]
        if missing:
            parser.error("the following arguments are required: " + ", ".join(missing))
    return args


def _select_candidates(members: dict[str, object], destination: str) -> list[str]:
    """Return the vocabulary members to offer as candidates for *destination*.

    Prefers members whose declared ``destination_pattern`` directory matches
    *destination*'s parent directory (AC INF-400c-5-iii: "lists the canonical
    members whose routing destination matches the destination the agent
    supplied"). Falls back to every vocabulary member when nothing matches --
    an empty candidate list on a genuine rejection would be a worse outcome
    than an over-inclusive one.

    Pure function: no I/O, no shared-state mutation.
    """
    dest_dir = str(Path(destination).parent)
    matches = []
    for name in sorted(members):
        meta = members[name]
        pattern = meta.get("destination_pattern") if isinstance(meta, dict) else None
        if isinstance(pattern, str) and str(Path(pattern).parent) == dest_dir:
            matches.append(name)
    return matches or sorted(members)


def _resolve_declared_sink() -> tuple[Path | None, str]:
    """Return ``(sink, "")`` for the declared sink, or ``(None, reason)`` when it must not be written.

    Uses ONLY the build-time declaration (ADR-069): the usable-stream rule, then
    the stale-root rule. There is deliberately no CWD-relative fallback. Reads
    the declaration only; creates nothing.
    """
    output_root = deployed_output_root()
    sink, why = read_usable_stream(output_root, _SINK_KEY)
    if sink is None:
        return None, refusal_message(output_root, "knowledge-emission sink", why)
    stale = stale_declaration_message(output_root)
    if stale is not None:
        return None, stale
    return sink, ""


def _print_sink() -> int:
    """Print the declared sink (exit 0) or the refusal reason on stderr (exit 1).

    Read-only: shares ``_resolve_declared_sink`` with the write path, so it
    reports exactly where a run without ``--sink`` would write, and creates
    nothing -- not even a missing log directory.
    """
    sink, reason = _resolve_declared_sink()
    if sink is None:
        print(f"ERROR: {reason}", file=sys.stderr)
        return 1
    print(sink)
    return 0


def _append_jsonl(path: Path, record: dict[str, object]) -> None:
    """Append *record* as one JSON line to *path*.

    Creates the missing directories above *path*. For the declared sink the
    caller has already proved the enduring root is live (``_resolve_declared_sink``),
    so only the log directory (and, in a ``<project>/debugging/logs`` layout,
    the ``debugging`` level between the live project and it) can be created --
    the enduring root itself is never recreated (ADR-069). An explicit path
    given by the caller is honoured as given.

    External I/O, wrapped per the project error-handling policy: logs a
    WARNING and re-raises so the caller (at the CLI boundary) decides how to
    proceed rather than silently losing the write.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as exc:
        logger.warning("Failed to append to %s: %s", path, exc)
        raise


def _handle_rejection(args: argparse.Namespace, members: dict[str, object]) -> None:
    """Report a rejected entry_kind and record it in the rejection log.

    Never writes to the knowledge-emission sink. Never raises: a failure to
    persist the rejection-log entry is logged and swallowed here, since the
    calling agent's run must not be blocked by this best-effort helper (AC
    INF-400c-5-iii).
    """
    candidates = _select_candidates(members, args.destination)
    print(
        f"REJECTED entry_kind {args.entry_kind!r}: not a member of the "
        "declared vocabulary. Candidate canonical members for this "
        f"destination: {candidates}",
        file=sys.stderr,
    )
    if args.rejection_log is not None:
        record = {
            "event": "knowledge_rejected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": args.agent,
            "component": args.component,
            "destination": args.destination,
            "rejected_entry_kind": args.entry_kind,
            "candidates": candidates,
        }
        try:
            _append_jsonl(args.rejection_log, record)
        except OSError:
            # Already logged by _append_jsonl. A rejection-log write failure
            # must not escalate into a failed run for the calling agent.
            pass


def _is_contentless(args: argparse.Namespace) -> bool:
    """Return True when ``--text`` carries no learning (ADR-034 A2.5).

    The text is whitespace-normalised, then every occurrence of the record's own
    agent, component, destination, entry_kind and ticket values is removed and
    every non-alphanumeric dropped. Nothing left means the text is empty or only
    restates the record's own metadata. Pure function: no I/O.
    """
    remainder = " ".join((args.text or "").split())
    descriptive = (args.agent, args.component, args.destination, args.entry_kind, args.ticket)
    for value in sorted((v for v in descriptive if v), key=len, reverse=True):
        remainder = re.sub(re.escape(value), "", remainder, flags=re.IGNORECASE)
    return not re.sub(r"[\W_]+", "", remainder)


def _record_capture_attempt(
    args: argparse.Namespace, outcome: str, missing_target: str | None = None
) -> None:
    """Write ONE ``capture_attempt`` ledger record by running the deployed emit_event.py.

    ``missing_target`` is passed as ``--missing-target`` and only for ``failed``.

    The script path is derived from the deployed layout (never a literal) and no
    ``--log`` is passed, so the telemetry stream resolves from the declaration
    (ADR-034 A2.2, A2.4). Fails open: a missing script, a launch error or a
    non-zero exit prints a stderr warning and returns, so the knowledge outcome
    already reached stands and the helper still exits 0.
    """
    script = deployed_output_root() / "skills" / "agent-telemetry" / "scripts" / "emit_event.py"
    cmd = [sys.executable, str(script), "--agent", args.agent, "--event", "capture_attempt",
           "--phase", "knowledge-capture", "--outcome", outcome]
    if args.ticket:
        cmd += ["--ticket", args.ticket]
    if missing_target is not None:
        cmd += ["--missing-target", missing_target]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"WARNING: capture attempt ({outcome}) not recorded: emit_event.py "
              f"could not run: {exc}", file=sys.stderr)
        return
    if done.returncode != 0 or done.stderr.strip():
        print(f"WARNING: capture attempt ({outcome}) not recorded: emit_event.py "
              f"exited {done.returncode}: {done.stderr.strip()}", file=sys.stderr)


def _refuse_contentless(args: argparse.Namespace) -> None:
    """Refuse contentless text: append nothing, say why on stderr, log ``nothing-to-record``."""
    print("REFUSED: --text is empty or only restates the record's own agent, component, "
          "destination, entry_kind or ticket; no knowledge event written", file=sys.stderr)
    _record_capture_attempt(args, "nothing-to-record")


def _handle_acceptance(args: argparse.Namespace, canonical_entry_kind: str) -> bool:
    """Write the validated event to the sink; return True when it was appended.

    A sink-write failure is reported and swallowed: a WARNING naming the sink
    and the error goes to stderr, one ``failed`` capture attempt with
    ``missing_target`` set to the sink path is written (telemetry is still
    writable on this path, ADR-034 A2.6), and the helper still exits 0. This
    helper's own contract is best-effort / non-fatal to the calling agent, and
    a lost knowledge write is preferable to aborting the primary task. When no
    ``--sink`` was given and the declaration cannot be used, nothing is
    created: the reason goes to stderr and the event is dropped (exit 0).
    """
    sink = args.sink
    if sink is None:
        sink, reason = _resolve_declared_sink()
        if sink is None:
            print(f"WARNING: knowledge event not recorded: {reason}", file=sys.stderr)
            return False
    event: dict[str, object] = {
        "event": "knowledge_captured",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": args.agent,
        "component": args.component,
        "destination": args.destination,
        "entry_kind": canonical_entry_kind,
        "text": args.text,
    }
    if args.ticket:
        event["ticket"] = args.ticket
    try:
        _append_jsonl(sink, event)
    except OSError as exc:
        print(f"WARNING: knowledge event not recorded: could not append to sink {sink}: {exc}",
              file=sys.stderr)
        _record_capture_attempt(args, "failed", str(sink))
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 except ``--print-sink`` without a usable declaration."""
    args = _parse_args(argv)
    if args.print_sink:
        return _print_sink()

    if _is_contentless(args):
        _refuse_contentless(args)
        return 0

    vocab_path = args.vocabulary or default_vocabulary_path()
    members = load_vocabulary(vocab_path)

    if args.entry_kind == UNCLASSIFIED:
        canonical_entry_kind = UNCLASSIFIED  # defined non-value, not a vocabulary member
    else:
        canonical_entry_kind = resolve_canonical(args.entry_kind, members)
    if canonical_entry_kind is None:
        _handle_rejection(args, members)
        return 0

    if _handle_acceptance(args, canonical_entry_kind):
        _record_capture_attempt(args, "recorded")
    return 0


if __name__ == "__main__":
    # Python automatically puts this script's own directory at sys.path[0]
    # when invoked as `python .../emit_knowledge.py`, so the top-level
    # `from entry_kind_vocabulary import ...` resolves without needing a
    # package `__init__.py` -- mirroring the standalone-script convention
    # already used by harvest_learnings.py's sibling modules.
    sys.exit(main())

# DECISION HISTORY
# ================================================================================
# - 2026-10-21 15:00 [python-coder]: A failed sink append now prints a stderr WARNING naming the sink and error and writes one `failed` capture_attempt (missing_target = sink path) instead of vanishing silently (pr-reviewer M-2). (#EPIC-ALearningAnAgentHasTodayActuallyGets/02) (ADR-034)
# - 2026-10-21 12:00 [python-coder]: Refuse empty/metadata-only --text (A2.5, writes a nothing-to-record attempt) and write ONE `recorded` capture_attempt via the deployed emit_event.py subprocess after a successful append (A2.4, fail open, no --log). (#EPIC-ALearningAnAgentHasTodayActuallyGets/02) (ADR-034)
# - 2026-10-20 14:00 [python-coder]: --sink optional (declared sink via sink_resolution, no relative fallback); "unclassified" recorded as a defined non-value; absent/unusable/stale declaration creates nothing, warns on stderr, exits 0; explicit --sink/--rejection-log honoured as given. (#EPIC-ALearningAnAgentHasTodayActuallyGets/01) (ADR-034)
# - 2026-10-20 17:00 [python-coder]: Added read-only --print-sink (same resolution as the no---sink write path; non-zero exit with a stderr reason on an absent/unusable/stale declaration); the five event flags became post-parse-required; module docstring corrected (it imports sink_resolution). (#EPIC-ALearningAnAgentHasTodayActuallyGets/01) (ADR-034)
# - 2026-10-20 19:40 [python-coder]: allow_abbrev=False so `--sin /x` is an argparse error and cannot carry a sink past check_sink_parity.py (pr-reviewer M-1). (#EPIC-ALearningAnAgentHasTodayActuallyGets/01) (ADR-034)
