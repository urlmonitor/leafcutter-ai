"""DK-300c-1: explicit builds and honest runtime coverage, with no broad fallback."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.conftest import load_fixture
from tests.kernel.adapters.cli_support import real_cli
from tests.kernel.entity_context.support import build, cards, config_for, recognize, write, write_repo


def _index_path(repo, config):
    return repo / config.entity_context.index_path


def _canonical_bytes(repo):
    return {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob("*")
            if p.is_file() and ".leafcutter" not in p.parts and ".git" not in p.parts}


def test_explicit_index_cli_prepares_consumable_metadata(repo):
    # covers: DK-300c-1
    # angle: reachability
    config = config_for()
    override = write(repo, "eval-config.json", config.model_dump(mode="json"))
    response = real_cli(["entities", "build", "--repository-root", str(repo), "--config", str(override)])
    assert response.code == 0, response.stderr + response.stdout
    assert isinstance(response.document(), dict)
    index = json.loads(_index_path(repo, config).read_text(encoding="utf-8"))
    assert index["schema_version"] == "1.0"
    assert index["repository_root"] == str(repo.resolve())
    result = recognize(repo, "Zephyr", config=config)
    assert "zephyr" in cards(result) and result.coverage.index_status == "current"
    assert result.coverage.index_fingerprint and result.coverage.families


def test_refresh_reflects_additions_changes_and_removals_without_source_writes(repo):
    # covers: DK-300c-1
    # angle: real_artifact
    before = _canonical_bytes(repo)
    build(repo)
    first = recognize(repo, "pkg.alpha.bare Zephyr")
    build(repo)
    unchanged = recognize(repo, "pkg.alpha.bare Zephyr")
    assert [c.model_dump() for c in first.entities] == [c.model_dump() for c in unchanged.entities]
    assert _canonical_bytes(repo) == before
    write(repo, "pkg/added.py", 'def added():\n    """Fresh declaration."""\n    return None\n')
    (repo / "pkg/alpha.py").unlink()
    glossary = repo / "docs/glossary.md"
    glossary.write_text(glossary.read_text(encoding="utf-8").replace("A manifest exporter with immutable versions.", "A changed exporter."), encoding="utf-8")
    intended = _canonical_bytes(repo)
    build(repo)
    current = recognize(repo, "pkg.alpha.bare pkg.added.added Zephyr")
    assert "pkg.alpha.bare" not in cards(current)
    assert cards(current)["pkg.added.added"].meaning == "Fresh declaration."
    assert cards(current)["zephyr"].meaning == "A changed exporter."
    assert current.coverage.index_fingerprint != first.coverage.index_fingerprint
    assert _canonical_bytes(repo) == intended


def test_second_dirty_edit_changes_snapshot_with_same_head(repo):
    # covers: DK-300c-1
    # angle: criterion
    def git(*args):
        completed = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
        return completed.stdout.strip()
    git("init")
    git("add", ".")
    git("-c", "user.name=Entity Test", "-c", "user.email=entity@example.test", "commit", "-m", "fixture")
    head = git("rev-parse", "HEAD")
    path = repo / "docs/glossary.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n### Dirty\n\nFirst dirty meaning.\n", encoding="utf-8")
    build(repo)
    first = recognize(repo, "Dirty")
    path.write_text(path.read_text(encoding="utf-8").replace("First dirty", "Second dirty"), encoding="utf-8")
    stale = recognize(repo, "Dirty")
    assert stale.coverage.index_status == "stale" and not cards(stale)
    build(repo)
    second = recognize(repo, "Dirty")
    assert git("rev-parse", "HEAD") == head
    assert first.coverage.index_fingerprint != second.coverage.index_fingerprint
    assert cards(first)["dirty"].provenance.snapshot != cards(second)["dirty"].provenance.snapshot
    assert cards(second)["dirty"].meaning == "Second dirty meaning."


@pytest.mark.parametrize("fault", load_fixture("entity_context/index_faults"))
def test_unusable_indexes_omit_affected_families_without_fallback(repo, tmp_path, fault):
    # covers: DK-300c-1-i
    # angle: failure
    config = config_for()
    build(repo, config)
    path = _index_path(repo, config)
    if fault == "missing":
        path.unlink()
    elif fault == "malformed":
        path.write_text("{broken", encoding="utf-8")
    elif fault == "schema":
        value = json.loads(path.read_text(encoding="utf-8"))
        value["schema_version"] = "unsupported-version"
        write(repo, config.entity_context.index_path, value)
    elif fault == "foreign":
        foreign = tmp_path / "foreign"
        write_repo(foreign)
        build(foreign, config)
        path.write_bytes(_index_path(foreign, config).read_bytes())
    elif fault == "stale":
        (repo / "docs/glossary.md").write_text("# Changed\n", encoding="utf-8")
    original_read = Path.read_bytes
    original_open = Path.open
    def read_bytes(candidate):
        if fault == "unreadable" and candidate == path:
            raise PermissionError("fixture index unavailable")
        return original_read(candidate)
    def open_path(candidate, *args, **kwargs):
        if fault == "unreadable" and candidate == path:
            raise PermissionError("fixture index unavailable")
        return original_open(candidate, *args, **kwargs)
    with (patch("kernel.context_enrichment.gather_context", side_effect=AssertionError("legacy fallback forbidden")),
          patch("kernel.context_enrichment.search_source", side_effect=AssertionError("body search forbidden")),
          patch("kernel.entity_index.build_entity_index", side_effect=AssertionError("runtime rebuild forbidden")),
          patch.object(Path, "rglob", side_effect=AssertionError("runtime crawl forbidden")),
          patch.object(Path, "read_bytes", read_bytes), patch.object(Path, "open", open_path)):
        result = recognize(repo, "Zephyr pkg.alpha.run", config=config)
    assert result.status in {"partial", "unavailable"}
    assert result.coverage.index_status != "current"
    assert not result.entities and result.limitations
    assert result.budgets.jev_calls == 0


def test_incomplete_index_keeps_only_valid_current_family_cards(repo):
    # covers: DK-300c-1-i
    # angle: criterion
    write(repo, "pkg/alpha.py", "def invalid(:\n")
    build(repo)
    result = recognize(repo, "Zephyr pkg.alpha.run")
    assert "zephyr" in cards(result, "glossary")
    assert "pkg.alpha.run" not in cards(result, "symbol")
    assert result.status == "partial" and result.limitations
    assert result.coverage.families["symbol"] != result.coverage.families["glossary"]
