"""
MODULE: _lint_ruff
GOAL: Run ruff the ONE way every mode of the lint gate runs it, and turn its
    answer into structured findings -- or into a typed failure when ruff did
    not give a verdict.
BUSINESS CONTEXT: BP-1300e-1-i. The staged, full and files modes must differ
    only in WHAT bytes ruff is shown, never in how it is invoked: one argv
    builder, always `--force-exclude` (ruff given explicit paths ignores the
    configuration's exclude list otherwise, and the gate would refuse exactly
    the files CI skips), never `--isolated`, `--fix`, `--unsafe-fixes` or
    `--exit-zero`. A ruff answer that cannot be parsed is a could-not-check,
    not an empty list of findings.
ARCHITECTURE: Stdlib only. `build_argv`, `parse_concise`, `classify_failure`,
    `label_predates` and `line_text` are pure. `run_ruff` is the I/O edge.
    A staged blob is judged on stdin with `--stdin-filename <repo-relative
    path>` and ruff's cwd set to the subject root, so configuration,
    per-file-ignores and `--force-exclude` resolve against the real path while
    the staged bytes are judged. ruff cannot say whether it EXCLUDED a stdin
    file or found it clean (both print "All checks passed!"), so a clean blob
    is followed by one probe with a sentinel that always fails to parse
    (`invalid-syntax` is reported under every selection): a finding comes
    back only for a file ruff admits.

DECISION HISTORY
- 2026-10-12 [python-coder/BP-1300e-1-i, -ii, -iii]: Created.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from _lint_report import Finding

logger = logging.getLogger(__name__)

RUN_TIMEOUT = 300
SENTINEL = b"(\n"
_FINDING = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+): (?P<rest>\S.*)$")
_NOISE = (
    re.compile(r"^Found \d+ errors?\.$"),
    re.compile(r"^All checks passed!$"),
    re.compile(r"^\[\*\] .*"),
    re.compile(r"^No fixes available.*"),
    re.compile(r"^\s*$"),
)
_CONFIG_FAILURE = re.compile(r"Failed to (?:load configuration|parse) [`'\"]?([^`'\"\n]+?)[`'\"]?\s*(?:\n|$)")
_LINE_BREAK = re.compile(r"\r\n|\r|\n")


class RuffFailure(Exception):
    """ruff gave no verdict; carries the could_not_check reason and detail."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class RuffRun:
    """What one ruff process said."""

    returncode: int
    stdout: str
    stderr: str


def _fail(reason: str, detail: str) -> NoReturn:
    """Raise RuffFailure (the single raise site for ruff-side failures)."""
    raise RuffFailure(reason, detail)


def build_argv(
    prefix: tuple[str, ...],
    select: tuple[str, ...] | None,
    *,
    targets: tuple[str, ...] = (),
    stdin_filename: str | None = None,
    show_files: bool = False,
) -> list[str]:
    """Build ruff's argv; the only place an invocation is composed (pure).

    Args:
        prefix: The located argv prefix (module or executable form).
        select: A step's ``--select`` rule codes, or None to use the project's own.
        targets: Paths to check (files and full modes).
        stdin_filename: Repo-relative name of the blob on stdin (staged mode).
        show_files: List the files ruff would check instead of checking them.
    """
    argv = [*prefix, "check", "--force-exclude", "--no-cache"]
    if show_files:
        return [*argv, "--show-files", *targets]
    argv += ["--output-format", "concise"]
    if select:
        argv += ["--select", ",".join(select)]
    if stdin_filename is not None:
        return [*argv, "--stdin-filename", stdin_filename, "-"]
    return [*argv, *targets]


def run_ruff(argv: list[str], cwd: Path, stdin: bytes | None = None) -> RuffRun:
    """Run one ruff process in *cwd*; an unlaunchable ruff is a typed failure."""
    try:
        done = subprocess.run(argv, cwd=str(cwd), input=stdin, capture_output=True, check=False, timeout=RUN_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("cannot run ruff %s: %s", argv[:3], exc)
        _fail("ruff_failed_to_start", f"ruff could not be launched: {exc}")
    return RuffRun(done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"))


def classify_failure(run: RuffRun, root: Path) -> tuple[str, str]:
    """Name why ruff gave no verdict: an unreadable configuration, or a failed start (pure)."""
    text = (run.stderr.strip() or run.stdout.strip() or f"ruff exited {run.returncode}")[:600]
    config = _CONFIG_FAILURE.search(run.stderr)
    if config is None:
        return "ruff_failed_to_start", f"ruff exited {run.returncode} before judging any file: {text}"
    named = os.path.relpath(config.group(1), root) if os.path.isabs(config.group(1)) else config.group(1)
    return "ruff_config_unreadable", f"the ruff configuration {named.replace(os.sep, '/')} could not be read: {text}"


def parse_concise(text: str, root: Path) -> list[tuple[str, int, int, str, str]]:
    """Parse ruff's concise output into (path, line, col, code, message) tuples (pure).

    Raises:
        RuffFailure: internal_error, for any line that is neither a finding nor ruff's own summary.
    """
    found = []
    for raw in text.splitlines():
        match = _FINDING.match(raw)
        if match is None:
            if any(noise.match(raw) for noise in _NOISE):
                continue
            _fail("internal_error", f"unparseable ruff output line: {raw!r}")
        code, _, message = match["rest"].partition(" ")
        path = match["path"].replace("\\", "/")
        if os.path.isabs(path):
            path = Path(os.path.relpath(path, root)).as_posix()
        found.append((path, int(match["line"]), int(match["col"]), code.rstrip(":"), message.removeprefix("[*] ").strip()))
    return found


def _findings(run: RuffRun, root: Path, step_name: str) -> list[Finding]:
    """Turn one finished ruff run into findings, or raise when it gave no verdict."""
    if run.returncode not in (0, 1):
        _fail(*classify_failure(run, root))
    rows = parse_concise(run.stdout, root)
    if run.returncode == 1 and not rows:
        _fail("internal_error", f"ruff reported failure but no finding could be parsed: {run.stdout.strip()[:300]!r}")
    return [Finding(p, line, col, code, msg, step_name) for p, line, col, code, msg in rows]


def check_blob(prefix: tuple[str, ...], root: Path, rel: str, data: bytes, step) -> list[Finding]:
    """Judge one blob (staged or HEAD bytes) as if it lived at *rel*, under one step."""
    argv = build_argv(prefix, step.select, stdin_filename=rel)
    return _findings(run_ruff(argv, root, data), root, step.name)


def is_admitted(prefix: tuple[str, ...], root: Path, rel: str, step) -> bool:
    """True when ruff admits *rel* (not excluded): a sentinel blob produces a finding."""
    return bool(check_blob(prefix, root, rel, SENTINEL, step))


def check_paths(prefix: tuple[str, ...], root: Path, paths: list[str], step) -> list[Finding]:
    """Judge existing work-tree paths (files and full modes) under one step."""
    argv = build_argv(prefix, step.select, targets=tuple(paths))
    return _findings(run_ruff(argv, root), root, step.name)


def show_files(prefix: tuple[str, ...], root: Path, paths: list[str]) -> list[str]:
    """List the repo-relative files ruff would check among *paths*, excludes applied."""
    run = run_ruff(build_argv(prefix, None, targets=tuple(paths), show_files=True), root)
    if run.returncode != 0:
        _fail(*classify_failure(run, root))
    real_root = os.path.realpath(root)
    rels = (Path(os.path.relpath(os.path.realpath(line), real_root)).as_posix() for line in run.stdout.splitlines() if line.strip())
    return sorted(set(rels))


def line_text(data: bytes, line_no: int) -> str:
    """The whitespace-stripped text of line *line_no* (1-based), split as ruff splits lines (pure)."""
    lines = _LINE_BREAK.split(data.decode("utf-8", "replace"))
    return lines[line_no - 1].strip() if 0 < line_no <= len(lines) else ""


def label_predates(findings: list[Finding], current: bytes, head: bytes | None, head_findings: list[Finding]) -> None:
    """Mark findings that already fired at HEAD on an identical line (pure; mutates *findings*).

    Derived from HEAD, never from diff hunks: a finding predates the change when
    the same rule fired in the HEAD version on a line whose stripped text is
    identical (a multiset match, so one HEAD occurrence credits only one
    finding). Removing the only use of a variable at line 90 creates a NEW F841
    at untouched line 40, which a hunk-based label would wrongly call old. The
    label never changes the verdict.
    """
    if head is None:
        return
    credit = Counter((f.code, line_text(head, f.line)) for f in head_findings)
    for finding in findings:
        key = (finding.code, line_text(current, finding.line))
        if credit[key] > 0:
            credit[key] -= 1
            finding.predates_change = True
