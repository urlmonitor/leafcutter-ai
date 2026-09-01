"""
MODULE: test_ki_bp_019_yaml_hard_import
GOAL: Regression test for KI-BP-019 — a missing ``pyyaml`` dependency must
    fail loudly at import time, not be silently swallowed into a degraded
    no-yaml path that returns empty frontmatter for every template.
BUSINESS CONTEXT: ``scripts/template_compiler.py`` used to wrap
    ``import yaml`` in a bare ``except ImportError``, setting a
    module-level ``_YAML_AVAILABLE = False`` flag with no output on any
    stream. ``parse_frontmatter`` then returned ``{}`` for *every*
    template it was given, so every compiled agent silently lost
    ``name``/``description``/``model``/``tools`` (and the sign-off /
    verification blocks that key off those fields never appeared),
    while the build still printed ``Total files written: N`` and exited
    0. This test proves that with ``yaml`` genuinely unavailable,
    importing ``template_compiler`` now fails loudly (non-zero exit,
    error naming the missing dependency) instead of degrading silently,
    and that with ``yaml`` present, frontmatter parsing still produces a
    fully populated dict — the observable behaviour the original defect
    corrupted.
ARCHITECTURE: "yaml is missing" is simulated in a fresh, real subprocess
    by installing a ``builtins.__import__`` shim that raises
    ``ModuleNotFoundError`` for the ``yaml`` module before
    ``template_compiler`` is imported. A subprocess is required — rather
    than ``sys.modules["yaml"] = None`` in this test process — because
    this process already has ``yaml`` imported transitively via other
    modules, so mutating its module cache would not reproduce a genuine
    "environment lacks pyyaml" condition and risks corrupting later
    tests in the same run. A companion control test runs the identical
    harness with yaml left unblocked to prove the harness itself can
    observe a populated frontmatter dict, so a red result from the
    blocked case is known to come from the block and not from a broken
    harness.
NOTE ON TRACEABILITY: this module has no ``# covers: XX-NNN`` tag.
    ``check_test_ac_tags.py``'s ``COVERS_REGEX`` (``[A-Z]{2,6}-[0-9]{3}``)
    matches Acceptance Criterion IDs, not Known Issue IDs — ``KI-BP-019``
    does not match that pattern (and, separately, a module-docstring tag
    is outside the three locations the hook actually reads: the line
    above ``def``, the function docstring, or the first body line). This
    fix was authored directly against a Known Issue, not against an
    Acceptance Criterion, so there is no true ``covers:`` claim to make
    here; a fabricated tag would satisfy the regex without being honest
    about coverage. If durable AC-level traceability is wanted for this
    behaviour, author an AC via ``/plan-feature`` and add a real
    per-function tag then — do not backfill a fake one now.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

# A template body with real frontmatter, fed to parse_frontmatter() inside
# the subprocess. If yaml import degrades silently (the original defect),
# this would come back as an empty dict instead of the four keys below.
_SAMPLE_TEMPLATE_TEXT = textwrap.dedent(
    """\
    ---
    name: sample-agent
    description: A sample agent used only by this regression test.
    model: sonnet
    tools: Read, Edit
    ---

    Body content unrelated to frontmatter parsing.
    """
)

# Shared subprocess body: parses _SAMPLE_TEMPLATE_TEXT via the real
# parse_frontmatter() and prints whether all four expected keys came back
# populated. {block_yaml} is substituted per-run to toggle the simulated
# missing-dependency condition.
_HARNESS_TEMPLATE = textwrap.dedent(
    """
    import builtins
    import sys

    sys.path.insert(0, {scripts_dir!r})

    {block_yaml}

    import template_compiler

    fm, _body = template_compiler.parse_frontmatter({sample_text!r})
    expected_keys = {{"name", "description", "model", "tools"}}
    if expected_keys.issubset(fm.keys()):
        print("FRONTMATTER_POPULATED")
    else:
        print(f"FRONTMATTER_EMPTY_OR_PARTIAL:{{fm!r}}")
    """
)

_BLOCK_YAML_SNIPPET = textwrap.dedent(
    """
    _real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "yaml" or name.startswith("yaml."):
            # name= mirrors what Python's real import machinery sets on a
            # genuine "module not installed" ModuleNotFoundError -- code
            # under test may branch on exc.name, so the simulation must
            # carry it too or it is not representative of a real missing
            # dependency.
            raise ModuleNotFoundError("No module named 'yaml'", name="yaml")
        return _real_import(name, *args, **kwargs)

    builtins.__import__ = _blocked_import
    """
)


def _run_harness(*, block_yaml: bool) -> subprocess.CompletedProcess[str]:
    """Run the import/parse harness in a fresh subprocess.

    Args:
        block_yaml: When True, installs the import shim that makes ``yaml``
            unavailable before ``template_compiler`` is imported. When
            False, runs with the real environment's ``yaml`` intact.

    Returns:
        The completed subprocess result (returncode, stdout, stderr).
    """
    script = _HARNESS_TEMPLATE.format(
        scripts_dir=str(_SCRIPTS_DIR),
        block_yaml=_BLOCK_YAML_SNIPPET if block_yaml else "",
        sample_text=_SAMPLE_TEMPLATE_TEXT,
    )
    return subprocess.run(  # noqa: S603 - fixed args, no shell, trusted script
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


class TestMissingYamlFailsLoudly:
    """KI-BP-019: a missing pyyaml must fail loudly, never degrade silently."""

    def test_control_harness_reports_populated_frontmatter_when_yaml_present(self) -> None:
        """Sanity check: with yaml available, the harness sees a populated dict.

        This is the control run. It proves the harness itself is capable of
        observing a populated frontmatter dict, so that a red result from
        the blocked-yaml case below is trustworthy evidence of the defect
        rather than an artifact of a broken test harness.
        """
        result = _run_harness(block_yaml=False)

        assert result.returncode == 0, (
            f"control harness failed unexpectedly: stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        assert "FRONTMATTER_POPULATED" in result.stdout, (
            "control harness did not observe populated frontmatter with "
            f"yaml available: stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_import_fails_loudly_when_yaml_is_unavailable(self) -> None:
        """template_compiler must refuse to import when yaml is unavailable.

        Before the fix, this subprocess exited 0 having printed
        ``FRONTMATTER_EMPTY_OR_PARTIAL:{}`` — the ImportError was caught
        silently, ``_YAML_AVAILABLE`` was set to False with no output on
        any stream, and ``parse_frontmatter`` returned ``{}``. The fix
        requires the ImportError to propagate at import time, so the
        subprocess must now exit non-zero and its stderr must name the
        missing dependency, and it must never reach the point of printing
        a frontmatter result at all.
        """
        result = _run_harness(block_yaml=True)

        assert result.returncode != 0, (
            "template_compiler imported successfully with yaml blocked — "
            "this is the KI-BP-019 silent-degradation defect: a missing "
            "pyyaml dependency must fail loudly, not be swallowed into a "
            f"degraded no-yaml path.\nstdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        assert "FRONTMATTER_POPULATED" not in result.stdout, (
            "template_compiler produced a frontmatter result at all with "
            f"yaml blocked, instead of failing at import: stdout={result.stdout!r}"
        )
        assert "yaml" in result.stderr.lower(), (
            "process failed but the error does not name the missing "
            f"'yaml' dependency: stderr={result.stderr!r}"
        )
        assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr, (
            f"expected an import-error traceback naming yaml: stderr={result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# Finding 1 (post-fix review): registry_validator.validate_produces_field()
# used to catch ModuleNotFoundError as a plain ImportError and skip its
# frontmatter check silently, exactly reproducing the KI-BP-019 symptom one
# file over -- a validator whose job is to check template frontmatter would
# report a clean run in exactly the environment where its own dependency
# (via template_compiler) is missing. Fixed by distinguishing "template_compiler
# itself is not on the path" (legitimate skip) from "template_compiler is on
# the path but ITS dependency is missing" (must be a loud validation error).
# ---------------------------------------------------------------------------

_REGISTRY_VALIDATOR_HARNESS_TEMPLATE = textwrap.dedent(
    """
    import builtins
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, {scripts_dir!r})

    {block_yaml}

    import registry_validator

    package_root = Path({package_root!r})
    agents = json.loads((package_root / "config" / "agent_registry.json").read_text())["agents"]
    template_dir = package_root / "templates" / "agents"

    errors = registry_validator.validate_produces_field(agents, template_dir)
    if errors:
        print("PRODUCES_CHECK_REPORTED_ERRORS")
        for e in errors:
            print(f"ERROR_DETAIL:{{e}}")
    else:
        print("PRODUCES_CHECK_CLEAN")
    """
)


def _write_minimal_registry_fixture(root: Path) -> None:
    """Write a minimal agent_registry.json + one compliant agent template.

    The fixture is deliberately "clean" -- one agent, whose registry entry
    AND template frontmatter both declare a valid ``produces`` value -- so
    that a real run of ``validate_produces_field`` against it reports zero
    errors whenever the check actually executes. That makes ``errors == []``
    a meaningful signal of "the check ran and found nothing wrong", not an
    artifact of the fixture being too sparse to check anything.

    Args:
        root: Directory to populate as a fake package root (config/ +
            templates/agents/).
    """
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    templates_dir = root / "templates" / "agents"
    templates_dir.mkdir(parents=True, exist_ok=True)

    registry = {
        "agents": [
            {
                "id": "sample-agent",
                "produces": "production_code",
                "template_path": "templates/agents/sample-agent.md",
            }
        ]
    }
    (config_dir / "agent_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (templates_dir / "sample-agent.md").write_text(
        "---\nname: sample-agent\nproduces: production_code\n---\n\nBody.\n",
        encoding="utf-8",
    )


def _run_registry_validator_harness(
    *, fixture_root: Path, block_yaml: bool
) -> subprocess.CompletedProcess[str]:
    """Run ``validate_produces_field`` against the fixture in a fresh subprocess.

    Args:
        fixture_root: Path to a directory populated by
            ``_write_minimal_registry_fixture``.
        block_yaml: When True, installs the import shim that makes ``yaml``
            unavailable before ``registry_validator`` (and, transitively,
            ``template_compiler``) is imported.

    Returns:
        The completed subprocess result (returncode, stdout, stderr).
    """
    script = _REGISTRY_VALIDATOR_HARNESS_TEMPLATE.format(
        scripts_dir=str(_SCRIPTS_DIR),
        package_root=str(fixture_root),
        block_yaml=_BLOCK_YAML_SNIPPET if block_yaml else "",
    )
    return subprocess.run(  # noqa: S603 - fixed args, no shell, trusted script
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


class TestRegistryValidatorProducesCheckDoesNotReportGreen:
    """Finding 1: validate_produces_field() must not silently skip-and-pass
    its frontmatter check when yaml (a template_compiler dependency) is
    missing -- that relocates the KI-BP-019 defect rather than closing it.
    """

    def test_control_harness_reports_clean_when_yaml_present(self, tmp_path: Path) -> None:
        """Sanity check: against a fixture with no real violations and yaml
        available, the check reports clean.

        This is the control run, proving the harness and fixture are sound
        so that a "not clean" result from the blocked-yaml case below is
        trustworthy evidence of the fix rather than a fixture artifact.
        """
        _write_minimal_registry_fixture(tmp_path)
        result = _run_registry_validator_harness(fixture_root=tmp_path, block_yaml=False)

        assert result.returncode == 0, (
            f"control harness failed unexpectedly: stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        assert "PRODUCES_CHECK_CLEAN" in result.stdout, (
            "control harness did not report a clean produces check against "
            f"a violation-free fixture: stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )

    def test_produces_check_does_not_report_clean_when_yaml_is_unavailable(
        self, tmp_path: Path
    ) -> None:
        """The frontmatter check must not report clean when yaml is missing.

        Before the fix, ``except ImportError`` caught the ``ModuleNotFoundError``
        raised by ``template_compiler``'s own hard ``import yaml`` and returned
        the accumulated errors list unchanged -- against this violation-free
        fixture that meant ``PRODUCES_CHECK_CLEAN``, exactly reproducing
        KI-BP-019's "reports green while checking nothing" symptom one file
        over. The fix requires this branch to append a real validation error
        naming the missing dependency instead.
        """
        _write_minimal_registry_fixture(tmp_path)
        result = _run_registry_validator_harness(fixture_root=tmp_path, block_yaml=True)

        assert result.returncode == 0, (
            f"harness itself crashed rather than reporting a result: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "PRODUCES_CHECK_CLEAN" not in result.stdout, (
            "validate_produces_field() reported a clean run with yaml "
            "unavailable -- this is the KI-BP-019 defect relocated: the "
            "frontmatter check must not silently skip-and-pass when its own "
            f"dependency is missing.\nstdout={result.stdout!r}"
        )
        assert "PRODUCES_CHECK_REPORTED_ERRORS" in result.stdout, (
            f"expected a reported-errors result: stdout={result.stdout!r}"
        )
        assert "yaml" in result.stdout.lower(), (
            "the reported error does not name the missing 'yaml' dependency "
            f"-- it should be distinguishable from a generic skip: "
            f"stdout={result.stdout!r}"
        )
