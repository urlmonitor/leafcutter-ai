"""
MODULE: test_generate_agent_cards_bp018
GOAL: RED-phase regression tests for BP-018 — rebuilding agent cards must
      preserve their provenance dates (`created`, `last_updated`) and must
      not rewrite a card whose substantive content has not changed, even on
      a later calendar day than the one it was last built on.
TICKET: (none — direct bug-fix dispatch, see docs/acceptance-criteria/build_pipeline/BP-018.yaml)
COVERS: BP-018

Bug summary (see BP-018.yaml for full spec):
  generate_card() in scripts/generate_agent_cards.py hardcodes
  `created: {date.today()}` into every card it renders and never emits
  `last_updated` at all. Because the generated string therefore differs
  from what's on disk on any day after the card was last built, the
  compare-before-write guard in build_agent_cards() (lines ~1027-1034)
  never fires, so every card is rewritten unconditionally — destroying the
  `created` provenance and dropping `last_updated` (which is maintained by
  the separate transform-doc-frontmatter commit hook, not by this
  generator).

These tests drive the REAL `generate_card` / `build_agent_cards` functions
against real tmp_path directories and real files, and read the resulting
frontmatter back off disk / off the return value. The system clock is
controlled by patching the `date` symbol as imported into
`generate_agent_cards` (`from datetime import date`) — never by waiting on
a real calendar day.

Run with AC_ENFORCE_STRICT=1 (BP-018 is work_status: todo, so without the
strict env var the pytest_ac_enforcement plugin would downgrade genuine
failures on this file to xfail):

    AC_ENFORCE_STRICT=1 python -m pytest unit_tests/test_generate_agent_cards_bp018.py -v
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_HOOK_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_HOOK_DIR))

import generate_agent_cards  # noqa: E402  (path must be inserted first)
from generate_agent_cards import build_agent_cards, generate_card  # noqa: E402
from transform_doc_frontmatter import transform_content  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixture inputs
# ---------------------------------------------------------------------------

TEMPLATE_FM = {
    "name": "test-agent",
    "description": "A test agent for BP-018 regression coverage.",
    "model": "sonnet",
    "tools": "Bash, Read",
    "portable": True,
    "signoff": True,
    "skills_used": ["signoff"],
}

REGISTRY_ENTRY = {
    "id": "test-agent",
    "name": "Test Agent",
    "tier": "phase",
    "priority": 6,
    "spawned_by": ["ticket-supervisor"],
    "spawn_allowlist": [],
    "skills_used": ["signoff"],
}


def _write_minimal_project(target_root: Path, template_fm: dict) -> None:
    """Write a minimal templates/agents/*.md + config/agent_registry.json pair."""
    templates_dir = target_root / "templates" / "agents"
    templates_dir.mkdir(parents=True, exist_ok=True)
    fm_yaml = yaml.dump(template_fm, default_flow_style=False, sort_keys=False)
    (templates_dir / "test-agent.md").write_text(
        f"---\n{fm_yaml}---\n\nBody text.\n",
        encoding="utf-8",
    )
    config_dir = target_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "agent_registry.json").write_text(
        json.dumps([REGISTRY_ENTRY]),
        encoding="utf-8",
    )


def _extract_frontmatter(text: str) -> dict:
    """Parse the YAML frontmatter block out of a generated/on-disk card string."""
    assert text.startswith("---"), "card content must start with YAML frontmatter"
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    assert end is not None, "card content must have a closing frontmatter delimiter"
    fm_body = "\n".join(lines[1:end])
    parsed = yaml.safe_load(fm_body)
    assert isinstance(parsed, dict)
    return parsed


# A realistic pre-existing card, in the exact shape the
# transform-doc-frontmatter commit hook normalizes cards to on disk.
#
# BUG HISTORY: an earlier version of this fixture was hand-written literal
# text. It happened to get `created`/`last_updated` right (the two fields
# BP-018's AC-2/AC-3 assert on), but `title`/`description`/`card_version`
# were written in the GENERATOR's old hand-built style (double-quoted,
# unfolded), not the shape `_yaml.dump(fm_dict, default_flow_style=False,
# allow_unicode=True, sort_keys=False)` actually produces (single-quoted,
# width-80-folded). That mismatch was invisible to every assertion in this
# file, but a real-artifact check against docs/agents/cards/ found the
# generator still rewrote all 60 real cards on every build — a pure
# formatting mismatch this synthetic fixture had hidden. Building the
# fixture with the hook's OWN yaml.dump() call (not hand-written text)
# closes that gap: it cannot drift from what the hook actually produces.
_EXISTING_CARD_FRONTMATTER = {
    "agent_id": "test-agent",
    "title": "Agent Card: test-agent",
    "description": "A test agent for BP-018 regression coverage.",
    "type": "card",
    "status": "active",
    "created": date(2026, 8, 1),
    "card_version": "generated",
    "last_updated": "2026-08-05",
}

_EXISTING_CARD_BODY = (
    "# test-agent\n"
    "\n"
    "**A test agent for BP-018 regression coverage.**\n"
    "\n"
    "| Field | Value |\n"
    "|-------|-------|\n"
    "| Model | sonnet |\n"
    "| Tier | phase |\n"
    "| Priority | 6 |\n"
    "| Portable | Yes |\n"
    "| Sign-off capable | Yes |\n"
)


def _build_card_text(fm_dict: dict, body: str) -> str:
    """Build card file text via the SAME yaml.dump() call the
    transform-doc-frontmatter commit hook uses in `_rebuild_content()`
    (templates/scripts/commit_guardian/transform_doc_frontmatter.py), so
    fixtures cannot silently drift from the real on-disk format.
    """
    fm_yaml = yaml.dump(
        fm_dict, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    fm_yaml = fm_yaml.rstrip("\n")
    return f"---\n{fm_yaml}\n---\n{body}"


_REALISTIC_EXISTING_CARD = _build_card_text(
    _EXISTING_CARD_FRONTMATTER, _EXISTING_CARD_BODY
)


# ---------------------------------------------------------------------------
# Test 1 — core regression: no-op rebuild on a later day writes nothing
# ---------------------------------------------------------------------------

class TestNoOpRebuildOnLaterDay:
    """BP-018: a build with unchanged inputs on a later day must not rewrite."""

    def test_ac1_noop_rebuild_on_later_day_writes_nothing(self, tmp_path):
        # covers: BP-018
        """BP-018: build_agent_cards() must not rewrite a card, and must not
        count it as written, when template/registry inputs are unchanged and
        only the calendar date has advanced since the last build.

        This is the core regression from the AC and the bug report: a
        `build.py --force-breaking` run on 2026-08-14 rewrote all 60 cards
        under docs/agents/cards/ purely because `generate_card()` hardcodes
        `created: {date.today()}`, defeating the existing compare-before-write
        guard on any day after the card was first generated.
        """
        target_root = tmp_path / "project"
        _write_minimal_project(target_root, TEMPLATE_FM)

        day1 = date(2026, 8, 13)
        day2 = date(2026, 8, 17)  # a later day; nothing else has changed

        with patch.object(generate_agent_cards, "date") as mock_date:
            mock_date.today.return_value = day1
            written_first = build_agent_cards(
                target_root=target_root, config={}, dry_run=False, force=False,
            )

        card_path = target_root / "docs" / "agents" / "cards" / "test-agent.card.md"
        assert card_path.exists(), "first build must create the card"
        assert written_first == 1
        content_after_first_build = card_path.read_text(encoding="utf-8")

        with patch.object(generate_agent_cards, "date") as mock_date:
            mock_date.today.return_value = day2
            written_second = build_agent_cards(
                target_root=target_root, config={}, dry_run=False, force=False,
            )

        content_after_second_build = card_path.read_text(encoding="utf-8")

        assert written_second == 0, (
            "a no-op rebuild on a later day must not be counted as written; "
            f"got written={written_second} (bug: date.today() is baked into "
            "the generated content, so the compare-before-write guard never "
            "matches on a later day)"
        )
        assert content_after_second_build == content_after_first_build, (
            "the card file on disk must be byte-for-byte identical after a "
            "no-op rebuild on a later day; it was rewritten instead"
        )


# ---------------------------------------------------------------------------
# Test 2 — `created` survives a genuine content rewrite
# ---------------------------------------------------------------------------

class TestCreatedSurvivesGenuineRewrite:
    """BP-018: on-disk `created` is carried through when content genuinely changes."""

    def test_ac2_created_carried_through_on_genuine_rewrite(self, tmp_path):
        # covers: BP-018
        """BP-018: when the card IS legitimately rewritten because substantive
        content changed, the `created` value already present on disk must
        survive unchanged — it must NOT be replaced with today's date.
        """
        target_root = tmp_path / "project"
        cards_dir = target_root / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        card_path = cards_dir / "test-agent.card.md"
        card_path.write_text(_REALISTIC_EXISTING_CARD, encoding="utf-8")

        # Substantive change: the description text itself changed.
        changed_fm = dict(TEMPLATE_FM)
        changed_fm["description"] = "A CHANGED description that forces a real rewrite."

        fake_today = date(2026, 8, 17)
        with patch.object(generate_agent_cards, "date") as mock_date:
            mock_date.today.return_value = fake_today
            result = generate_card(
                agent_id="test-agent",
                template_frontmatter=changed_fm,
                registry_entry=REGISTRY_ENTRY,
                card_path=card_path,
                package_root=target_root,
            )

        fm = _extract_frontmatter(result)
        assert str(fm.get("created")) == "2026-08-01", (
            "created must be carried through from the existing on-disk card "
            f"(expected '2026-08-01'), but generate_card() emitted "
            f"created={fm.get('created')!r} — it hardcodes date.today() "
            "instead of reading provenance from the existing card."
        )


# ---------------------------------------------------------------------------
# Test 3 — `last_updated` survives a genuine content rewrite
# ---------------------------------------------------------------------------

class TestLastUpdatedSurvivesRewrite:
    """BP-018: on-disk `last_updated` is not dropped by a genuine rewrite."""

    def test_ac3_last_updated_survives_rewrite(self, tmp_path):
        # covers: BP-018
        """BP-018: an existing `last_updated` value (maintained by the
        transform-doc-frontmatter commit hook, not by this generator) must
        survive a genuine content rewrite rather than being dropped from the
        frontmatter entirely.
        """
        target_root = tmp_path / "project"
        cards_dir = target_root / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        card_path = cards_dir / "test-agent.card.md"
        card_path.write_text(_REALISTIC_EXISTING_CARD, encoding="utf-8")

        changed_fm = dict(TEMPLATE_FM)
        changed_fm["description"] = "A CHANGED description that forces a real rewrite."

        fake_today = date(2026, 8, 17)
        with patch.object(generate_agent_cards, "date") as mock_date:
            mock_date.today.return_value = fake_today
            result = generate_card(
                agent_id="test-agent",
                template_frontmatter=changed_fm,
                registry_entry=REGISTRY_ENTRY,
                card_path=card_path,
                package_root=target_root,
            )

        fm = _extract_frontmatter(result)
        assert "last_updated" in fm, (
            "last_updated must survive a genuine rewrite, but the frontmatter "
            f"key is missing entirely from the regenerated card. Full "
            f"frontmatter: {fm}"
        )
        assert str(fm.get("last_updated")) == "2026-08-05", (
            "last_updated must be carried through unchanged from the existing "
            f"on-disk card (expected '2026-08-05'), got {fm.get('last_updated')!r}"
        )


# ---------------------------------------------------------------------------
# Test 4 — first generation (no file on disk) still stamps `created` = today
# ---------------------------------------------------------------------------

class TestFirstGenerationStampsToday:
    """BP-018: a brand-new card (no provenance to read) is still stamped with today."""

    def test_ac4_first_generation_stamps_created_as_today(self, tmp_path):
        # covers: BP-018
        """BP-018: when a card is being generated for the FIRST time (no file
        on disk to read provenance from), `created` must still be set to the
        current date.

        NOTE: this locks in behavior that is already correct in the current
        (buggy) implementation — generate_card() has no on-disk file to read
        provenance from in this case, so it already falls back to
        date.today(). This test is expected to PASS immediately; it is
        included as a characterization/regression lock so a future fix for
        AC-2/AC-3 (reading provenance off disk) cannot accidentally break the
        first-generation path. It is NOT part of the red_baseline — see the
        completion report for AC-1/AC-2/AC-3, which are the genuinely RED
        tests for this bug.
        """
        target_root = tmp_path / "project"
        _write_minimal_project(target_root, TEMPLATE_FM)

        card_path = target_root / "docs" / "agents" / "cards" / "test-agent.card.md"
        assert not card_path.exists()

        fake_today = date(2026, 8, 17)
        with patch.object(generate_agent_cards, "date") as mock_date:
            mock_date.today.return_value = fake_today
            written = build_agent_cards(
                target_root=target_root, config={}, dry_run=False, force=False,
            )

        assert written == 1
        assert card_path.exists()
        fm = _extract_frontmatter(card_path.read_text(encoding="utf-8"))
        assert str(fm.get("created")) == "2026-08-17", (
            f"first-time generation must stamp created with today's date "
            f"(expected '2026-08-17'), got {fm.get('created')!r}"
        )


# ---------------------------------------------------------------------------
# Test 5 — generated frontmatter is a fixed point of the commit hook's own
# transform (catches formatting-only mismatches AC-1/AC-2/AC-3 cannot see)
# ---------------------------------------------------------------------------

class TestGeneratedFrontmatterIsHookFixedPoint:
    """BP-018: generator output must not be reformatted by the commit hook.

    Once a card already carries full provenance (`created` AND
    `last_updated` both present), transform_doc_frontmatter.py's hook finds
    nothing missing and must leave the content untouched. If generate_card()
    serializes the frontmatter any differently than the hook's own
    `_rebuild_content()` would (different quoting, different line width,
    different key order), the hook rewrites the card on its NEXT commit even
    though the provenance values themselves are correct — reintroducing the
    churn BP-018 exists to eliminate, just one commit later than AC-1 can see
    on its own. This is exactly the gap a real-artifact check against the
    real docs/agents/cards/ files found after an earlier fix got the
    `created`/`last_updated` VALUES right but not the surrounding format.
    """

    def test_generated_frontmatter_survives_hook_transform_unchanged(self, tmp_path):
        # covers: BP-018
        """BP-018: generate_card()'s output, run through the hook's own
        transform_content(), must come back byte-identical with changed == 0.
        """
        target_root = tmp_path / "project"
        cards_dir = target_root / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        card_path = cards_dir / "test-agent.card.md"
        card_path.write_text(_REALISTIC_EXISTING_CARD, encoding="utf-8")

        fake_today = date(2026, 8, 17)
        with patch.object(generate_agent_cards, "date") as mock_date:
            mock_date.today.return_value = fake_today
            generated = generate_card(
                agent_id="test-agent",
                template_frontmatter=TEMPLATE_FM,
                registry_entry=REGISTRY_ENTRY,
                card_path=card_path,
                package_root=target_root,
            )

        defaults = {"type": "how-to", "status": "draft"}
        transformed, changed = transform_content(
            generated, today_date="2026-08-17", defaults=defaults,
        )

        assert changed == 0, (
            "transform_doc_frontmatter.py's hook found a field missing in "
            f"freshly generated card content (filled {changed} field(s)), "
            "but this card already carries full created + last_updated "
            "provenance — generate_card()'s output is not a fixed point of "
            "the hook's own frontmatter, so the hook would rewrite this "
            "card again on its next commit"
        )
        assert transformed == generated, (
            "generate_card()'s output must be byte-identical after running "
            "through the hook's transform_content(); any difference means "
            "a future commit reformats the card and defeats the "
            "compare-before-write guard on the following build"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
