"""TQ-200d-4-vi: the reference entry, the README bullet and the quoted template sentence."""

from __future__ import annotations

import re

from unit_tests.evals.tq200d4vi import _helpers as h


def _entry(text: str, kind: str) -> str:
    m = re.search(rf"^### `{kind}`\n(.*?)(?=^### |\Z)", text, re.DOTALL | re.MULTILINE)
    assert m, f"no '### `{kind}`' entry in {h.DOC.name}"
    return m.group(1)


def test_new_kind_entry_quotes_a_test_writer_sentence():
    # covers: TQ-200d-4-vi
    # angle: real_artifact
    """AC-5: the entry quotes a sentence test-writer.md holds; report_says_not_run no longer lists the writer row; README links it."""
    text = h.DOC.read_text(encoding="utf-8")
    entry = _entry(text, h.NEW_KIND)
    tail = entry.split("**Template sentence:**")[1]
    quoted = re.search(r">\s*(.+)", tail)
    assert quoted, "entry has no quoted Template sentence"
    template = h.TEMPLATE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert quoted.group(1).strip().rstrip("*") in template, quoted.group(1)
    assert "templates/agents/test-writer.md" in tail
    assert "test-runner.md" not in tail
    assert "The database tests were not run." not in tail
    used_by = re.search(r"\*\*Used by:\*\*(.+)", _entry(text, h.OLD_KIND)).group(1)
    assert "test-writer" not in used_by and "test-runner" in used_by, used_by
    assert "#report_says_stopped_before_database" in h.README.read_text(encoding="utf-8")
