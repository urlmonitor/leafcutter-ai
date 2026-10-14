"""
MODULE: unit_tests/build_guards/test_bp_1500h_1_helper.py
GOAL: Pin the contract of the ONE shared interpretation of a file-location
    setting (``scripts/config_paths.resolve_file_setting``) named by
    BP-1500h-1's it_requirements / delivers_to, and prove it survives the
    real config merge (empty stays empty, absent becomes the default).
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500h-1.yaml
    (and BP-1500h-1-i for the 'broken' outcome).

The module is looked up with ``importlib.util.find_spec`` first, so a missing
helper fails as an AssertionError naming the missing behaviour, not as an
import crash of the test module.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bp1500h_support import (  # noqa: E402
    CHANGELOG_KEY,
    HELPER_FUNCTION,
    HELPER_MODULE,
    SCRIPTS_DIR,
    shipped_default,
)

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _resolver():
    assert importlib.util.find_spec(HELPER_MODULE) is not None, (
        f"scripts/{HELPER_MODULE}.py does not exist: the shared file-location "
        "setting interpretation has not been implemented"
    )
    mod = importlib.import_module(HELPER_MODULE)
    fn = getattr(mod, HELPER_FUNCTION, None)
    assert callable(fn), f"{HELPER_MODULE}.{HELPER_FUNCTION} is missing"
    return fn


def test_helper_distinguishes_off_default_usable_and_broken(tmp_path):
    # covers: BP-1500h-1
    # angle: criterion
    """resolve_file_setting returns off for '' / whitespace, the shipped
    default (source 'default') for an absent key, usable for a real file,
    and broken (missing / is_directory) for a missing path or a folder."""
    resolve = _resolver()
    default_rel = shipped_default(CHANGELOG_KEY)
    (tmp_path / "rules.md").write_text("| a | b |\n", encoding="utf-8")
    (tmp_path / "somefolder").mkdir()

    off = resolve({CHANGELOG_KEY: ""}, CHANGELOG_KEY, tmp_path)
    blank = resolve({CHANGELOG_KEY: "   "}, CHANGELOG_KEY, tmp_path)
    assert off["state"] == "off" and off["path"] is None
    assert blank["state"] == "off"

    used = resolve({CHANGELOG_KEY: "rules.md"}, CHANGELOG_KEY, tmp_path)
    assert used["state"] == "usable" and used["source"] == "configured"
    assert Path(used["path"]) == tmp_path / "rules.md"

    folder = resolve({CHANGELOG_KEY: "somefolder"}, CHANGELOG_KEY, tmp_path)
    assert folder["state"] == "broken" and folder["reason"] == "is_directory"
    missing = resolve({CHANGELOG_KEY: "nope.md"}, CHANGELOG_KEY, tmp_path)
    assert missing["state"] == "broken" and missing["reason"] == "missing"

    # absent key: judged at the shipped default location, never 'off'
    absent_missing = resolve({}, CHANGELOG_KEY, tmp_path)
    assert absent_missing["state"] == "broken" and absent_missing["source"] == "default"
    (tmp_path / default_rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / default_rel).write_text("x\n", encoding="utf-8")
    absent_ok = resolve({}, CHANGELOG_KEY, tmp_path)
    assert absent_ok["state"] == "usable" and absent_ok["source"] == "default"
    assert Path(absent_ok["path"]) == tmp_path / default_rel


def test_empty_survives_real_config_merge_and_absent_becomes_default(tmp_path):
    # covers: BP-1500h-1
    # angle: seam
    """Seam: the REAL config_loader.load_config output feeds the helper. An
    explicit '' must stay '' after the defaults merge (state off); the same
    project with the key absent must arrive holding the shipped default.
    Catches 'the empty value is replaced by the shipped default during merging'."""
    resolve = _resolver()
    from config_loader import load_config  # real producer

    def merged(settings: dict) -> tuple[Path, dict]:
        project = tmp_path / ("p" + str(len(settings)))
        (project / ".claude").mkdir(parents=True)
        with (project / ".claude" / "skills_config.json").open("w", encoding="utf-8") as fh:
            json.dump(settings, fh)
        return project, load_config(None, project)

    proj_empty, cfg_empty = merged({CHANGELOG_KEY: ""})
    assert resolve(cfg_empty, CHANGELOG_KEY, proj_empty)["state"] == "off"

    proj_absent, cfg_absent = merged({})
    (proj_absent / shipped_default(CHANGELOG_KEY)).parent.mkdir(parents=True, exist_ok=True)
    (proj_absent / shipped_default(CHANGELOG_KEY)).write_text("x\n", encoding="utf-8")
    got = resolve(cfg_absent, CHANGELOG_KEY, proj_absent)
    assert got["state"] == "usable" and got["source"] == "default"
