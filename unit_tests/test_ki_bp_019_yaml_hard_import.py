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
# covers: KI-BP-019
"""

from __future__ import annotations

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
            raise ModuleNotFoundError("No module named 'yaml'")
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
