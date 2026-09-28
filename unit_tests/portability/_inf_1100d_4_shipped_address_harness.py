"""
MODULE: _inf_1100d_4_shipped_address_harness
AC: INF-1100d-4 -- "The package refuses to ship a database address again"
    INF-1100d-4-i -- "The address check flags real-looking addresses, allows
    obvious placeholders, and leaves unshipped history alone"
GOAL: Shared, test-only fixture builders and the subprocess-invocation
    contract for the not-yet-implemented shipped-address check CLI, so
    ``test_inf_1100d_4.py`` and ``test_inf_1100d_4_i.py`` cannot drift from
    each other on how the check is invoked or how a shipped-shaped temp tree
    is built.

CLI CONTRACT ASSUMED (documented here so a reader -- and this AC pair's
    implementer -- does not have to reverse it out of assertions; the check
    does not exist yet, so this is test-writer's chosen target interface,
    not an already-committed one):

    ``python scripts/portability/check_shipped_addresses.py [--source-root
    PATH] [--build-root PATH]``

    - No flags: scan the DECLARED shipped roots (``templates/`` -- including
      ``templates/docs/`` -- and ``config/``) relative to the current
      working directory. This is the normal-suite entry point.
    - ``--source-root PATH``: treat ``PATH`` as a repo-root-shaped
      directory and scan only ``PATH/templates`` and ``PATH/config`` --
      the SAME declared-roots rule as the no-flags case, just rooted
      elsewhere. Anything else under ``PATH`` (a ``docs/`` tree, an
      ``AC-store`` YAML, etc.) is never visited, by construction, not by an
      exclusion list -- this is the property INF-1100d-4-i's seam test
      exists to prove.
    - ``--build-root PATH``: treat ``PATH`` as an already-built output
      directory (a deployed layout with no ``templates/``/``config/``
      segmentation of its own) and scan it in full.
    - Exit 0 on a clean run, printing a summary that states how many
      shipped files were scanned (matched by ``scanned_file_count()``
      below) -- a scan that found zero files must not report success
      (INF-1100d-4's own it_requirements).
    - Exit non-zero when any address is found, printing one line per
      finding naming the file and line number.

BUSINESS CONTEXT: CLAUDE.md "Tests must not spawn their own build.py"
    forbids a ``build.py`` subprocess here; INF-1100d-4's own
    it_requirements says built-output coverage uses a SYNTHETIC built tree
    until TQ-600a's shared session layout lands -- ``deployed_agent_file()``
    below builds that synthetic tree by hand, never via ``build.py``.

NOTE ON THE FORBIDDEN LITERAL: the AC pair's own NQ1 decision is that the
    check itself carries no literal of the old shipped address, and this
    harness holds the same line for every test file it backs: the address
    string is assembled from parts by ``build_address()`` /
    ``old_shipped_address()``, and the pre-fix proof's exact bytes are read
    from git (``git_show()``) rather than reconstructed by hand -- the
    legacy shipped address never appears as a single hand-typed literal
    anywhere in this module or the test files that import it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The pinned pre-work commit named by INF-1100d-4's own it_requirements:
# "The pre-fix proof must use the real bytes of the five shipped source
# files ... as they stood at the pinned pre-work commit e919a24f."
PRE_FIX_COMMIT = "e919a24f"

# The five shipped source files INF-1100d-4's criteria names as carrying
# the address at the pinned pre-work commit. (See test_inf_1100d_4.py's own
# module docstring for the documented, git-verified discrepancy in this
# list -- one of these five does not actually contain a matching address at
# this commit.)
PRE_FIX_SHIPPED_FILES = (
    "templates/agents/test-writer.md",
    "templates/agents/test-runner.md",
    "templates/workflows/test.md",
    "config/skills_config.default.json",
    "config/skills_config.schema.json",
)


def check_script_path() -> Path:
    """Locate the not-yet-implemented shipped-address check CLI.

    Resolved lazily -- called from inside each test function, never
    imported or stat'd at module collection time -- so a not-yet-existing
    script fails only the test that actually invokes it, not collection of
    this whole module (unit_tests/README.md's red-baseline discipline: each
    test must fail individually).
    """
    return REPO_ROOT / "scripts" / "portability" / "check_shipped_addresses.py"


def run_check(
    *,
    source_root: Path | str | None = None,
    build_root: Path | str | None = None,
    cwd: Path | str | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the shipped-address check CLI as a REAL subprocess -- never an
    in-process import -- against the repo's real ``sys.executable``. This is
    the 'reachability' surface named by this AC pair's own
    ``test_spec.surface_invoked`` entries.
    """
    argv = [sys.executable, str(check_script_path())]
    if source_root is not None:
        argv += ["--source-root", str(source_root)]
    if build_root is not None:
        argv += ["--build-root", str(build_root)]
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )


def check_output(result: subprocess.CompletedProcess) -> str:
    """Combined stdout+stderr, the text a human or a caller would see."""
    return (result.stdout or "") + (result.stderr or "")


def scanned_file_count(output: str) -> int | None:
    """Parse a 'scanned N ... shipped file(s)' style count out of the
    check's own output. Returns None when no such count is present -- used
    to assert the it_requirement 'a scan that found zero files must not
    report success' rather than trusting a bare exit code."""
    match = re.search(r"(\d+)\s+shipped file", output, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def finding_reported(output: str, filename: str, line: int) -> bool:
    """True when ``output`` names ``filename`` at ``line`` using the
    ``<path>:<line>`` convention this codebase already uses for other
    file+line reports (e.g. ``scripts/ac_store/done_proof.py``'s
    ``f"{py_file}:{lineno}"``). Deliberately requires the filename and line
    number to appear ADJACENT with a colon between them, rather than a bare
    ``str(line) in output`` substring check, which a coincidental digit
    elsewhere in the output (a port number, another line number) could
    satisfy without the check actually having reported that finding."""
    pattern = re.escape(filename) + r".*?:" + str(line) + r"\b"
    return re.search(pattern, output) is not None


def build_address(
    scheme: str,
    host: str,
    port: int,
    database: str,
    user: str | None = None,
    password: str | None = None,
) -> str:
    """Assemble a ``<scheme>://[user[:password]@]host:port/database``
    address from parts. Never hand-typed as a single literal in a test file
    -- unit_tests/README.md's fixture-authenticity convention, and this AC
    pair's own NQ1 decision that no shipped artifact (including the tests
    proving it) carries a literal of a real-looking address."""
    if user is not None:
        credentials = f"{user}:{password}@" if password is not None else f"{user}@"
    else:
        credentials = ""
    return f"{scheme}://{credentials}{host}:{port}/{database}"


def old_shipped_address() -> str:
    """The literal legacy shipped address this whole AC pair exists to
    remove, assembled from parts (never a single hardcoded literal)."""
    return build_address(
        "postgresql", "localhost", 5403, "LIVE", user="trader", password="trader"
    )


def git_show(rel_path: str, commit: str = PRE_FIX_COMMIT) -> str:
    """Read a file's REAL bytes at ``commit`` via ``git show`` -- never a
    hand-typed reconstruction of history. Raises when the pinned history is
    unavailable, per this AC's own it_requirements: 'If that history is
    unavailable (e.g. a shallow CI clone), fail closed; never skip
    silently.'"""
    result = subprocess.run(
        ["git", "show", f"{commit}:{rel_path}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pinned pre-fix history unavailable for {commit}:{rel_path} "
            f"(fail closed, never skip silently) -- stderr={result.stderr!r}"
        )
    return result.stdout


def materialize_pre_fix_tree(tmp_path: Path, commit: str = PRE_FIX_COMMIT) -> Path:
    """Materialise the pinned pre-work commit's REAL bytes for the shipped
    source files INF-1100d-4 names, laid out under ``tmp_path`` at the same
    relative paths they ship at (``templates/...``, ``config/...``). This is
    the 'real_artifact' proof: the check runs against the actual historical
    bytes, never a reconstruction, and ``tmp_path`` is shaped so
    ``--source-root tmp_path`` scans exactly ``templates/`` + ``config/``
    under it, matching the declared-roots contract."""
    for rel_path in PRE_FIX_SHIPPED_FILES:
        content = git_show(rel_path, commit)
        dest = tmp_path / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return tmp_path


def find_line_with_address(text: str, address: str) -> int | None:
    """Return the 1-indexed line number of the first line in ``text``
    containing ``address``, or None if it does not appear. Used to derive
    an EXPECTED line number from real fetched content rather than a
    hand-counted/hardcoded literal -- unit_tests/README.md's
    assert-over-emitted-artifacts convention applied to the fixture itself,
    not just the check's output."""
    for lineno, line in enumerate(text.splitlines(), start=1):
        if address in line:
            return lineno
    return None


def write_shipped_file(tmp_path: Path, rel_path: str, lines: list[str]) -> Path:
    """Write ``lines`` (joined with newlines) to ``tmp_path/rel_path``,
    creating parent directories as needed, and return the full path."""
    dest = tmp_path / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def deployed_agent_file(tmp_path: Path, content_line: str) -> Path:
    """Build a SYNTHETIC built-layout tree by hand (never via a ``build.py``
    subprocess -- CLAUDE.md 'Tests must not spawn their own build.py', and
    this AC's own it_requirements: 'until then a synthetic built tree').
    Writes one deployed-shaped agent file at
    ``tmp_path/.leafcutter/agents/example-agent.md`` containing
    ``content_line`` and returns its path."""
    return write_shipped_file(
        tmp_path,
        ".leafcutter/agents/example-agent.md",
        ["# Example deployed agent", content_line],
    )
