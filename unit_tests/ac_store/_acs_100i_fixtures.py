"""
MODULE: _acs_100i_fixtures
GOAL: Paths, fixture construction and real-CLI invocation for the ACS-100i-6 /
    -7 / -8 test tree. Split out of _acs_100i_support to keep both modules
    inside the project's 400-line file limit; _acs_100i_support re-exports
    everything here, so test modules import from that one module only.
BUSINESS CONTEXT: See _acs_100i_support — this tree narrows the AC-store
    "package surface" structured-spec obligation from a spelling-keyed proxy to
    an explicit `package_surface: true` declaration.
ARCHITECTURE: Fixtures are always produced by the REAL serializer
    (``yaml.safe_dump``) and written to a real file, never hand-indented in a
    string literal — Fixture Authenticity Rule (test-writer §2h.2). Validators
    are always invoked as real subprocesses, never mocked and never grepped.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# unit_tests/ac_store/_acs_100i_fixtures.py -> repo root is three parents up.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

AC_STORE_DIR = REPO_ROOT / "docs" / "acceptance-criteria"
SCHEMA_PATH = REPO_ROOT / "config" / "ac_store_schema.json"
SCHEMA_VALIDATOR_CLI = REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"
PKG_SURFACE_VALIDATOR_CLI = REPO_ROOT / "scripts" / "ac_store" / "validate_ac.py"

# Self-hosting boundary (ADR-001): scripts/commit_guardian/ exists only in a
# deployed consumer layout; in this source repo the hooks live under templates/.
COMMIT_GUARDIAN_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
AC_SCHEMA_HOOK = COMMIT_GUARDIAN_DIR / "check_ac_schema.py"

#: The five fields the structured implementation spec must carry. Mirrors
#: scripts/ac_store/validate_ac.py REQUIRED_IMPL_FIELDS and the
#: `it_requirements` object branch's `required` list in the schema.
REQUIRED_IMPL_FIELDS: tuple[str, ...] = (
    "config_schema_fragment",
    "reference_file_path",
    "n_location_rule",
    "required_skills",
    "post_write_commands",
)

#: Records named by ACS-100i-7 scenario 3 — all refused on this rule today,
#: none of them edited by this change, all of which must become accepted.
NAMED_FALSE_REFUSALS: tuple[str, ...] = (
    "BO-2000d-1",
    "BO-2000d-2",
    "BO-2000d-1-i",
    "BP-006a-1",
    "BO-1800a-1",
)

#: Phrasings a refusal may use to report a field as absent. The ACS-100i-6-i
#: "names each missing field" contract is satisfied by ANY of these; an
#: implementer inventing a sixth phrasing must add it here in the same commit.
_MISSING_FIELD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"'([A-Za-z_][A-Za-z0-9_]*)' is a required property"),
    re.compile(r"missing required key '([A-Za-z_][A-Za-z0-9_]*)'"),
    re.compile(r"missing required field:? '([A-Za-z_][A-Za-z0-9_]*)'"),
    re.compile(r"missing (?:field|key) '([A-Za-z_][A-Za-z0-9_]*)'"),
)

BASELINE_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "acs_100i_7" / "pre_change_refusal_baseline.json"
)


# ---------------------------------------------------------------------------
# Fixture construction (real serializer only)
# ---------------------------------------------------------------------------


def base_ac_record(**overrides: Any) -> dict[str, Any]:
    """Return a schema-valid AC record skeleton, with ``overrides`` applied.

    Every field is filled with a value the real schema accepts so that the ONLY
    violation in any fixture is the one the test deliberately introduces.

    Args:
        **overrides: Fields to set or replace on the skeleton.

    Returns:
        A fresh dict (never a shared reference).
    """
    record: dict[str, Any] = {
        "id": "ACS-999",
        "title": "Fixture record for the package-surface declaration tests",
        "component": "ac-store",
        "components": ["ac_store"],
        "status": "active",
        "readiness": "approved",
        "priority": "medium",
        "criteria": (
            "Given a fixture record\n"
            "When the AC-record validator evaluates it\n"
            "Then only the deliberately-introduced violation is reported"
        ),
        "level": "L3",
        "assigned_agent": "python-coder",
        "it_requirements": "A plain string implementation note.",
    }
    record.update(overrides)
    return record


def complete_impl_spec() -> dict[str, Any]:
    """Return an ``it_requirements`` object carrying all five required fields.

    ``reference_file_path`` points at a file that really exists in this repo so
    ``scripts/ac_store/validate_ac.py``'s path-resolution check also passes.
    """
    return {
        "config_schema_fragment": {"type": "object"},
        "reference_file_path": "config/ac_store_schema.json",
        "n_location_rule": "1",
        "required_skills": ["python-coder"],
        "post_write_commands": ["python scripts/build.py"],
    }


def write_ac_yaml(directory: Path, filename: str, data: dict[str, Any]) -> Path:
    """Serialize ``data`` with the REAL YAML producer and write it to disk.

    Per the Fixture Authenticity Rule (test-writer §2h.2) a serialized-format
    fixture must come from the real serializer, never a hand-indented literal —
    a hand-typed fixture reproduces the author's mental model of the format,
    which is precisely the bias that let the ``files_touched`` parser ship as a
    total no-op (EPIC-PhantomDoneFilesTouched).

    Args:
        directory: Directory to write into (normally pytest's ``tmp_path``).
        filename: File name to create.
        data: Record to serialize.

    Returns:
        Absolute path of the written file.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Real CLI invocation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CliRun:
    """Outcome of running a validator CLI as a real subprocess."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        """Combined stdout + stderr."""
        return self.stdout + self.stderr

    @property
    def refused(self) -> bool:
        """True when the CLI exited non-zero."""
        return self.returncode != 0


def run_cli(
    script: Path,
    *args: str,
    cwd: Path | None = None,
    env_overrides: dict[str, str] | None = None,
) -> CliRun:
    """Run a validator or hook script as a subprocess and capture its output.

    Args:
        script: Absolute path to the script to execute.
        *args: Arguments to pass after the script path.
        cwd: Working directory; defaults to the repo root so the script's
            git-based root resolution (``git rev-parse --show-toplevel``) finds
            this worktree, exactly as it would during a real commit.
        env_overrides: Extra environment variables — used for the commit
            hooks' production ``HOOK_TEST_STAGED_FILES`` seam.

    Returns:
        A :class:`CliRun`.
    """
    env = None
    if env_overrides:
        env = dict(os.environ)
        env.update(env_overrides)

    proc = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(cwd or REPO_ROOT),
        env=env,
        check=False,
    )
    return CliRun(proc.returncode, proc.stdout, proc.stderr)


def refusal_text(path: Path) -> str:
    """Return the combined refusal text both CLI validators produce for a file.

    ACS-100i-6 / -6-i place requirements on what a refusal *states*. Both
    ``validate_ac_schema.py`` (schema-driven) and ``validate_ac.py``
    (package-surface-specific) are AC-record validators, and the obligation may
    be reported by either, so the contract is asserted against the union of
    their real output.

    Args:
        path: Absolute path to an AC YAML file on disk.

    Returns:
        Concatenated stdout+stderr of both validators.
    """
    return (
        run_cli(SCHEMA_VALIDATOR_CLI, str(path)).output
        + "\n"
        + run_cli(PKG_SURFACE_VALIDATOR_CLI, str(path)).output
    )


# ---------------------------------------------------------------------------
# Refusal-content predicates
# ---------------------------------------------------------------------------


def fields_reported_missing(text: str) -> set[str]:
    """Extract the implementation-spec fields a refusal reports as ABSENT.

    Only the five structured-spec field names are returned, and only when they
    appear inside a phrase that reports absence (see
    ``_MISSING_FIELD_PATTERNS``). A message that merely enumerates all five as
    context — e.g. "must supply all of: a, b, c, d, e" — is deliberately NOT
    counted, so the ACS-100i-6-i "does not name the three that were supplied"
    clause is meaningful.

    Args:
        text: Combined refusal output.

    Returns:
        The set of field names reported missing.
    """
    found: set[str] = set()
    for pattern in _MISSING_FIELD_PATTERNS:
        found.update(pattern.findall(text))
    return found & set(REQUIRED_IMPL_FIELDS)


def states_structured_spec_obligation(text: str) -> bool:
    """Return True when a refusal states the declaration -> structured-spec rule.

    The contract from ACS-100i-6: "the refusal states that a record declaring a
    package surface must carry a structured implementation spec". Satisfied
    when the text names the field being complained about, names the package
    surface, and says the spec must be structured/an object.

    Args:
        text: Combined refusal output.

    Returns:
        True when all three elements are present.
    """
    lowered = text.lower()
    names_field = "it_requirements" in lowered
    names_surface = bool(re.search(r"package[ _-]surface", lowered))
    names_shape = "structur" in lowered or "object" in lowered
    return names_field and names_surface and names_shape


def load_baseline() -> dict[str, Any]:
    """Load the pre-change whole-store refusal baseline recorded by test-writer.

    Returns:
        The parsed baseline document.

    Raises:
        AssertionError: When the baseline fixture is missing — the ACS-100i-7
            comparison is meaningless without it and must not silently skip.
    """
    assert BASELINE_FIXTURE.is_file(), (
        f"pre-change refusal baseline missing at {BASELINE_FIXTURE}. It is "
        "recorded by test-writer BEFORE the narrowing lands; regenerate it "
        "only if the store itself has legitimately changed, in a separate and "
        "clearly-labelled commit."
    )
    return json.loads(BASELINE_FIXTURE.read_text(encoding="utf-8"))
