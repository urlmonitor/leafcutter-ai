"""A layer whose content ends in a blank line is not an empty layer.

Regression for a live fast-lane halt on 2026-08-31. The lane assembled a
complete 16,442-byte bundle -- breakpoint marker present exactly once, every
layer populated -- and refused it as ``obtained_but_incomplete``.

The cause was a heuristic in classifyContextBundle() that inferred layer
emptiness from formatting: assemble_context_bundle() joins layers with
``"\\n\\n"``, so an empty layer collapses two joins into four consecutive
newlines, and the gate tested ``/\\n{4,}/``. Its own comment claimed such a run
"never occurs when every layer is non-empty". That is false. The pinned
architecture layer is a real markdown document ending in an HTML comment and a
trailing blank line; joined to the next layer it produced FIVE consecutive
newlines at offset 10642, and the run halted.

BO-2400c-1-vi is what made this certain rather than merely possible: it pinned
the architecture layer to docs/architecture/diagrams/c1-001-command-map.md, so
every run now carries a real markdown document in that slot.

The fix moves the question to where it can be answered. Emptiness is an
assembly-time fact -- once the layers are concatenated the boundaries are gone
and any downstream check is guessing -- so injection_builders.py refuses an
empty required layer at assembly time, naming it, and the transport gate keeps
only checks that are unambiguous on real content.

These tests use REAL layer content with real trailing blank lines. The original
tests passed because their fixtures were short synthetic strings
("STABLE_ARCH_FOR_...") that no markdown document resembles -- the same
synthetic-fixture bias that this AC family has been bitten by repeatedly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "injection_builders.py"
_MARKER = "<!-- CACHE_BREAKPOINT -->"

# The real document the lane pins as its architecture layer (BO-2400c-1-vi).
_PINNED_ARCHITECTURE = (
    _REPO_ROOT / "docs" / "architecture" / "diagrams" / "c1-001-command-map.md"
)


def _run_assemble(architecture: Path, high_level: Path, prior_tests: Path):
    """Invoke the assemble-bundle subcommand as a real subprocess.

    Args:
        architecture: Path to the architecture layer file.
        high_level: Path to the high-level layer file.
        prior_tests: Path to the prior-tests layer file.

    Returns:
        The CompletedProcess, with stdout and stderr captured as text.
    """
    return subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "assemble-bundle",
            "--architecture", str(architecture),
            "--high-level", str(high_level),
            "--prior-tests", str(prior_tests),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_layer_ending_in_blank_lines_still_assembles(tmp_path):
    # covers: BO-2400c-1-iii
    """Trailing blank lines in layer content do not make the bundle incomplete.

    This is the exact shape that halted the live run: a layer whose content
    ends with a blank line, so the join yields 4+ consecutive newlines.
    """
    architecture = tmp_path / "architecture.md"
    architecture.write_text(
        "# Architecture\n\nSome real prose.\n\n<!--\n  a trailing comment\n-->\n\n\n",
        encoding="utf-8",
    )
    high_level = tmp_path / "high_level.md"
    high_level.write_text("# High-Level ACs\n\nParent criteria text.\n", encoding="utf-8")
    prior_tests = tmp_path / "prior_tests.md"
    prior_tests.write_text("# Prior Tests\n\nExisting coverage notes.\n", encoding="utf-8")

    result = _run_assemble(architecture, high_level, prior_tests)

    assert result.returncode == 0, (
        f"A bundle whose layers merely end in blank lines must assemble. "
        f"stderr: {result.stderr}"
    )
    assert result.stdout.count(_MARKER) == 1
    # The condition the old heuristic keyed on is present in valid output.
    assert "\n\n\n\n" in result.stdout, (
        "This fixture is meant to REPRODUCE the 4+ newline run. If it no "
        "longer does, the test has stopped guarding the regression."
    )


def test_the_real_pinned_architecture_document_assembles(tmp_path):
    # covers: BO-2400c-1-iii
    """The actual document the lane pins produces a usable bundle.

    Guards against a fixture drifting away from the artifact it stands in for:
    this reads the real on-disk file the bundle prompt names.
    """
    assert _PINNED_ARCHITECTURE.exists(), (
        f"The architecture path pinned by BO-2400c-1-vi is missing: "
        f"{_PINNED_ARCHITECTURE}"
    )
    high_level = tmp_path / "high_level.md"
    high_level.write_text("# High-Level ACs\n\nParent criteria.\n", encoding="utf-8")
    prior_tests = tmp_path / "prior_tests.md"
    prior_tests.write_text("# Prior Tests\n\nCoverage notes.\n", encoding="utf-8")

    result = _run_assemble(_PINNED_ARCHITECTURE, high_level, prior_tests)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.count(_MARKER) == 1


def test_an_empty_required_layer_is_refused_at_assembly_naming_it(tmp_path):
    # covers: BO-2400c-1-iii
    """An genuinely empty required layer exits 1 and names the layer.

    This is the case the removed heuristic existed to catch. It is now caught
    upstream, where the layer boundaries still exist, so the diagnosis names
    the layer instead of inferring it from newline runs.
    """
    architecture = tmp_path / "architecture.md"
    architecture.write_text("# Architecture\n\nReal content.\n", encoding="utf-8")
    high_level = tmp_path / "high_level.md"
    high_level.write_text("   \n\n  \n", encoding="utf-8")  # whitespace only
    prior_tests = tmp_path / "prior_tests.md"
    prior_tests.write_text("# Prior Tests\n\nCoverage notes.\n", encoding="utf-8")

    result = _run_assemble(architecture, high_level, prior_tests)

    assert result.returncode == 1, (
        f"An empty required layer must be refused. stdout: {result.stdout[:200]!r}"
    )
    assert "high_level" in result.stderr, (
        f"The refusal must name the empty layer. stderr: {result.stderr!r}"
    )
    assert "empty" in result.stderr.lower()
    assert result.stdout == "", "No partial bundle may be printed on refusal."


def test_a_zero_byte_required_layer_is_refused(tmp_path):
    # covers: BO-2400c-1-iii
    """A completely empty file is refused the same way as a whitespace-only one."""
    architecture = tmp_path / "architecture.md"
    architecture.write_text("", encoding="utf-8")
    high_level = tmp_path / "high_level.md"
    high_level.write_text("# High-Level\n\nText.\n", encoding="utf-8")
    prior_tests = tmp_path / "prior_tests.md"
    prior_tests.write_text("# Prior Tests\n\nText.\n", encoding="utf-8")

    result = _run_assemble(architecture, high_level, prior_tests)

    assert result.returncode == 1
    assert "architecture" in result.stderr
    assert result.stdout == ""
