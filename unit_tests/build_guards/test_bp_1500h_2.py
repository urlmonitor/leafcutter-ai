"""
MODULE: unit_tests/build_guards/test_bp_1500h_2.py
GOAL: Failing tests for AC BP-1500h-2 -- the COMPILED changelog-agent prompt
    reads an empty categories setting as "no project rules configured, apply
    the default categories", an existing rules file as "read that path and
    apply its rules", and an absent key as "read the shipped default path".
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500h-2.yaml

Every test reads the prompt a REAL ``build.py`` produced into a scratch
consumer (``_bp1500h_support.real_build``, cached per scenario), never the
template source. No compiled variant may keep the error-discarding
``2>/dev/null`` read (AC it_requirements).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bp1500h_support import (  # noqa: E402
    CHANGELOG_KEY,
    compiled_changelog_step3,
    real_build,
    settings_for,
    shipped_default,
)

_RULES_REL = "docs/rules/my-categories.md"
_RULES_TEXT = "| Category | Rule |\n|---|---|\n| Docs | docs/ |\n"
_NO_RULES = re.compile(r"no project.{0,60}(rules|categori[sz]ation).{0,80}configured", re.I | re.S)
_DEFAULT_CATS = re.compile(r"default categor", re.I)
_EMPTY_READ = re.compile(r"""\b(cat|head|type)\s+["']?\s*["']?\s*(2>|$|\n|`)""", re.M)


def _step3_empty() -> str:
    return compiled_changelog_step3(real_build(settings_for(CHANGELOG_KEY, "")).target)


def _step3_absent() -> str:
    return compiled_changelog_step3(real_build(settings_for(CHANGELOG_KEY, None)).target)


def _step3_existing() -> str:
    run = real_build(
        settings_for(CHANGELOG_KEY, _RULES_REL), plant={_RULES_REL: _RULES_TEXT}
    )
    return compiled_changelog_step3(run.target)


@pytest.mark.shared_layout_mutator
def test_empty_setting_compiles_default_categories_step_without_read():
    # covers: BP-1500h-2
    # angle: deployed
    """Empty setting: compiled Step 3 says no project categorisation rules are
    configured and to apply the default categories, and has no read of an empty
    path or the project folder (no `cat ""`, no 2>/dev/null). Control: the
    existing-rules-file step is NOT this wording."""
    step = _step3_empty()

    assert _NO_RULES.search(step), f"no 'no rules configured' statement:\n{step}"
    assert _DEFAULT_CATS.search(step), f"no 'default categories' instruction:\n{step}"
    assert not _EMPTY_READ.search(step), f"reads an empty path:\n{step}"
    assert "2>/dev/null" not in step, "error-discarding read still compiled"
    assert not _NO_RULES.search(_step3_existing()), "control: configured != off"


@pytest.mark.shared_layout_mutator
def test_existing_rules_file_compiles_read_and_apply_step():
    # covers: BP-1500h-2
    # angle: discrimination
    """Setting pointing at an existing rules file: compiled Step 3 tells
    changelog-agent to read that exact path and apply its rules; it is not the
    empty-value wording and keeps no error-discarding read."""
    step = _step3_existing()

    assert _RULES_REL in step, f"compiled step does not name the rules path:\n{step}"
    assert re.search(r"\b(read|cat)\b", step, re.I)
    assert re.search(r"apply", step, re.I)
    assert "2>/dev/null" not in step, "error-discarding read still compiled"
    assert not _NO_RULES.search(step), "configured file compiled as 'not configured'"
    assert step != _step3_empty()


@pytest.mark.shared_layout_mutator
def test_absent_setting_compiles_read_of_shipped_default_path():
    # covers: BP-1500h-2
    # angle: boundary
    """Key absent: compiled Step 3 tells changelog-agent to read the shipped
    default path (read from skills_config.default.json here, never typed) and
    apply its rules, and differs from the empty-value step. Catches 'absent is
    compiled as off' and a default hard-coded in the compile code."""
    default_rel = shipped_default(CHANGELOG_KEY)
    assert default_rel
    step = _step3_absent()

    assert default_rel in step, f"compiled step does not read {default_rel}:\n{step}"
    assert re.search(r"apply", step, re.I)
    assert "2>/dev/null" not in step, "error-discarding read still compiled"
    assert not _NO_RULES.search(step), "absent compiled as off"
    assert step != _step3_empty()
