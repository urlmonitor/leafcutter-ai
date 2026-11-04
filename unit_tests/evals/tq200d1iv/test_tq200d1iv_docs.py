"""
MODULE: unit_tests/evals/tq200d1iv/test_tq200d1iv_docs
GOAL: RED doc-drift tests for TQ-200d-1-iv: the two reference entries describe the unittest reading,
    every python block on them scores as the entry states, the template remedies are unchanged and
    the evals README bullet links both entries.
Target: docs/reference/produced-tests-eval-assertion-kinds-test-writer.md, scripts/evals/README.md
"""

from __future__ import annotations

import re

import pytest

from unit_tests.evals.tq200d1iv import _static as s

REPO = s.h.REPO_ROOT
PAGE = REPO / "docs" / "reference" / "produced-tests-eval-assertion-kinds-test-writer.md"
README = REPO / "scripts" / "evals" / "README.md"
TEMPLATE = REPO / "templates" / "agents" / "test-writer.md"
KINDS = (s.COUNT, s.SEED)
REMEDIES = ("assert an exact count of processed rows plus a non-NULL count", "assert at least one known expected value seeded in the fixture")


def _entry(kind):
    text = PAGE.read_text(encoding="utf-8")
    m = re.search(r"^### `" + kind + r"`\n(.*?)(?=^### |^## |\Z)", text, re.S | re.M)
    assert m, f"entry {kind} missing"
    return m.group(1)


def _blocks(entry, label):
    """Python fenced blocks after the **<label>:** line, up to the next label."""
    m = re.search(r"\*\*" + label + r":\*\*(.*?)(?=\n\*\*[A-Z][\w ]+:\*\*|\Z)", entry, re.S)
    return re.findall(r"```python\n(.*?)```", m.group(1), re.S) if m else []


@pytest.mark.parametrize("kind", KINDS)
def test_entries_name_the_accepted_unittest_calls(kind):
    # covers: TQ-200d-1-iv
    # angle: real_artifact
    passes = re.search(r"\*\*Passes when:\*\*(.*?)\n\n", _entry(kind), re.S).group(1)
    assert "assertEqual" in passes, passes
    if kind == s.COUNT:
        for token in ("assertEquals", "assertTrue", "assertGreater", "assertGreaterEqual", "len(seed)"):
            assert token in passes, f"{token} missing from Passes when"
    else:
        assert "either side" in passes, passes
        assert "assertion" in passes.lower()


@pytest.mark.parametrize("kind", KINDS)
def test_entries_carry_a_unittest_passing_example_that_passes(kind, tmp_path):
    # covers: TQ-200d-1-iv
    # angle: real_artifact
    blocks = _blocks(_entry(kind), "Passing example")
    assert any("self.assert" in b for b in blocks), "no unittest passing example"
    for i, block in enumerate(blocks):
        got = s.score_source(kind, block, tmp_path / str(i))
        assert got["passed"] is True, f"passing example {i} scores as failing: {got['detail']}"


@pytest.mark.parametrize("kind", KINDS)
def test_every_failing_python_block_fails(kind, tmp_path):
    # covers: TQ-200d-1-iv
    # angle: real_artifact
    entry = _entry(kind)
    blocks = _blocks(entry, "Failing example")
    for i, block in enumerate(blocks):
        got = s.score_source(kind, block, tmp_path / str(i))
        assert got["passed"] is False, f"failing example {i} passes: {block}"
    if kind == s.SEED:
        assert "assertIsNotNone" in entry
    else:
        assert "assertGreaterEqual(non_null, 0)" in entry
        assert "same expression" in entry or "itself" in entry


def test_count_and_seed_entries_describe_unittest_reading(tmp_path):
    # covers: TQ-200d-1-iv
    # angle: real_artifact
    for kind in KINDS:
        passes = re.search(r"\*\*Passes when:\*\*(.*?)\n\n", _entry(kind), re.S).group(1)
        assert "unittest" in passes.lower(), f"{kind}: Passes when does not mention unittest"
        for label, expected in (("Passing example", True), ("Failing example", False)):
            for i, block in enumerate(_blocks(_entry(kind), label)):  # every example scores as the page says
                got = s.score_source(kind, block, tmp_path / f"{kind}-{label[0]}{i}")
                assert got["passed"] is expected, f"{kind} {label.lower()} {i} scores {got['passed']}: {block}"


def test_template_remedies_are_unchanged():
    # covers: TQ-200d-1-iv
    # angle: real_artifact
    text = re.sub(r"\s+", " ", TEMPLATE.read_text(encoding="utf-8"))
    for remedy in REMEDIES:
        assert remedy in text


def test_readme_bullet_links_both_entries():
    # covers: TQ-200d-1-iv
    # angle: real_artifact
    text = README.read_text(encoding="utf-8")
    base = "docs/reference/produced-tests-eval-assertion-kinds-test-writer.md"
    bullets = [b for b in text.split("\n- ") if f"{base}#counts_rows_and_non_null" in b and f"{base}#asserts_known_seeded_value" in b]
    assert len(bullets) == 1, "no single README bullet links both entries"
    assert "unittest" in bullets[0]
    assert "len(seed)" in bullets[0]
