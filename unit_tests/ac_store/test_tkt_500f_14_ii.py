"""
MODULE: test_tkt_500f_14_ii
GOAL: RED test stubs for TKT-500f-14-ii. Verifies that the recognised-source-code
      extension set (_SOURCE_CODE_EXTENSIONS) in generate_ticket_from_ac.py correctly
      bounds what counts as gating source code:

      1. EXCLUDES markup/style/shell files (.html, .css, .sh) — these must NOT be
         classified as gating source code. A ticket whose only source-ish file is
         .html/.css/.sh on a non-coder agent must NOT get ac-validator and
         ac-fulfillment-gate wired as needed phases (AC-1).

      2. INCLUDES common non-Python source files (.go, .rs, .mjs) — these MUST be
         recognised as gating source code. A ticket whose files_touched contains
         a .go, .rs, or .mjs file must wire ac-validator and ac-fulfillment-gate
         as needed phases, exactly as a .py or .js file already does (AC-2).

      Both test methods assert set membership directly on _SOURCE_CODE_EXTENSIONS
      (fast, targeted) and verify the same behaviour end-to-end by calling main()
      with --dry-run and parsing the YAML frontmatter from stdout (same pattern as
      test_tkt_500f_14.py and test_tkt_500f_14_i.py).

      A non-coder assigned_agent (documentation-expert) is used in each fixture so
      that the extension-set signal is isolated: the code-ticket gate can only fire
      via _has_source_file (files_touched extension check), not via
      _is_coder_assigned, making each assertion purely about set membership.

TICKET: TICKET-20260721-TKT-500f-14-ii.md
COVERS: TKT-500f-14-ii
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import (  # noqa: E402
    _SOURCE_CODE_EXTENSIONS,
    main as _main,
)


# ---------------------------------------------------------------------------
# Helper: run --dry-run and return the parsed frontmatter dict
# (same pattern as test_tkt_500f_14.py and test_tkt_500f_14_i.py)
# ---------------------------------------------------------------------------


def _run_dry_run(ac_data: dict, ac_id: str) -> dict:
    """Run generate_ticket_from_ac.py --dry-run with the given AC data.

    Writes a temporary AC YAML file, invokes main() with --dry-run, captures
    stdout, and parses the YAML frontmatter block from the output.

    Args:
        ac_data: AC record dict.  The 'id' key is set to *ac_id* automatically.
        ac_id:   The AC id to use for the fixture file.

    Returns:
        Parsed frontmatter dict, or an empty dict when parsing fails.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        ac_root = tmppath / "docs" / "acceptance-criteria" / "fixture-component"
        ac_root.mkdir(parents=True)

        ac_yaml_data = dict(ac_data)
        ac_yaml_data["id"] = ac_id

        ac_file = ac_root / f"{ac_id}.yaml"
        ac_file.write_text(yaml.dump(ac_yaml_data, allow_unicode=True), encoding="utf-8")

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            _main(
                [
                    "--ac", ac_id,
                    "--ac-root", str(tmppath / "docs" / "acceptance-criteria"),
                    "--dry-run",
                ]
            )

        output = captured.getvalue()

    # The output format is:  ---\n<YAML>\n---\n\n<body>\n
    # Split on "---" to extract the frontmatter block.
    parts = output.split("---")
    # parts[0] is empty (before first ---), parts[1] is the YAML, parts[2]+ is the body
    if len(parts) >= 3:
        try:
            parsed = yaml.safe_load(parts[1])
            if isinstance(parsed, dict):
                return parsed
        except yaml.YAMLError:
            pass
    return {}


# ---------------------------------------------------------------------------
# Shared fixture builder
# ---------------------------------------------------------------------------


def _non_coder_ac(ref_path: str, title_suffix: str) -> dict:
    """Build a minimal AC fixture for a non-coder agent with the given reference_file_path.

    documentation-expert is used as the assigned agent because:
      - It is NOT in _KNOWN_CODERS, so _is_coder_assigned=False.
      - The only path that can wire ac-validator/ac-fulfillment-gate is the
        extension-set check (_has_source_file), which is precisely what we test.
      - change_target=pipeline + risk_surface=internal: the guardrail produces only
        [pr-reviewer], so the gate agents can only arrive via the code-ticket signal.
    """
    return {
        "title": f"Fixture AC — TKT-500f-14-ii extension-set test ({title_suffix})",
        "level": "L2",
        "status": "active",
        "work_status": "todo",
        "assigned_agent": "documentation-expert",
        "component": "ticket-creation",
        "estimated_complexity": "S",
        "change_target": "pipeline",
        "risk_surface": "internal",
        "it_requirements": {
            "reference_file_path": ref_path,
        },
        "criteria": (
            f"Given a leaf AC with reference_file_path '{ref_path}' on a non-coder agent,\n"
            "When a ticket is generated from that AC by generate_ticket_from_ac.py,\n"
            "Then the extension-set gate signal is exercised per TKT-500f-14-ii."
        ),
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestExtensionSetBoundsMarkupStyleShellAndNonPySources(unittest.TestCase):
    """TKT-500f-14-ii: markup/style/shell excluded; .go/.rs/.mjs included.

    The recognised-source-code extension set (_SOURCE_CODE_EXTENSIONS) must be
    bounded in two directions:

    AC-1 — Exclusion boundary:
      .html, .css, .sh are markup/style/shell files, not source code.  They must
      be absent from _SOURCE_CODE_EXTENSIONS so that a ticket whose files_touched
      contains ONLY these extensions (on a non-coder agent) is NOT classified as a
      code ticket and does NOT receive ac-validator/ac-fulfillment-gate gates.

    AC-2 — Inclusion boundary:
      .go (Go), .rs (Rust), and .mjs (ES module) are common non-Python source files.
      They must be present in _SOURCE_CODE_EXTENSIONS so that a ticket whose
      files_touched contains one of these extensions wires ac-validator and
      ac-fulfillment-gate as needed phases, the same as .py or .js already does.

    Current state (makes both tests RED before implementation):
      _SOURCE_CODE_EXTENSIONS = (_PROSE_PATH_EXTENSIONS - _DOC_CONFIG_EXTENSIONS)
                                | {".tsx", ".jsx", ".vue", ".svelte"}
      - .html, .css, .sh pass through the subtraction (absent from
        _DOC_CONFIG_EXTENSIONS) → currently IN the set → AC-1 tests FAIL.
      - .go, .rs, .mjs absent from _PROSE_PATH_EXTENSIONS → absent from derived set
        → currently NOT in the set → AC-2 tests FAIL.
    """

    def test_markup_style_shell_not_gating_source(self):
        # covers: TKT-500f-14-ii
        """AC-1: .html, .css, .sh must NOT be in _SOURCE_CODE_EXTENSIONS.

        A generated ticket whose files_touched is only .html/.css/.sh on a non-coder
        agent must NOT force-add ac-validator or ac-fulfillment-gate.

        Must be RED before implementation: _SOURCE_CODE_EXTENSIONS currently includes
        .html, .css, and .sh because _DOC_CONFIG_EXTENSIONS only removes docs/config
        suffixes (.md, .yaml, .yml, .json, .txt, .toml, .cfg, .ini) and does not
        exclude markup/style/shell suffixes.  As a result _has_source_file=True for
        these files, incorrectly wiring the AC gates even for non-coder tickets.

        After the fix (TKT-500f-14-ii), .html/.css/.sh must be excluded from
        _SOURCE_CODE_EXTENSIONS (e.g. by adding them to _DOC_CONFIG_EXTENSIONS or
        by excluding them via a dedicated frozenset literal in the derivation formula).

        Two assertion layers per extension:
          1. Direct set-membership assertion on _SOURCE_CODE_EXTENSIONS.
          2. End-to-end _run_dry_run assertion on the generated agents map.
        """
        # --- Layer 1: direct set-membership assertions ---
        markup_shell_exts = (".html", ".css", ".sh")
        for ext in markup_shell_exts:
            with self.subTest(ext=ext, layer="set_membership"):
                self.assertNotIn(
                    ext,
                    _SOURCE_CODE_EXTENSIONS,
                    (
                        f"{ext!r} must NOT be in _SOURCE_CODE_EXTENSIONS — markup/style/shell "
                        f"files are not gating source code (TKT-500f-14-ii AC-1). "
                        f"Current _SOURCE_CODE_EXTENSIONS: {sorted(_SOURCE_CODE_EXTENSIONS)!r}. "
                        f"The derivation _PROSE_PATH_EXTENSIONS - _DOC_CONFIG_EXTENSIONS leaves "
                        f"{ext!r} in the set because _DOC_CONFIG_EXTENSIONS does not exclude it. "
                        f"Fix: add {ext!r} to _DOC_CONFIG_EXTENSIONS or to a dedicated exclusion "
                        f"set in the _SOURCE_CODE_EXTENSIONS formula."
                    ),
                )

        # --- Layer 2: end-to-end generator assertions (matches -14 test style) ---
        fixtures = [
            (".html", "templates/frontend/index.html"),
            (".css",  "templates/frontend/styles.css"),
            (".sh",   "scripts/deploy.sh"),
        ]
        for ext, ref_path in fixtures:
            with self.subTest(ext=ext, layer="end_to_end"):
                ac_id = f"TKT-500f-14-ii-markup-{ext.lstrip('.')}"
                ac_data = _non_coder_ac(ref_path, f"markup/style/shell {ext}")
                fm = _run_dry_run(ac_data, ac_id=ac_id)
                agents = fm.get("agents", {})

                self.assertNotEqual(
                    agents.get("ac-validator"),
                    "needed",
                    (
                        f"ac-validator must NOT be wired as 'needed' when files_touched "
                        f"contains only a {ext!r} file and assigned_agent is a non-coder "
                        f"(documentation-expert). "
                        f"Current agents map: {agents!r}. "
                        f"_SOURCE_CODE_EXTENSIONS currently includes {ext!r}, causing "
                        f"_has_source_file=True and incorrectly firing the AC-gate signal "
                        f"for markup/style/shell tickets. "
                        f"Fix: exclude .html/.css/.sh from _SOURCE_CODE_EXTENSIONS."
                    ),
                )

                self.assertNotEqual(
                    agents.get("ac-fulfillment-gate"),
                    "needed",
                    (
                        f"ac-fulfillment-gate must NOT be wired as 'needed' when files_touched "
                        f"contains only a {ext!r} file and assigned_agent is a non-coder. "
                        f"Current agents map: {agents!r}. "
                        f"_SOURCE_CODE_EXTENSIONS currently includes {ext!r}; "
                        f"fix: exclude .html/.css/.sh from _SOURCE_CODE_EXTENSIONS."
                    ),
                )

    def test_go_rs_mjs_recognised_as_gating_source(self):
        # covers: TKT-500f-14-ii
        """AC-2: .go, .rs, .mjs must be in _SOURCE_CODE_EXTENSIONS.

        A generated ticket with a .go, .rs, or .mjs file must wire ac-validator
        and ac-fulfillment-gate as needed phases, the same as a .py/.js source file.

        Must be RED before implementation: .go, .rs, and .mjs are absent from
        _PROSE_PATH_EXTENSIONS (the base set for the _SOURCE_CODE_EXTENSIONS
        derivation), so they are also absent from the derived set.  A non-coder
        assigned agent (documentation-expert) is used so that _is_coder_assigned=False
        and the ONLY signal path to wire the gate is via _has_source_file (the
        extension-set check).  With the current implementation both signals are False
        for .go/.rs/.mjs + non-coder, so neither gate is wired.

        After the fix (TKT-500f-14-ii), .go/.rs/.mjs must be added to
        _SOURCE_CODE_EXTENSIONS so that _has_source_file=True for these files and
        the gate is correctly wired.

        Two assertion layers per extension:
          1. Direct set-membership assertion on _SOURCE_CODE_EXTENSIONS.
          2. End-to-end _run_dry_run assertion on the generated agents map.
        """
        # --- Layer 1: direct set-membership assertions ---
        non_py_source_exts = (".go", ".rs", ".mjs")
        for ext in non_py_source_exts:
            with self.subTest(ext=ext, layer="set_membership"):
                self.assertIn(
                    ext,
                    _SOURCE_CODE_EXTENSIONS,
                    (
                        f"{ext!r} must be in _SOURCE_CODE_EXTENSIONS — it is a common "
                        f"non-Python source extension that must trigger the code-ticket "
                        f"AC-gate signal (TKT-500f-14-ii AC-2). "
                        f"Current _SOURCE_CODE_EXTENSIONS: {sorted(_SOURCE_CODE_EXTENSIONS)!r}. "
                        f"{ext!r} is absent because it is not in _PROSE_PATH_EXTENSIONS "
                        f"(the base set for the derivation). "
                        f"Fix: add {ext!r} to _PROSE_PATH_EXTENSIONS or include it directly "
                        f"in the frozenset extension literal in the _SOURCE_CODE_EXTENSIONS "
                        f"derivation formula."
                    ),
                )

        # --- Layer 2: end-to-end generator assertions (matches -14 test style) ---
        fixtures = [
            (".go",  "scripts/server/main.go"),
            (".rs",  "scripts/server/lib.rs"),
            (".mjs", "templates/workflows/build.mjs"),
        ]
        for ext, ref_path in fixtures:
            with self.subTest(ext=ext, layer="end_to_end"):
                ac_id = f"TKT-500f-14-ii-source-{ext.lstrip('.')}"
                ac_data = _non_coder_ac(ref_path, f"non-py source {ext}")
                fm = _run_dry_run(ac_data, ac_id=ac_id)
                agents = fm.get("agents", {})

                self.assertEqual(
                    agents.get("ac-validator"),
                    "needed",
                    (
                        f"ac-validator must be wired as 'needed' when files_touched "
                        f"contains a {ext!r} file (TKT-500f-14-ii AC-2). "
                        f"Current agents map: {agents!r}. "
                        f"{ext!r} is absent from _SOURCE_CODE_EXTENSIONS, so "
                        f"_has_source_file=False.  With documentation-expert as assigned "
                        f"agent, _is_coder_assigned=False too — neither signal wires the "
                        f"gate under the current implementation. "
                        f"Fix: add .go/.rs/.mjs to _SOURCE_CODE_EXTENSIONS."
                    ),
                )

                self.assertEqual(
                    agents.get("ac-fulfillment-gate"),
                    "needed",
                    (
                        f"ac-fulfillment-gate must be wired as 'needed' when files_touched "
                        f"contains a {ext!r} file (TKT-500f-14-ii AC-2). "
                        f"Current agents map: {agents!r}. "
                        f"Fix: add .go/.rs/.mjs to _SOURCE_CODE_EXTENSIONS."
                    ),
                )


if __name__ == "__main__":
    unittest.main()
