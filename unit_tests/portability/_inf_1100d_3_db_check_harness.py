"""
MODULE: _inf_1100d_3_db_check_harness
AC: INF-1100d-3-i -- "'Not configured' and 'configured but unreachable' are
    different reports, and neither shows a password"
    INF-1100d-3-ii -- "A database test run without the setting stops and
    names the missing setting"
GOAL: Shared, test-only fixture builders and path constants for the two ACs'
    single shipped module (scripts/db_check/checker.py -- one reader of
    testing_context.db_connection_test, per both ACs' own "one reader"
    it_requirements). Centralises project-fixture construction so
    test_inf_1100d_3_i.py and test_inf_1100d_3_ii.py cannot drift from each
    other on what "P1/P2/P3" mean.
BUSINESS CONTEXT: Both AC test_specs require REAL on-disk projects (a real
    .claude/skills_config.json, written with json.dump -- never a hand-typed
    string, per unit_tests/README.md #4 / the Fixture Authenticity Rule) and
    REAL subprocess invocation of the shipped CLI / a pattern-shaped pytest
    file, never an import-and-call-directly shortcut and never a source-text
    grep (CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally, Not by
    Grep"). No test here spawns scripts/build.py (CLAUDE.md "Tests must not
    spawn their own build.py"); the self-hosted layout already has
    scripts/db_check/checker.py resolvable directly off SCRIPTS_DIR, which
    doubles as the "deployed scripts/ tree" an adopter project would get
    from build.py, per the module's own build_phases_script_deploy.py
    docstring precedent (self-hosted "deployed" == this same source tree).
NOTE: Neither this harness nor either test file imports
    scripts.db_check.checker (or db_check.checker) at module scope. The
    module does not exist yet -- test-writer runs before python-coder -- so
    every import happens lazily, inside a test body, so a missing module
    surfaces as a per-test ImportError/ModuleNotFoundError (a valid red
    state per this repo's test-writer contract) rather than a single
    collection error that swallows every test in the file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
DB_CHECK_DIR = SCRIPTS_DIR / "db_check"
CHECKER_MODULE_PATH = DB_CHECK_DIR / "checker.py"

# RFC 5737 TEST-NET-1 -- guaranteed non-routable. Used to make "a database
# driver connection was actually attempted" observable as a hang/timeout
# from the OUTSIDE (subprocess.run(timeout=...)) rather than an ambiguous
# fast "connection refused", which a black-hole address does not produce.
BLACKHOLE_HOST = "192.0.2.1"
BLACKHOLE_PORT = "54329"

# P3 fixture for INF-1100d-3-i: "configured but unreachable" (that database
# stopped). Credentials deliberately match the AC's own criteria text
# verbatim so the credential-leak test has a real password to look for.
P3_HOST = "db.internal"
P3_PORT = 5432
P3_DATABASE = "app_test"
P3_USER = "app"
P3_PASSWORD = "s3cret"
P3_ADDRESS = f"postgresql://{P3_USER}:{P3_PASSWORD}@{P3_HOST}:{P3_PORT}/{P3_DATABASE}"

# P3 fixture for INF-1100d-3-ii: same host/port/database, different
# (non-secret) credentials -- this AC's own criteria text names this exact
# string as the value the resolver must return verbatim.
RESOLVER_P3_ADDRESS = f"postgresql://app:app@{P3_HOST}:{P3_PORT}/{P3_DATABASE}"

# RFC 5737 TEST-NET-3 -- a second, distinct non-routable address used by the
# seam test's stub resolver so its "unreachable" outcome cannot be confused
# with P3's real fixture address.
STUB_RESOLVER_ADDRESS = "postgresql://stub:stub@203.0.113.5:9999/stubdb"

PSYCOPG2_STUB_SOURCE = '''"""Stub psycopg2 -- records any connect() attempt to a flag file so the
PARENT test process (which only observes this subprocess's exit/output) can
prove zero connection attempts occurred for an unconfigured setting. This
file is written into a temp project's own root and that root is placed
FIRST on the child's PYTHONPATH, so it shadows any real psycopg2 install.
"""
from pathlib import Path

_FLAG = Path(__file__).resolve().parent / "CONNECT_ATTEMPTED.flag"


def connect(*args, **kwargs):
    _FLAG.write_text(
        "connected: args=%r kwargs=%r" % (args, kwargs), encoding="utf-8"
    )
    raise RuntimeError(
        "stub psycopg2.connect() called -- a real driver connection was "
        "attempted for what should have been an unconfigured setting"
    )
'''

PATTERN_SHAPED_TEST_SOURCE = '''"""Pattern-shaped DB test -- unit_tests/README.md Step 2b shape, with setUp
calling the shared resolver instead of a literal connection string (per
INF-1100d-3-ii's own doc_links relevance note on templates/agents/
test-writer.md Step 2b)."""
import unittest
from pathlib import Path

from db_check.checker import resolve_test_db_address

_PROJECT_ROOT = Path(__file__).resolve().parent


class TestDbPatternShaped(unittest.TestCase):
    def setUp(self):
        address = resolve_test_db_address(_PROJECT_ROOT)
        import psycopg2

        self.conn = psycopg2.connect(address)
        self.conn.autocommit = False

    def tearDown(self):
        if hasattr(self, "conn"):
            self.conn.rollback()
            self.conn.close()

    def test_pattern_body_placeholder(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
'''


def make_tmp_dir(prefix: str) -> Path:
    """Fresh temp directory (never a project subdirectory -- unit_tests/README.md
    output rules)."""
    return Path(tempfile.mkdtemp(prefix=prefix))


def write_project(tmp_path: Path, testing_context: dict[str, Any]) -> Path:
    """Write a REAL ``.claude/skills_config.json`` (via ``json.dump``, never
    a hand-typed literal -- unit_tests/README.md #4 / Fixture Authenticity
    Rule) for a fresh temp 'adopter project' and return its root.

    ``testing_context`` is always written as a present (possibly empty)
    object. This matters: config_loader.load_config()'s merge is
    ``{**defaults, **project_config}`` -- a SHALLOW top-level merge. If the
    project config omits the ``testing_context`` key entirely, the merge
    falls through to the PACKAGE DEFAULT's ``testing_context`` object
    wholesale, which (as of this worktree, pending INF-1100d-4) still ships
    a real address. Passing an explicit dict here -- even ``{}`` for
    "db_connection_test not set at all" -- makes the project's own
    (present) testing_context object discard the package default's
    testing_context entirely, so "unset" is proven by the project fixture
    itself rather than by relying on the package default happening to be
    empty at read time.
    """
    project_root = tmp_path / "adopter_project"
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    config: dict[str, Any] = {"testing_context": testing_context}
    (claude_dir / "skills_config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    return project_root


def run_checker_cli(
    project_root: Path,
    *,
    env_overrides: dict[str, str] | None = None,
    timeout: float = 8.0,
) -> subprocess.CompletedProcess:
    """Invoke the shipped checker CLI as a real subprocess -- the way the
    test runner invokes it (INF-1100d-3-i's own test_spec
    ``surface_invoked``: "the shipped test-database checker CLI, run as a
    subprocess the way the test runner invokes it")."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(CHECKER_MODULE_PATH), "--target-dir", str(project_root)],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def write_pattern_shaped_project(tmp_path: Path, testing_context: dict[str, Any]) -> dict[str, Path]:
    """Build a temp adopter project containing BOTH a real skills_config.json
    and a real Step-2b-pattern-shaped pytest file that imports the shared
    resolver via the SAME import path an adopter project's own deployed
    ``scripts/`` tree would expose it under (``db_check.checker``, per
    INF-1100d-3-ii it_requirements #5). A stub ``psycopg2.py`` sits beside
    the pattern file so any *actual* connect() attempt is observable via a
    flag file, without requiring a real psycopg2 install in this test env.
    """
    project_root = write_project(tmp_path, testing_context)
    (project_root / "psycopg2.py").write_text(PSYCOPG2_STUB_SOURCE, encoding="utf-8")
    pattern_file = project_root / "test_pattern_shaped.py"
    pattern_file.write_text(PATTERN_SHAPED_TEST_SOURCE, encoding="utf-8")
    return {
        "project_root": project_root,
        "pattern_file": pattern_file,
        "connect_flag": project_root / "CONNECT_ATTEMPTED.flag",
    }


def run_pattern_shaped_pytest(
    paths: dict[str, Path], timeout: float = 8.0
) -> subprocess.CompletedProcess:
    """Run the pattern-shaped test file as a REAL pytest subprocess
    (INF-1100d-3-ii's own test_spec ``surface_invoked``: "a DB test written
    in the shipped Step 2b pattern shape, run by pytest as a subprocess").

    PYTHONPATH puts the temp project root FIRST (so the psycopg2 stub
    shadows any real driver), then SCRIPTS_DIR (the self-hosted stand-in for
    an adopter project's own deployed ``scripts/`` tree) so
    ``from db_check.checker import resolve_test_db_address`` resolves the
    same way it would in a real install.
    """
    env = os.environ.copy()
    parts = [str(paths["project_root"]), str(SCRIPTS_DIR)]
    existing = env.get("PYTHONPATH")
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(paths["pattern_file"]),
            "-q",
            "-rA",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        cwd=str(paths["project_root"]),
        env=env,
        timeout=timeout,
    )
