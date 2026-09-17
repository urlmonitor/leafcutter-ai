"""
MODULE: test_adr_index_frontmatter_preserved
GOAL: Reproduce and pin the INF-1300c-5 regression: regenerating
    docs/architecture/adrs/README.md via `adr_refs.py --index --write` must
    preserve the existing README's frontmatter fields (status, created,
    components, and any others), only bumping last_updated to today, and
    must emit a complete frontmatter block (including status: active and
    components: [documentation_system]) when no README exists yet.

Nature: TDD test stub -- MUST be RED against the current unmodified
    scripts/adr_refs.py, whose _build_index() (lines 373-377) always emits a
    fixed frontmatter block containing only title/description/type,
    discarding status/created/last_updated/components even when the README
    on disk already carries them.

Root cause (from ticket): _build_index() renders a hard-coded frontmatter
    string instead of reading and carrying over the existing README's
    frontmatter. Fix must (a) preserve existing keys/values when the README
    already exists, updating only last_updated to today, and (b) emit a
    complete frontmatter block (status: active, created/last_updated: today,
    components: [documentation_system]) when the README is absent.

covers: INF-1300c-5
"""

from __future__ import annotations

import datetime
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ADR_REFS_SCRIPT = _REPO_ROOT / "scripts" / "adr_refs.py"

_ADR_ONE = (
    '---\ntitle: "First Decision"\nstatus: accepted\ncreated: "2026-01-01"\n'
    "---\n\n# ADR-001: First Decision\n\nSome body text.\n"
)
_ADR_TWO = (
    '---\ntitle: "Second Decision"\nstatus: accepted\ncreated: "2026-02-02"\n'
    "---\n\n# ADR-002: Second Decision\n\nSome body text.\n"
)

_EXISTING_README = (
    "---\n"
    'title: "Architecture Decision Records"\n'
    'description: "Index of all Architecture Decision Records (ADRs) for the '
    'leafcutter-ai package, listing each decision\'s number, status, title, '
    'and date."\n'
    'type: "reference"\n'
    "status: active\n"
    "created: '2026-08-13'\n"
    "last_updated: '2026-08-13'\n"
    "components:\n"
    "- documentation_system\n"
    "custom_field: must_survive_regeneration\n"
    "---\n\n"
    "# Architecture Decision Records\n\n"
    "Stale body that the regeneration is expected to replace.\n"
)


def _make_adr_repo(tmp_path: Path) -> Path:
    """Build a minimal repo layout with two ADRs on disk."""
    adr_dir = tmp_path / "docs" / "architecture" / "adrs"
    adr_dir.mkdir(parents=True)
    (adr_dir / "ADR-001-first-decision.md").write_text(_ADR_ONE, encoding="utf-8")
    (adr_dir / "ADR-002-second-decision.md").write_text(_ADR_TWO, encoding="utf-8")
    return adr_dir


def _run_index_write(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_ADR_REFS_SCRIPT), "--root", str(root),
         "--index", "--write"],
        capture_output=True, text=True, timeout=30,
    )


def _read_frontmatter(readme_path: Path) -> dict:
    text = readme_path.read_text(encoding="utf-8")
    assert text.startswith("---"), (
        f"README has no leading frontmatter block:\n{text[:200]}"
    )
    end = text.find("\n---", 3)
    assert end != -1, f"README frontmatter block never closes:\n{text[:200]}"
    return yaml.safe_load(text[3:end])


class TestIndexWritePreservesExistingFrontmatter:
    def test_index_write_preserves_existing_frontmatter_fields(self, tmp_path):
        # covers: INF-1300c-5
        # angle: real_artifact
        """Regenerating over an existing README must keep status, created,
        components and any custom key untouched, bumping only last_updated.
        """
        adr_dir = _make_adr_repo(tmp_path)
        readme_path = adr_dir / "README.md"
        readme_path.write_text(_EXISTING_README, encoding="utf-8")

        result = _run_index_write(tmp_path)
        assert result.returncode == 0, (
            f"adr_refs.py --index --write failed:\nstdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )

        fm = _read_frontmatter(readme_path)

        today = datetime.date.today().isoformat()
        assert fm.get("status") == "active", (
            "BUG (INF-1300c-5): existing 'status' field was dropped during "
            f"regeneration; got frontmatter: {fm}"
        )
        assert fm.get("created") == "2026-08-13", (
            "BUG (INF-1300c-5): existing 'created' field was dropped/overwritten "
            f"during regeneration; got frontmatter: {fm}"
        )
        assert fm.get("components") == ["documentation_system"], (
            "BUG (INF-1300c-5): existing 'components' field was dropped during "
            f"regeneration; got frontmatter: {fm}"
        )
        assert fm.get("custom_field") == "must_survive_regeneration", (
            "BUG (INF-1300c-5): an unrecognized existing frontmatter key was "
            f"dropped during regeneration instead of carried over; got: {fm}"
        )
        assert fm.get("last_updated") == today, (
            "last_updated must be bumped to today's date on regeneration; "
            f"got frontmatter: {fm}"
        )

    def test_index_write_emits_complete_frontmatter_when_readme_absent(
        self, tmp_path
    ):
        # covers: INF-1300c-5
        # angle: boundary
        """Negative control: with no pre-existing README, the generator must
        still emit a COMPLETE frontmatter block (status/created/last_updated/
        components), not merely the truncated title/description/type block
        the bug produces today in every case, existing-README or not.
        """
        _make_adr_repo(tmp_path)
        readme_path = tmp_path / "docs" / "architecture" / "adrs" / "README.md"
        assert not readme_path.exists()

        result = _run_index_write(tmp_path)
        assert result.returncode == 0, (
            f"adr_refs.py --index --write failed:\nstdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )

        fm = _read_frontmatter(readme_path)
        today = datetime.date.today().isoformat()

        assert fm.get("status") == "active", (
            "BUG (INF-1300c-5): freshly generated README frontmatter is missing "
            f"'status: active'; got frontmatter: {fm}"
        )
        assert fm.get("created") == today, (
            "BUG (INF-1300c-5): freshly generated README frontmatter is missing "
            f"'created' (today's date); got frontmatter: {fm}"
        )
        assert fm.get("last_updated") == today, (
            "BUG (INF-1300c-5): freshly generated README frontmatter is missing "
            f"'last_updated' (today's date); got frontmatter: {fm}"
        )
        assert fm.get("components") == ["documentation_system"], (
            "BUG (INF-1300c-5): freshly generated README frontmatter is missing "
            f"'components: [documentation_system]'; got frontmatter: {fm}"
        )
        # title/description/type must still be present -- the bug's own output
        # is never wrong about these, so this is the sanity half of the control.
        assert fm.get("title") == "Architecture Decision Records"
        assert fm.get("type") == "reference"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
