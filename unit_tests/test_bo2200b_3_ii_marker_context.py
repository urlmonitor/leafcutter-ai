"""Context discrimination for placeholder-marker detection (BO-2200b-3-ii).

Quoting a marker is not carrying one. These tests pin three suppressions --
fenced code blocks, mid-heading markers, and markdown emphasis mistaken for a
list bullet -- and, in the same tests, the retentions each suppression must not
swallow.

The fourth test is the one that matters most and looks the least necessary: it
guards the fix direction NOT taken. The obvious cure for the mid-heading false
positive is to require `TODO:` to sit at a marker position, and that would make
every other test here pass while silently dropping the canonical true positive
the gate exists for. See KI-CG-033.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from build_placeholder_detection import scan_for_placeholders  # noqa: E402


def _scan_one(tmp_path: Path, name: str, body: str) -> list[dict]:
    """Write `body` to `name` under tmp_path and return the scan hits."""
    target = tmp_path / name
    target.write_text(body, encoding="utf-8")
    return scan_for_placeholders(tmp_path, [target])


def test_marker_inside_fenced_code_block_is_not_reported(tmp_path: Path) -> None:
    # covers: BO-2200b-3-ii
    """A fenced block is the block form of the inline-code exemption.

    The same marker appears twice: once quoted inside a fence, once as real
    prose outside it. Only the second may be reported -- asserting the absence
    alone would pass on a scanner that had simply stopped detecting TODO.
    """
    body = (
        "# Register\n"
        "\n"
        "```\n"
        "templates/skills/roadmap-query/SKILL.md:54,58  todo: 1 / todo: 2   (a count field)\n"
        "```\n"
        "\n"
        "Some prose. TODO: fill this in properly.\n"
    )
    hits = _scan_one(tmp_path, "register.md", body)

    reported_lines = [h["line"] for h in hits]
    assert 4 not in reported_lines, (
        f"the fenced line must not be reported; got {hits!r}"
    )
    assert 7 in reported_lines, (
        "the unfenced TODO: must still be reported -- otherwise this test would "
        f"pass on a scanner that detects nothing at all; got {hits!r}"
    )


def test_marker_after_heading_text_is_not_reported_but_opening_one_is(
    tmp_path: Path,
) -> None:
    # covers: BO-2200b-3-ii
    """A marker mid-heading is part of a title; one that opens the heading is a stub.

    Both halves live in one test on purpose. A blanket "headings are exempt"
    rule satisfies the first assertion and fails the second, and only the pair
    distinguishes the two.
    """
    body = (
        "### KI-BO-021 — TODO: `BO-2400e-4` is closed on two of its four tests\n"
        "\n"
        "## TODO: fill this in\n"
        "\n"
        "  # - TODO: add your own design/brand/style-guide doc path(s) here, if any.\n"
    )
    hits = _scan_one(tmp_path, "headings.md", body)

    reported_lines = [h["line"] for h in hits]
    assert 1 not in reported_lines, (
        f"a marker after other heading text is a title, not a stub; got {hits!r}"
    )
    assert 3 in reported_lines, (
        "a marker opening the heading text IS a stub and must still be reported "
        f"-- a blanket heading exclusion is the wrong fix; got {hits!r}"
    )
    assert 5 in reported_lines, (
        "a single `#` is a COMMENT in YAML/shell/Python, not a heading -- treating "
        "it as one dropped a real marker in ui-context.template.md:39, which is why "
        f"the heading rule starts at `##`; got {hits!r}"
    )


def test_emphasis_is_not_a_list_bullet_for_placeholder(tmp_path: Path) -> None:
    # covers: BO-2200b-3-ii
    """`*Placeholder*` is emphasis; `- PLACEHOLDER:` is a list item.

    The original rule matched a bullet CHARACTER rather than a list bullet, so
    italic was flagged and bold was not -- an inconsistency that is itself the
    tell that it was matching punctuation instead of structure.
    """
    body = (
        "*Placeholder* text is shown when the field is empty.\n"
        "**Placeholder** text is shown when the field is empty.\n"
        "- PLACEHOLDER: fill in the real value\n"
    )
    hits = _scan_one(tmp_path, "emphasis.md", body)

    reported_lines = [h["line"] for h in hits]
    assert 1 not in reported_lines, f"italic emphasis is not a list bullet; got {hits!r}"
    assert 2 not in reported_lines, f"bold emphasis is not a list bullet; got {hits!r}"
    assert 3 in reported_lines, (
        f"a real bulleted PLACEHOLDER must still be reported; got {hits!r}"
    )


def test_canonical_mid_line_todo_marker_still_reported(tmp_path: Path) -> None:
    # covers: BO-2200b-3-ii
    """The flagship true positive: a TODO: mid-line after ordinary prose.

    This is the regression guard on the fix NOT taken. Requiring `TODO:` to sit
    at line start, after a bullet, or after a comment introducer would make the
    heading test above pass and would drop this -- the exact sentinel a freshly
    installed CLAUDE.md carries, and the reason the detector exists.
    """
    body = (
        "Current phase: `phase_1`\n"
        "Current outcome: TODO: Replace with the single must-achieve outcome for Phase 1.\n"
    )
    hits = _scan_one(tmp_path, "CLAUDE.md", body)

    assert [h["line"] for h in hits] == [2], (
        "the canonical roadmap sentinel must be reported even though the marker "
        f"is mid-line after prose; got {hits!r}"
    )


@pytest.mark.parametrize(
    "register_name",
    [
        "commit-guardian.md",
        "build-orchestration.md",
        "testing-quality.md",
        "supervisor-system.md",
        "feedback-collector.md",
        "ac-store.md",
        "ac-driven-dev.md",
    ],
)
def test_real_known_issues_registers_scan_clean(register_name: str) -> None:
    # covers: BO-2200b-3-ii
    """The real registers must scan clean -- they are asserted, not fixtured.

    These files describe the markers, so they are the natural home of
    quoted-marker false positives. A hand-written fixture would reproduce the
    author's own assumption about what a false positive looks like, which is
    the bias that produced the mis-measurement in the first place.
    """
    target = _REPO_ROOT / "docs" / "known-issues" / register_name
    assert target.is_file(), f"expected a real register at {target}"

    hits = scan_for_placeholders(_REPO_ROOT, [target])
    assert hits == [], (
        f"{register_name} must scan clean; got {len(hits)} false positive(s): {hits[:5]!r}"
    )
