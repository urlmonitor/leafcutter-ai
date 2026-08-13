"""
MODULE: test_acs_200e_validator_schema_parity
GOAL: Behavioral parity tests proving scripts/ac_store/validate_ac_schema.py
    (the standalone AC validator) actually loads and applies
    config/ac_store_schema.json, and that its verdict agrees with the
    commit-time gate (templates/scripts/commit_guardian/check_ac_schema.py).
BUSINESS CONTEXT: The standalone validator's module docstring claims it
    "Also validates the full schema against config/ac_store_schema.json", but
    as of authoring it imports only sys, pathlib, yaml, and _ac_components —
    there is no jsonschema import and no load of the schema file anywhere in
    the module. It performs hand-rolled field checks only (readiness, priority,
    components, documentation_triggers). Meanwhile the commit-time hook DOES
    load the schema and run jsonschema validation. An AC file can therefore
    print "OK: ... is valid." from the standalone validator and then be
    hard-rejected at commit time — this happened this session with two
    real AC files carrying list-form it_requirements on a package-surface AC
    (assigned_agent: python-coder, component in [build_pipeline,
    build-orchestration]), which config/ac_store_schema.json's if/then block
    (~lines 682-717) requires to be a structured object with five fields.
ARCHITECTURE: Tests are purely behavioral — they EXECUTE the real standalone
    validator as a subprocess (never grep its source) against a real on-disk
    YAML fixture produced via yaml.dump (never a hand-indented literal, per
    the Fixture Authenticity Rule), and separately invoke the exact
    jsonschema helper the commit-time hook uses
    (validate_with_jsonschema, imported from
    templates/scripts/commit_guardian/_ac_schema_validators.py) against the
    same in-memory data to establish the hook's verdict for comparison.

    Import note: this repo self-hosts (see docs/architecture/adrs/
    ADR-001-self-hosting-boundary.md) — `scripts/commit_guardian/` only
    exists in a *deployed* consumer layout produced by build.py. In this
    source repo, the hook and its helper module live under
    `templates/scripts/commit_guardian/`, so tests import
    `_ac_schema_validators` from that source location via a sys.path
    insertion rather than from a deployed `scripts/commit_guardian/` that
    does not exist here.

AC: ACS-200e — "The standalone AC validator enforces the same schema as the
    commit-time gate" (docs/acceptance-criteria/ac-store/
    ACS-200-automated-verification/ACS-200e.yaml).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

STANDALONE_VALIDATOR = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"
SCHEMA_PATH = _REPO_ROOT / "config" / "ac_store_schema.json"

# Self-hosting boundary (ADR-001): the commit-hook helper only exists under
# templates/ in this source repo; a deployed consumer layout would have it at
# scripts/commit_guardian/_ac_schema_validators.py instead.
_COMMIT_GUARDIAN_SRC_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
sys.path.insert(0, str(_COMMIT_GUARDIAN_SRC_DIR))
from _ac_schema_validators import validate_with_jsonschema  # noqa: E402

# A real, already-approved AC in the store whose component ("ac-store") is
# NOT in the schema's package-surface if/then trigger list
# (build_pipeline / build-orchestration), so it must remain valid both
# before and after the fix.
_REAL_SCHEMA_VALID_AC = (
    _REPO_ROOT
    / "docs"
    / "acceptance-criteria"
    / "ac-store"
    / "ACS-200-automated-verification"
    / "ACS-200d.yaml"
)


def _invalid_package_surface_ac_data() -> dict[str, Any]:
    """Build the exact defect scenario described in ACS-200e's notes field.

    A package-surface AC (assigned_agent: python-coder, component:
    build-orchestration) whose it_requirements is a plain list of strings
    instead of the structured object config/ac_store_schema.json's if/then
    block (lines ~682-717) requires. Every other field is filled in with a
    schema-valid value so the ONLY violation present is the it_requirements
    shape — this isolates the defect the same way the two real AC files that
    triggered this ticket did.
    """
    return {
        "id": "ACS-999",
        "title": "Fixture: package-surface AC with invalid list it_requirements",
        "component": "build-orchestration",
        "components": ["build_orchestration"],
        "status": "active",
        "criteria": (
            "Given a package-surface AC assigned to python-coder in a "
            "build-orchestration component\n"
            "When it_requirements is a plain list instead of the required "
            "structured object\n"
            "Then the schema must reject it"
        ),
        "readiness": "approved",
        "priority": "high",
        "assigned_agent": "python-coder",
        "it_requirements": [
            "This is a plain list, not the required structured object",
            "Second requirement string",
        ],
    }


def _write_ac_yaml(tmp_path: Path, filename: str, data: dict[str, Any]) -> Path:
    """Serialize `data` via the REAL yaml.dump producer and write it to disk.

    Per the Fixture Authenticity Rule (test-writer §2h.2), a serialized-format
    fixture must be produced by the real serializer, never a hand-indented
    string literal — a hand-typed YAML fixture reproduces the author's mental
    model of indentation, which is the exact bias class of bug this AC exists
    to catch (see EPIC-PhantomDoneFilesTouched precedent).

    Args:
        tmp_path: Pytest tmp_path fixture directory to write into.
        filename: Name of the YAML file to create under tmp_path.
        data: The AC content to serialize.

    Returns:
        The absolute Path of the written YAML file.
    """
    path = tmp_path / filename
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
    return path


def _run_standalone_validator(path: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the real standalone validator as a subprocess against `path`.

    Args:
        path: Absolute path to the AC YAML file to validate.

    Returns:
        The completed subprocess result (returncode, stdout, stderr).
    """
    return subprocess.run(
        [sys.executable, str(STANDALONE_VALIDATOR), str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_standalone_validator_rejects_package_surface_ac_with_list_it_requirements(
    tmp_path: Path,
) -> None:
    # covers: ACS-200e
    """AC-ACS-200e: standalone validator must reject a schema-violating AC.

    Given an AC YAML file that violates config/ac_store_schema.json (a
    package-surface AC — assigned_agent python-coder in a build-orchestration
    component — whose it_requirements is a plain list instead of the
    required structured object), when the standalone validator is run
    against that file, it must report the schema violation and exit
    non-zero.

    This currently FAILS: validate_ac_schema.py never loads
    config/ac_store_schema.json, so it exits 0 ("OK: ... is valid.") for
    this file — the exact false-green symptom ACS-200e exists to close.
    """
    fixture_path = _write_ac_yaml(
        tmp_path, "ACS-999.yaml", _invalid_package_surface_ac_data()
    )

    result = _run_standalone_validator(fixture_path)

    assert result.returncode != 0, (
        "standalone validator must reject a package-surface AC whose "
        "it_requirements is a plain list rather than the required "
        f"structured object, but it exited 0. stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    combined_output = result.stdout + result.stderr
    assert "it_requirements" in combined_output, (
        "validator output must name the it_requirements violation so an "
        f"author knows what to fix; got stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )


def test_standalone_validator_and_commit_hook_agree(tmp_path: Path) -> None:
    # covers: ACS-200e
    """AC-ACS-200e: standalone validator verdict must agree with the hook's.

    Given the same AC YAML file, when both the standalone validator and the
    commit-time hook's schema validation are run against it, their verdicts
    (reject / accept) must agree — no file may pass the standalone validator
    and then be rejected by the commit hook.

    This currently FAILS: the standalone validator accepts (exit 0) while
    validate_with_jsonschema (the exact helper the commit hook calls) rejects
    it — they disagree, reproducing the false-green-then-hard-reject symptom
    from this session.
    """
    data = _invalid_package_surface_ac_data()
    fixture_path = _write_ac_yaml(tmp_path, "ACS-999.yaml", data)

    standalone_result = _run_standalone_validator(fixture_path)
    standalone_rejects = standalone_result.returncode != 0

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    hook_errors = validate_with_jsonschema(data, schema)
    hook_rejects = bool(hook_errors)

    # Sanity check on the test itself: the commit-hook side must actually
    # reject this fixture, or this test would prove nothing about parity.
    assert hook_rejects, (
        "sanity check failed: validate_with_jsonschema did not reject the "
        f"known-invalid fixture; got no errors for data={data!r}"
    )
    assert standalone_rejects == hook_rejects, (
        "standalone validator and commit-time hook must agree on this AC "
        f"file: standalone rejects={standalone_rejects} "
        f"(exit={standalone_result.returncode}, stdout="
        f"{standalone_result.stdout!r}), hook rejects={hook_rejects} "
        f"(errors={hook_errors})"
    )


def test_standalone_validator_still_accepts_a_schema_valid_ac(tmp_path: Path) -> None:
    # covers: ACS-200e
    """AC-ACS-200e: anti-over-broadening guard — a valid AC must still pass.

    Given a schema-valid AC file, when the standalone validator is run
    against it, it must still exit 0. Modelled on the real
    docs/acceptance-criteria/ac-store/ACS-200-automated-verification/
    ACS-200d.yaml, whose component is "ac-store" — outside the
    build_pipeline/build-orchestration package-surface conditional — so
    fixing ACS-200e must not start rejecting ordinary, already-valid ACs.

    This PASSES both before and after the fix: today the standalone
    validator accepts it for the (wrong) reason that it never checks the
    schema at all; after the fix it must accept it for the correct reason
    that the file genuinely satisfies config/ac_store_schema.json.
    """
    assert _REAL_SCHEMA_VALID_AC.is_file(), (
        f"reference fixture AC not found on disk: {_REAL_SCHEMA_VALID_AC}"
    )
    # Copy the real on-disk artifact verbatim (byte-for-byte) rather than
    # pointing the test directly at a live docs/ file that other flows may
    # edit — the AC content itself, not just its current file location, is
    # the fixture (Fixture Authenticity Rule, test-writer §2h.2).
    verbatim_content = _REAL_SCHEMA_VALID_AC.read_text(encoding="utf-8")
    copied_path = tmp_path / _REAL_SCHEMA_VALID_AC.name
    copied_path.write_text(verbatim_content, encoding="utf-8")

    result = _run_standalone_validator(copied_path)

    assert result.returncode == 0, (
        f"a schema-valid AC (verbatim copy of {_REAL_SCHEMA_VALID_AC.name}) "
        f"must still pass the standalone validator; stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )

    # Independently confirm the commit-hook's jsonschema verdict agrees this
    # file is valid, so this guard cannot itself be defeated by a fixture
    # that happens to be invalid under both validators for unrelated reasons.
    data = yaml.safe_load(verbatim_content)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    hook_errors = validate_with_jsonschema(data, schema)
    assert hook_errors == [], (
        f"reference fixture must be schema-valid under the hook's own "
        f"jsonschema check too, or this anti-over-broadening guard proves "
        f"nothing; got errors={hook_errors}"
    )
