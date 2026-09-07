"""
MODULE: unit_tests/commit_guardian/test_bp_1100g_5_i.py
COVERS: BP-1100g-5-i

GOAL: RED test stubs for the cross_layer_seam_answer shortfall reader — a
    commit-time reader over a ticket's ``## Comments`` ``completion_manifest:``
    block(s) that reports exactly three named shortfall kinds against the
    BP-1100g-5 shipped record shape (SKILL.md §2b.2, key
    ``cross_layer_seam_answer``, shapes ``{result: covered, producing_side,
    consuming_side}`` and ``{result: not_applicable, reason, remediation}``):

        - "reasonless"              — result: not_applicable with no reason
        - "absent"                  — a completion_manifest exists for this
                                       work item but carries no
                                       cross_layer_seam_answer key at all
        - "answered_more_than_once" — the same work item's hand-off record
                                       carries the key more than once

    A reasoned negative (result: not_applicable + a non-empty reason) is a
    valid answer and must never be reported. A run that never produced a
    completion_manifest for a work item at all (halted before hand-off, or a
    pre-epoch legacy sign-off with no manifest block per SKILL.md §2b Legacy
    Compatibility) is a DIFFERENT state from "absent" and must also never be
    reported — see BP-1100g-5-i's fourth Then-clause and its notes' "NO
    RECORD AND A BAD RECORD ARE DIFFERENT STATES".

BUSINESS CONTEXT: completion_manifest has ZERO code readers today (verified:
    grep over scripts/ returns no occurrences). This ticket builds the FIRST
    one, extending the existing ticket parser (``_signoff_parity_checks.py``,
    already hosting the ``## Sign-offs`` parity checks) rather than adding a
    second ticket parser, per this AC's own it_requirements. The anti-grep
    clause is binding throughout this file: cardinality for the
    answered-more-than-once case MUST come from the raw text the run actually
    emitted (a duplicate ``cross_layer_seam_answer:`` key collapses silently
    under a plain ``yaml.safe_load`` — PyYAML's default loader does not raise
    on duplicate mapping keys, it just keeps the last one) — never from
    grepping test-writer's source code for how many times it calls a
    hypothetical "record the answer" function. This carries BO-1000b-1-i's
    trap forward: that ticket's count-guard regex matched only quoted-string
    call sites and was blind to template-literal ones, so the double-write
    defect shipped anyway.

ARCHITECTURE: Interface contract under test (to be implemented by
    python-coder, extending ``templates/scripts/commit_guardian/
    _signoff_parity_checks.py`` — the deployed copy is reached here via the
    ``scripts/commit_guardian`` import path per this repo's existing
    convention for these modules, matching
    ``unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py``
    and ``unit_tests/commit_guardian/test_bp_1100g_4.py``):

    extract_cross_layer_seam_answers(content: str) -> list[dict] | None
        Scans a ticket's full text for every ``cross_layer_seam_answer:``
        occurrence inside a ``completion_manifest:`` block, in document
        order, and returns:
            None  — no ``completion_manifest:`` block exists ANYWHERE in
                    ``content`` (the no-record / halted-run / legacy state —
                    see SKILL.md §2b Legacy Compatibility).
            []    — at least one ``completion_manifest:`` block exists, but
                    none of them carries the ``cross_layer_seam_answer`` key.
            [ans, ...] — one parsed dict per RAW TEXTUAL occurrence of the
                    key (cardinality reflects the text, never a
                    de-duplicated ``dict`` built by ``yaml.safe_load`` on the
                    whole block, which would silently collapse a duplicate
                    key to one entry).

    check_cross_layer_seam_answer(content: str, ticket_path: str) -> dict | None
        Applies the BP-1100g-5-i shortfall rule to one ticket's hand-off
        record and returns, per the ticket's own delivers_to contract:
            None — no shortfall: either the no-record state (see above), or
                   exactly one conforming answer (``result: covered`` with
                   both sides named, or ``result: not_applicable`` with a
                   non-empty ``reason``).
            {"work_item_id": ticket_path, "kind": "reasonless" |
             "absent" | "answered_more_than_once", "detail": <non-empty str>}
                   otherwise.

    Hook registration (REGISTRATION IS PART OF THE WORK, per this AC's own
    it_requirements): the pre-existing hook id ``check-ticket-signoff-parity``
    must appear in ``templates/scripts/commit_guardian/commit_guardian.json``'s
    ``hooks_manifest.hooks`` array — confirmed ABSENT from every
    ``.pre-commit-config.yaml`` and from ``commit_guardian.json`` today (see
    BO-400d-3's own finding: "check-ticket-signoff-parity appears in NO
    .pre-commit-config.yaml"). Reachability of this new reader depends on
    that registration existing, so it is in scope here, not deferred to
    BO-400d-3 / TQ-500b-1 (which track the pre-existing, unrelated gap of the
    hook never having been wired to run at all).

    Wiring: the new shortfall(s) for a ticket must be appended into the same
    stderr-printed violation stream ``check_ticket_signoff_parity.py`` already
    produces (``<path>: <message>`` per line, see ``main()``), naming the
    shortfall kind by its exact token so a reader can grep the hook's own
    output for it.

=== Red baseline ===

    RED today: neither ``extract_cross_layer_seam_answers`` nor
    ``check_cross_layer_seam_answer`` exists in ``_signoff_parity_checks.py``
    (verified: no occurrence of either name or of the string
    ``cross_layer_seam_answer`` anywhere under ``scripts/`` or ``templates/``),
    so every import below raises ImportError. The hook-registration assertion
    in the reachability test fails independently, because
    ``check-ticket-signoff-parity`` is registered nowhere today.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"

if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

_SUBPROCESS_TIMEOUT_SECONDS = 60


# ---------------------------------------------------------------------------
# Fixture builders — real serializer, never a hand-typed YAML literal (2h.2)
# ---------------------------------------------------------------------------


def _dump_seam_answer_yaml(answer: dict) -> str:
    """Serialize ONE ``cross_layer_seam_answer`` mapping via the REAL
    ``yaml.safe_dump`` serializer — never a hand-typed literal.

    Args:
        answer: The nested mapping (e.g. ``{"result": "covered", ...}``).

    Returns:
        The serialized ``cross_layer_seam_answer:\\n  ...`` text, no
        trailing newline.
    """
    return yaml.safe_dump(
        {"cross_layer_seam_answer": answer}, default_flow_style=False, sort_keys=False
    ).rstrip("\n")


def _indent(text: str, spaces: int) -> str:
    """Indent every non-blank line of *text* by *spaces* spaces."""
    pad = " " * spaces
    return "\n".join((pad + line if line.strip() else line) for line in text.splitlines())


def _build_completion_manifest_block(
    seam_answers: list[dict] | None = None,
    other_items: dict | None = None,
) -> str:
    """Build a real ``completion_manifest:`` text block.

    Each entry in *seam_answers* is independently produced by the real
    ``yaml.safe_dump`` serializer (see ``_dump_seam_answer_yaml``). Passing
    more than one entry reproduces the BO-1000b-1-i double-recording defect
    SHAPE textually — exactly how a buggy conditional-plus-unconditional
    write would emit it — while every individual answer is still real,
    machine-serialized YAML; only their concatenation into one manifest is
    test-assembled.

    Args:
        seam_answers: Zero, one, or more than one seam-answer mappings.
        other_items: Unrelated bare-``true`` manifest items (e.g.
            ``{"tests_written": True}``) so a manifest that omits the seam
            key is a REAL, populated manifest, not an artificially empty one.

    Returns:
        The full ``completion_manifest:`` block text (no trailing newline).
    """
    lines = ["completion_manifest:"]
    if other_items:
        other_text = yaml.safe_dump(
            other_items, default_flow_style=False, sort_keys=False
        ).rstrip("\n")
        lines.append(_indent(other_text, 2))
    for answer in seam_answers or []:
        lines.append(_indent(_dump_seam_answer_yaml(answer), 2))
    return "\n".join(lines)


def _build_ticket_fixture(
    work_item_id: str,
    *,
    include_completion_manifest: bool,
    seam_answers: list[dict] | None = None,
    other_manifest_items: dict | None = None,
) -> str:
    """Build a real, minimal ticket ``.md`` file body for one work item.

    ``include_completion_manifest=False`` produces the "halted run" / legacy
    shape: a ticket whose ``## Comments`` sign-off entry never wrote a
    ``completion_manifest:`` block at all — the no-record state, distinct
    from a completion_manifest that omits the seam key.

    Args:
        work_item_id: A short slug used in the title and as part of the
            frontmatter, purely for readability of failures.
        include_completion_manifest: Whether the sign-off comment includes a
            ``completion_manifest:`` block at all.
        seam_answers: Forwarded to ``_build_completion_manifest_block``.
        other_manifest_items: Forwarded to ``_build_completion_manifest_block``.

    Returns:
        Full ticket markdown text, frontmatter + ``## Sign-offs`` +
        ``## Comments``.
    """
    fm = {
        "title": f"zz fixture {work_item_id}",
        "status": "in_progress",
        "components": ["build_pipeline"],
        "created": "2026-08-31",
        "depends_on": [],
        "agents": {"test-writer": "signed_off"},
    }
    frontmatter_text = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False).rstrip("\n")
    lines = [
        "---",
        frontmatter_text,
        "---",
        "",
        f"# {work_item_id}",
        "",
        "## Sign-offs",
        "",
        "- [x] test-writer — 2026-08-31 12:00",
        "",
        "## Comments",
        "",
        "### 2026-08-31 12:00 — test-writer (status: ok)",
        "feedback-id: fb_2026-08-31_zzzzzzzz",
    ]
    if include_completion_manifest:
        lines.append(_build_completion_manifest_block(seam_answers, other_manifest_items))
    lines.append("")
    lines.append("Prose summary sentence for this fixture sign-off comment.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# angle: criterion
# ---------------------------------------------------------------------------


class TestFourRecordsProduceThreeNamedShortfallsAndNoReportForW(unittest.TestCase):
    """test_spec: test_bp_1100g_5_i_four_records_produce_three_named_shortfalls_and_no_report_for_w
    (angle: criterion). The four records from the AC's own Gherkin: W (reasoned
    negative, not reported), X (reasonless), Y (absent), Z (answered twice)."""

    def test_bp_1100g_5_i_four_records_produce_three_named_shortfalls_and_no_report_for_w(
        self,
    ) -> None:
        # covers: BP-1100g-5-i
        # angle: criterion
        """W -> no report. X -> reasonless. Y -> absent. Z -> answered_more_than_once."""
        from _signoff_parity_checks import check_cross_layer_seam_answer

        content_w = _build_ticket_fixture(
            "record-w",
            include_completion_manifest=True,
            seam_answers=[
                {
                    "result": "not_applicable",
                    "reason": "pure function, no consumer outside its own module",
                    "remediation": "n/a - not_applicable is a first-class outcome, not a defect.",
                }
            ],
        )
        content_x = _build_ticket_fixture(
            "record-x",
            include_completion_manifest=True,
            seam_answers=[{"result": "not_applicable", "reason": ""}],
        )
        content_y = _build_ticket_fixture(
            "record-y",
            include_completion_manifest=True,
            seam_answers=[],
            other_manifest_items={"tests_written": True},
        )
        content_z = _build_ticket_fixture(
            "record-z",
            include_completion_manifest=True,
            seam_answers=[
                {"result": "covered", "producing_side": "module A", "consuming_side": "module B"},
                {"result": "not_applicable", "reason": "left over from an earlier branch"},
            ],
        )

        result_w = check_cross_layer_seam_answer(content_w, "record-w.md")
        self.assertIsNone(
            result_w,
            f"record W (reasoned negative) must NOT be reported: got {result_w!r}",
        )

        result_x = check_cross_layer_seam_answer(content_x, "record-x.md")
        self.assertIsNotNone(result_x, "record X (reasonless) must be reported")
        self.assertEqual(result_x["kind"], "reasonless")
        self.assertEqual(result_x["work_item_id"], "record-x.md")
        self.assertTrue(result_x.get("detail"), "detail must be a non-empty, actionable string")

        result_y = check_cross_layer_seam_answer(content_y, "record-y.md")
        self.assertIsNotNone(result_y, "record Y (no seam answer at all) must be reported")
        self.assertEqual(result_y["kind"], "absent")
        self.assertEqual(result_y["work_item_id"], "record-y.md")

        result_z = check_cross_layer_seam_answer(content_z, "record-z.md")
        self.assertIsNotNone(result_z, "record Z (answered twice) must be reported")
        self.assertEqual(result_z["kind"], "answered_more_than_once")
        self.assertEqual(result_z["work_item_id"], "record-z.md")


# ---------------------------------------------------------------------------
# angle: real_artifact
# ---------------------------------------------------------------------------


class TestRecordsAreParsedFromRealTicketFilesWrittenBySignoffRecipe(unittest.TestCase):
    """test_spec: test_bp_1100g_5_i_records_are_parsed_from_real_ticket_files_written_by_the_signoff_recipe
    (angle: real_artifact). The four records built as REAL on-disk ticket
    files via the real ``yaml.safe_dump`` serializer (per the signoff SKILL
    recipe), round-tripped through disk before parsing."""

    def test_bp_1100g_5_i_records_are_parsed_from_real_ticket_files_written_by_the_signoff_recipe(
        self,
    ) -> None:
        # covers: BP-1100g-5-i
        # angle: real_artifact
        """Write the four records to real files, read them back, and parse the
        ROUND-TRIPPED text — never a hand-typed markdown literal."""
        from _signoff_parity_checks import check_cross_layer_seam_answer

        records = {
            "record-w.md": (
                _build_ticket_fixture(
                    "record-w",
                    include_completion_manifest=True,
                    seam_answers=[{"result": "not_applicable", "reason": "pure function"}],
                ),
                None,
            ),
            "record-x.md": (
                _build_ticket_fixture(
                    "record-x",
                    include_completion_manifest=True,
                    seam_answers=[{"result": "not_applicable", "reason": ""}],
                ),
                "reasonless",
            ),
            "record-y.md": (
                _build_ticket_fixture(
                    "record-y",
                    include_completion_manifest=True,
                    seam_answers=[],
                    other_manifest_items={"tests_written": True},
                ),
                "absent",
            ),
            "record-z.md": (
                _build_ticket_fixture(
                    "record-z",
                    include_completion_manifest=True,
                    seam_answers=[
                        {"result": "covered", "producing_side": "p", "consuming_side": "c"},
                        {"result": "not_applicable", "reason": "leftover"},
                    ],
                ),
                "answered_more_than_once",
            ),
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            written_paths: dict[str, Path] = {}
            for name, (content, _expected) in records.items():
                path = tmp_path / name
                path.write_text(content, encoding="utf-8")
                written_paths[name] = path

            for name, path in written_paths.items():
                _content, expected_kind = records[name]
                roundtripped = path.read_text(encoding="utf-8")
                result = check_cross_layer_seam_answer(roundtripped, str(path))
                if expected_kind is None:
                    self.assertIsNone(
                        result,
                        f"{name}: expected no report from the round-tripped real "
                        f"file, got {result!r}",
                    )
                else:
                    self.assertIsNotNone(
                        result,
                        f"{name}: expected a {expected_kind!r} report from the "
                        f"round-tripped real file, got None",
                    )
                    self.assertEqual(result["kind"], expected_kind, f"{name}: {result!r}")


# ---------------------------------------------------------------------------
# angle: boundary
# ---------------------------------------------------------------------------


class TestCardinalityIsCountedPerWorkItemAcrossTwoItemsAndAHaltedRun(unittest.TestCase):
    """test_spec: test_bp_1100g_5_i_cardinality_is_counted_per_work_item_across_two_items_and_a_halted_run
    (angle: boundary). Zero / one / two answers for a single item; two
    DIFFERENT items each carrying their own single answer (per-item, not
    per-run); and a run halted before hand-off (no completion_manifest at
    all), which must yield nothing."""

    def test_bp_1100g_5_i_cardinality_is_counted_per_work_item_across_two_items_and_a_halted_run(
        self,
    ) -> None:
        # covers: BP-1100g-5-i
        # angle: boundary
        """0/1/2 answers for one item; two items each with their own answer;
        a halted run (no completion_manifest at all) reports nothing."""
        from _signoff_parity_checks import check_cross_layer_seam_answer

        # Zero answers: completion_manifest present, seam key absent.
        zero_content = _build_ticket_fixture(
            "boundary-zero",
            include_completion_manifest=True,
            seam_answers=[],
            other_manifest_items={"tests_written": True},
        )
        zero_result = check_cross_layer_seam_answer(zero_content, "boundary-zero.md")
        self.assertIsNotNone(zero_result)
        self.assertEqual(zero_result["kind"], "absent")

        # One answer, conforming (covered) -> no report.
        one_content = _build_ticket_fixture(
            "boundary-one",
            include_completion_manifest=True,
            seam_answers=[{"result": "covered", "producing_side": "p", "consuming_side": "c"}],
        )
        one_result = check_cross_layer_seam_answer(one_content, "boundary-one.md")
        self.assertIsNone(one_result, f"a single conforming answer must not be reported: {one_result!r}")

        # Two answers for the SAME item -> answered_more_than_once.
        two_content = _build_ticket_fixture(
            "boundary-two",
            include_completion_manifest=True,
            seam_answers=[
                {"result": "not_applicable", "reason": "first"},
                {"result": "not_applicable", "reason": "second"},
            ],
        )
        two_result = check_cross_layer_seam_answer(two_content, "boundary-two.md")
        self.assertIsNotNone(two_result)
        self.assertEqual(two_result["kind"], "answered_more_than_once")

        # Two DIFFERENT work items in the same run, each with its OWN single
        # answer — independence check (per work item, not per run).
        item_a_content = _build_ticket_fixture(
            "item-a",
            include_completion_manifest=True,
            seam_answers=[{"result": "not_applicable", "reason": ""}],
        )
        item_b_content = _build_ticket_fixture(
            "item-b",
            include_completion_manifest=True,
            seam_answers=[{"result": "covered", "producing_side": "p", "consuming_side": "c"}],
        )
        result_a = check_cross_layer_seam_answer(item_a_content, "item-a.md")
        result_b = check_cross_layer_seam_answer(item_b_content, "item-b.md")
        self.assertIsNotNone(result_a)
        self.assertEqual(result_a["kind"], "reasonless")
        self.assertEqual(result_a["work_item_id"], "item-a.md")
        self.assertIsNone(
            result_b,
            f"item B's own conforming answer must not be affected by item A's "
            f"shortfall in the same run: {result_b!r}",
        )

        # A run halted before hand-off: no completion_manifest block at all.
        halted_content = _build_ticket_fixture("halted", include_completion_manifest=False)
        halted_result = check_cross_layer_seam_answer(halted_content, "halted.md")
        self.assertIsNone(
            halted_result,
            f"a ticket with no completion_manifest at all (halted run) must "
            f"yield nothing — not a reasonless or contradictory report: {halted_result!r}",
        )


# ---------------------------------------------------------------------------
# angle: reachability
# ---------------------------------------------------------------------------


class TestShortfallsAreReportedThroughTheDeployedSignoffHook(unittest.TestCase):
    """test_spec: test_bp_1100g_5_i_shortfalls_are_reported_through_the_deployed_signoff_hook
    (angle: reachability). PRODUCTION ENTRY POINT test: run the deployed
    ``check_ticket_signoff_parity.py`` hook via the deployed ``run_hook.py``
    wrapper against four real staged ticket files, and assert the three
    shortfalls appear BY NAME in the hook's own output. Also asserts hook-id
    registration directly (registration is part of the work — see
    BO-400d-3's finding that this hook is registered nowhere today)."""

    def test_bp_1100g_5_i_shortfalls_are_reported_through_the_deployed_signoff_hook(
        self,
    ) -> None:
        # covers: BP-1100g-5-i
        # angle: reachability
        """The deployed hook, invoked exactly as pre-commit would invoke it,
        exits non-zero and names each of the three shortfall kinds by their
        exact token, attached to the correct ticket, and never for record W."""
        manifest_path = _REPO_ROOT / "scripts" / "commit_guardian" / "commit_guardian.json"
        self.assertTrue(
            manifest_path.is_file(),
            f"hooks manifest not found at {manifest_path} — run "
            "`python scripts/build.py --target-dir .` first",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hooks_list = manifest.get("hooks_manifest", {}).get("hooks", [])
        hook_ids = {h.get("id") for h in hooks_list}
        self.assertIn(
            "check-ticket-signoff-parity",
            hook_ids,
            f"hook id 'check-ticket-signoff-parity' is not registered in "
            f"{manifest_path} (found ids: {sorted(i for i in hook_ids if i)}) — "
            "an unregistered gate never runs.",
        )

        deployed_run_hook = (
            _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "run_hook.py"
        )
        deployed_hook = (
            _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "check_ticket_signoff_parity.py"
        )
        self.assertTrue(
            deployed_run_hook.is_file(),
            f"deployed run_hook.py wrapper not found at {deployed_run_hook}",
        )
        self.assertTrue(
            deployed_hook.is_file(),
            f"deployed check_ticket_signoff_parity.py not found at {deployed_hook}",
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixtures = {
                "zz-bp1100g5i-record-w.md": _build_ticket_fixture(
                    "record-w",
                    include_completion_manifest=True,
                    seam_answers=[
                        {"result": "not_applicable", "reason": "pure function, no seam"}
                    ],
                ),
                "zz-bp1100g5i-record-x.md": _build_ticket_fixture(
                    "record-x",
                    include_completion_manifest=True,
                    seam_answers=[{"result": "not_applicable", "reason": ""}],
                ),
                "zz-bp1100g5i-record-y.md": _build_ticket_fixture(
                    "record-y",
                    include_completion_manifest=True,
                    seam_answers=[],
                    other_manifest_items={"tests_written": True},
                ),
                "zz-bp1100g5i-record-z.md": _build_ticket_fixture(
                    "record-z",
                    include_completion_manifest=True,
                    seam_answers=[
                        {"result": "covered", "producing_side": "p", "consuming_side": "c"},
                        {"result": "not_applicable", "reason": "leftover"},
                    ],
                ),
            }
            written_paths = []
            for name, content in fixtures.items():
                path = tmp_path / name
                path.write_text(content, encoding="utf-8")
                written_paths.append(str(path))

            result = subprocess.run(
                [
                    sys.executable,
                    str(deployed_run_hook),
                    str(deployed_hook),
                    "--enforce",
                    *written_paths,
                ],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            )

        combined = result.stdout + result.stderr
        self.assertNotEqual(
            result.returncode,
            0,
            f"the deployed hook must exit non-zero when shortfalls exist. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

        def _lines_for(name: str) -> list[str]:
            return [ln for ln in combined.splitlines() if name in ln]

        w_lines = _lines_for("zz-bp1100g5i-record-w.md")
        for kind in ("reasonless", "absent", "answered_more_than_once"):
            self.assertFalse(
                any(kind in ln for ln in w_lines),
                f"record W (reasoned negative) must never be reported as a "
                f"shortfall: {w_lines!r}",
            )

        x_lines = _lines_for("zz-bp1100g5i-record-x.md")
        self.assertTrue(
            any("reasonless" in ln for ln in x_lines),
            f"record X must be reported as reasonless BY NAME: combined output={combined!r}",
        )

        y_lines = _lines_for("zz-bp1100g5i-record-y.md")
        self.assertTrue(
            any("absent" in ln for ln in y_lines),
            f"record Y must be reported as absent BY NAME: combined output={combined!r}",
        )

        z_lines = _lines_for("zz-bp1100g5i-record-z.md")
        self.assertTrue(
            any("answered_more_than_once" in ln for ln in z_lines),
            f"record Z must be reported as answered_more_than_once BY NAME: "
            f"combined output={combined!r}",
        )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-08-31 [test-writer/BP-1100g-5-i]: Initial RED test stubs. Four tests
  covering the four taught test_spec angles (criterion, real_artifact,
  boundary, reachability). Contract: ``extract_cross_layer_seam_answers`` and
  ``check_cross_layer_seam_answer`` to be added to
  ``_signoff_parity_checks.py`` (extending the existing ticket parser per
  it_requirement 1, not a second parser), plus registration of the
  pre-existing but never-wired ``check-ticket-signoff-parity`` hook id in
  ``commit_guardian.json``'s ``hooks_manifest`` (part of this ticket's scope
  per it_requirement 8, distinct from BO-400d-3/TQ-500b-1's broader gap).
====================================================================
"""
