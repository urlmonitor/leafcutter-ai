"""
MODULE: _sink_parity_emit
GOAL: The emit-mechanism half of check_sink_parity.py: the per-surface result
    type, the real ``--print-sink`` execution of a deployed script, the
    comparison of its output with the declared sink, and the scan that refuses
    a surface carrying a ``--sink`` destination of its own.
BUSINESS CONTEXT: Split out of check_sink_parity.py to keep that file under the
    file-size limit. check_sink_parity.py is the only caller and documents the
    full mechanism precedence; like it, this module ships with the package
    source only and is never deployed to a consumer's ``.leafcutter`` tree. It
    is imported as a sibling (``scripts/ci`` is ``sys.path[0]`` when the check
    runs as ``python scripts/ci/check_sink_parity.py``), the same convention
    check_consumer_install.py uses.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_QUERY_TIMEOUT_SECONDS = 30

# Matches EVERY ``emit_knowledge.py`` mention with the text after it, up to the
# next backtick (the closing inline-code tick or the closing code fence). Newlines
# are allowed so a command wrapped without a backslash is still read whole.
# Backslash-newline continuations are folded away before matching.
_EMIT_PATTERN = re.compile(r"emit_knowledge\.py([^`]*)")

# A ``--sink <value>`` / ``--sink=<value>`` argument on an emit invocation: a
# destination the surface carries itself.
_EMIT_SINK_ARG_PATTERN = re.compile(r"--sink(?:=|\s+)(\S+)")


@dataclass
class SurfaceResult:
    """Outcome of inspecting a single emit surface."""

    surface_id: str
    ok: bool
    reason: str = ""


def _resolve_via_invocation(
    script_path: Path, target_dir: Path
) -> tuple[str | None, str | None]:
    """Run a deployed script's (harvester or emit helper) ``--print-sink`` for real.

    Returns a ``(resolved_destination, error)`` pair -- exactly one of the
    two is ``None``.
    """
    harvester_path = script_path
    try:
        result = subprocess.run(
            [sys.executable, str(harvester_path), "--print-sink"],
            capture_output=True,
            text=True,
            cwd=str(target_dir),
            timeout=_QUERY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"could not invoke {harvester_path} --print-sink: {exc}"
    if result.returncode != 0:
        combined = (result.stdout + result.stderr).strip()
        return None, f"{harvester_path} --print-sink exited {result.returncode}: {combined}"
    return result.stdout.strip(), None


def _compare_resolved(
    surface_id: str, script_path: Path, target_dir: Path, declared_sink: str
) -> SurfaceResult:
    """Run *script_path* ``--print-sink`` for real and compare it with *declared_sink*."""
    resolved, error = _resolve_via_invocation(script_path, target_dir)
    if error is not None:
        return SurfaceResult(surface_id, False, error)
    # A zero exit with empty stdout would otherwise become Path("") ==
    # Path("."), reported as a path mismatch -- a confusing message for a
    # different problem. Name it instead. This also narrows `resolved` to
    # str for the comparison below, which `_resolve_via_invocation`'s
    # (str | None, str | None) signature cannot express on its own.
    if not resolved:
        return SurfaceResult(
            surface_id,
            False,
            f"{script_path} --print-sink exited 0 but printed no path, "
            "so there is no resolved destination to compare against the "
            f"declared sink {declared_sink!r}",
        )
    if Path(resolved) != Path(declared_sink):
        return SurfaceResult(
            surface_id,
            False,
            f"resolved destination {resolved!r} does not match the "
            f"declared sink {declared_sink!r}",
        )
    return SurfaceResult(surface_id, True)


def _emit_invocations(paragraph: str) -> list[str]:
    """Return the argument text after EVERY ``emit_knowledge.py`` mention in *paragraph*.

    Backslash-newline continuations are folded first so a wrapped command is
    read as the one line it is. An empty list means the paragraph never names
    the helper. Pure function: no I/O, no shared-state mutation.
    """
    return _EMIT_PATTERN.findall(re.sub(r"\\\r?\n", " ", paragraph))


def _self_carried_sink_failure(
    surface_id: str, paragraph: str, declared_sink: str
) -> SurfaceResult | None:
    """Return a failure when ANY emit invocation in *paragraph* carries ``--sink``.

    Checked before the mechanism precedence so neither an earlier prose mention
    nor a named ``harvest_learnings.py --print-sink`` can mask a surface that
    carries its own destination. Pure function: no I/O, no shared-state mutation.
    """
    for emit_args in _emit_invocations(paragraph):
        sink_arg = _EMIT_SINK_ARG_PATTERN.search(emit_args)
        if sink_arg is not None:
            literal = sink_arg.group(1)
            return SurfaceResult(
                surface_id,
                False,
                f"carries a destination of its own ({literal!r}) via --sink "
                "instead of letting the emit helper resolve the declared sink -- "
                f"the surface writes to {literal!r} while the install's declared "
                f"sink is {declared_sink!r}",
            )
    return None
