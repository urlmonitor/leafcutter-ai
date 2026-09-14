"""
MODULE: test_uxp_700e_2
GOAL: Pin the contract for UXP-700e-2 — "Each thing is described once; a
    shorter form is derived, never separately authored." Today
    docs/product-truth/index.json's `artifacts[].summary` for every flow-type
    artifact is a SEPARATELY HAND-AUTHORED short description that merely
    happens to sit next to the flow's own, authoritative `summary` field
    (confirmed by direct execution against the live store, 2026-09-09: the
    `leafcutter/how-acs-are-built` flow's own summary is 938 characters; the
    index artifact's stored summary for the same journey is a different,
    shorter, independently-typed string). This is EXACTLY the duplication
    this AC's own `notes` field measures across all 14 journeys ("index
    copies run 89 to 218 characters; the source descriptions run 365 to
    938... how-acs-are-built 197 vs 938; author-product-truth 218 vs 731;
    checkout-and-pay 203 vs 748").
BUSINESS CONTEXT: The sibling ticket UXP-514-6 (separate, not this ticket's
    scope) will GUARD this duplication with a generic drift check while it
    exists. THIS ticket's job is to remove the duplication at the root, by
    making docs/product-truth/scripts/generate_product_truth.py — the
    store's single derived-data writer — compute each flow-type artifact's
    index `summary` FROM the flow's own `summary` field at generation time,
    the same way it already computes `by_ac` / `by_flow` / node
    `impl_status` from source data on every run, rather than reading a
    value that was typed once, by hand, and never touched again.
ARCHITECTURE: Targets EXISTING module
    docs/product-truth/scripts/generate_product_truth.py (imported here as
    `gpt`). No new CLI is introduced; the CLI is `generate_product_truth.py`
    itself (`if __name__ == "__main__": sys.exit(main())`, already shipped).
    The tests below assume the natural, minimal-diff implementation: extend
    `write_index()` (or a helper it calls) to overwrite, for every
    `artifacts[]` entry whose `type == "flow"`, the entry's `summary` with a
    value derived from `flows[entry["id"]]["summary"]` — exactly the field
    and the two locations ("index" and "flow file") this AC's own `notes`
    and UXP-514-6's sibling notes both measure. Every test below is expected
    to fail (red) until that derivation is wired in, because NOTHING in the
    current `generate_product_truth.py` touches `artifacts[].summary` at all
    (`write_index` only syncs `artifacts[].impl_summary` today — see its
    existing "Sync artifact impl_summary entries" step).

    Test-file layout, mirroring unit_tests/product_truth/test_uxp_700c_1.py's
    established layout for this module family:
      * TestDerivedFromAuthoritative — angle: criterion. Runs the REAL
        `gpt.generate()` producer against a from-scratch fixture store and
        reads the REAL index.json it writes back, asserting the derived
        artifact summary is computed from (not independently authored
        against) the flow's own summary.
      * TestPropagationIsTheOnlyEdit — angle: seam. Pipes the REAL
        `gpt.generate()` producer's on-disk output into the REAL consumer —
        a fresh read of index.json — twice: once before and once after
        editing ONLY the authoritative flow summary on disk, and asserts
        (a) the derived short form changes accordingly and (b) no
        unrelated flow file's bytes are touched by the regeneration.
      * TestSecondAuthoredDescriptionIsReported — angle: failure. A stored
        index artifact summary that diverges from a fresh derivation (i.e.
        a hand-typed "second authored description" was introduced) must be
        surfaced: `generate(check=True, ...)` must report the change
        (`changed=True`) AND log/print a message naming the journey and
        showing both the stale and the freshly-derived text — not merely a
        generic, unattributed "something changed" signal.
      * TestReachability — angle: reachability. Runs the REAL
        generate_product_truth.py CLI as a subprocess (its own, pre-existing
        entry point) against a complete store built from scratch in a
        tempdir, and asserts the new derivation is visible through that
        real process's own `--check` exit code — proving the derivation
        logic in the tests above is actually wired into `main()`, not only
        reachable by importing `gpt` and calling its functions directly.

    completion_manifest.reachability_entry_point_answer:
      result: resolved
      entry_point: "python docs/product-truth/scripts/generate_product_truth.py
        --check --quiet (CLI via subprocess, main() guarded by
        if __name__ == '__main__':). This AC's own `## Test Requirements`
        entry for the reachability test carried the BO-2900g-4 unresolved
        sentinel (no surface_invoked was declared), so this entry point was
        resolved per Step 1 of the Reachability Entry-Point Resolution
        procedure: generate_product_truth.py is a CLI script under
        docs/product-truth/scripts/ with a main() guarded by
        `if __name__ == '__main__':` and argparse — category 1 (CLI script)
        applies directly; no further steps were needed."

    completion_manifest.cross_layer_seam_answer:
      result: covered
      producing_side: "generate_product_truth.py's generate()/write_index(),
        actually run (not mocked), writing index.json's derived
        artifacts[].summary field for a flow-type artifact from the flow's
        own on-disk summary."
      consuming_side: "a fresh read of the written index.json — the real
        consumer of the store's derived data — asserting its own observable
        content (the artifact's summary text) changes when, and only when,
        the authoritative flow summary it was derived from changes on disk,
        with no other flow's file bytes touched."
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"

# The scripts directory is not on the default path; add it so we can import,
# mirroring unit_tests/product_truth/test_uxp_700c_1.py's convention for this
# same docs/product-truth/scripts location.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402

_CLI_PATH = _SCRIPTS_DIR / "generate_product_truth.py"

# The measured real-world worst case (docs/acceptance-criteria/ux-prototyping/
# UXP-700-truthful-project-record/UXP-700e-2.yaml's own `notes`): the longest
# authoritative flow summary observed in this store is 938 characters, against
# a stored index copy of 89-218 characters. Used here as a representative
# fixture length rather than a convenient short one.
_LONG_SUMMARY_A = (
    "When a ticket is dispatched, the architect reviews the blast radius and "
    "classifies the change before any code is written, then a test-writer "
    "produces failing tests that pin the acceptance criteria before a coder "
    "touches production code, then a coder makes those tests pass without "
    "widening or narrowing any contract a consumer already depends on, then "
    "the change moves through scope validation, review, the acceptance-"
    "criteria fulfillment gate and documentation verification before it is "
    "committed and, where applicable, opened as a pull request, with every "
    "phase's handoff to the next recorded in the ticket's own sign-off "
    "history so the chain of custody is never in doubt."
)
_LONG_SUMMARY_B = (
    "When a customer wants to buy a plant, they browse the catalog, add the "
    "plant to their cart, review the cart contents against the live catalog "
    "price and stock, provide payment and shipping details, and place the "
    "order, which reserves stock, charges payment, and schedules a shipment "
    "notification the customer can later look up by order number."
)
_STALE_HAND_TYPED_SUMMARY_A = "A short, independently hand-typed blurb about the ticket pipeline."
_STALE_HAND_TYPED_SUMMARY_B = "A short, independently hand-typed blurb about buying a plant."


# --------------------------------------------------------------------------- #
# Fixture builders (mirrors unit_tests/product_truth/test_uxp_700c_1.py's
# _base_flow / _write_flow / _write_json conventions for this same store
# shape).
# --------------------------------------------------------------------------- #
def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _flow(flow_id: str, summary: str) -> dict:
    component = flow_id.split("/", 1)[0]
    return {
        "id": flow_id,
        "component": component,
        "name": flow_id,
        "summary": summary,
        "kind": "user",
        "source": "mock",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": [
            {"id": "only-step", "label": "only-step", "human": "the actor does the one thing", "order": 1}
        ],
        "branches": [],
    }


def _flow_path(store_root: Path, flow_id: str) -> Path:
    component, name = flow_id.split("/", 1)
    return store_root / "flows" / component / f"{name}.flow.json"


def _write_flow(store_root: Path, flow: dict) -> None:
    _write_json(_flow_path(store_root, flow["id"]), flow)


def _artifact(flow_id: str, stale_summary: str) -> dict:
    component = flow_id.split("/", 1)[0]
    return {
        "id": flow_id,
        "type": "flow",
        "component": component,
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "summary": stale_summary,
    }


def _build_store(store_root: Path, ac_root: Path, flows: list, artifacts: list) -> None:
    """Materialize a minimal-but-complete product-truth store: real on-disk
    flow files (the authoritative descriptions) plus an index.json whose
    artifacts[] carries a SEPARATELY HAND-TYPED short summary for each flow —
    i.e. today's live duplication defect, reproduced on purpose as the
    starting fixture state every test below regenerates away from.
    """
    (store_root / "mock-data").mkdir(parents=True, exist_ok=True)
    (store_root / "mockups").mkdir(parents=True, exist_ok=True)
    ac_root.mkdir(parents=True, exist_ok=True)
    for flow in flows:
        _write_flow(store_root, flow)
    _write_json(
        store_root / "index.json",
        {
            "artifacts": artifacts,
            "entity_registry": [],
            "by_component": {},
            "by_entity": {},
            "by_flow": {},
            "by_ac": {},
        },
    )


def _run_generate(store_root: Path, ac_root: Path, check: bool = False, run_date: str = "2026-01-01") -> bool:
    """Run the REAL gpt.generate() against a fixture store, redirecting the
    module-level STORE/AC_STORE (mirrors test_uxp_700c_1.py's TestCheckPointersSeam
    and unit_tests/test_generate_product_truth_idempotency.py's _run_generate).
    """
    original_store, original_ac_store = gpt.STORE, gpt.AC_STORE
    gpt.STORE, gpt.AC_STORE = store_root, ac_root
    try:
        return gpt.generate(check=check, run_date=run_date)
    finally:
        gpt.STORE, gpt.AC_STORE = original_store, original_ac_store


def _artifact_summary(index: dict, flow_id: str) -> str:
    for artifact in index["artifacts"]:
        if artifact["id"] == flow_id:
            return artifact["summary"]
    raise AssertionError(f"no artifacts[] entry found for {flow_id!r} in index.json")


class TestDerivedFromAuthoritative(unittest.TestCase):
    """Criterion: the index short form is computed from the journey's own
    (authoritative) summary — not an independently authored value."""

    def test_shorter_form_is_produced_from_the_authoritative_description(self):
        # covers: UXP-700e-2
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            store_root = tmp / "docs" / "product-truth"
            ac_root = tmp / "docs" / "acceptance-criteria"
            flow = _flow("fixture-product/how-it-is-built", _LONG_SUMMARY_A)
            _build_store(store_root, ac_root, [flow], [_artifact(flow["id"], _STALE_HAND_TYPED_SUMMARY_A)])

            _run_generate(store_root, ac_root)

            index = _read_json(store_root / "index.json")
            derived = _artifact_summary(index, flow["id"])

        self.assertNotEqual(
            derived,
            _STALE_HAND_TYPED_SUMMARY_A,
            "the independently hand-typed stale summary must be overwritten by a value "
            "computed from the flow's own summary, not preserved as a second authored text",
        )
        self.assertLess(
            len(derived),
            len(_LONG_SUMMARY_A),
            "the derived form must be a SHORTER form of the authoritative description",
        )
        self.assertTrue(
            _LONG_SUMMARY_A.startswith(derived[:20]),
            "the derived short form must be computed from the authoritative flow summary text "
            f"itself (expected it to start with a prefix of {_LONG_SUMMARY_A[:20]!r}, got "
            f"{derived!r})",
        )


class TestPropagationIsTheOnlyEdit(unittest.TestCase):
    """Seam: pipe the REAL generate() producer's on-disk output into the REAL
    consumer (a fresh read of index.json), before and after editing ONLY the
    authoritative description, and assert nothing else was touched."""

    def test_changing_the_authoritative_description_changes_every_shorter_form(self):
        # covers: UXP-700e-2
        # angle: seam
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            store_root = tmp / "docs" / "product-truth"
            ac_root = tmp / "docs" / "acceptance-criteria"
            flow_a = _flow("fixture-product/how-it-is-built", _LONG_SUMMARY_A)
            flow_b = _flow("fixture-product/buys-a-plant", _LONG_SUMMARY_B)
            _build_store(
                store_root,
                ac_root,
                [flow_a, flow_b],
                [
                    _artifact(flow_a["id"], _STALE_HAND_TYPED_SUMMARY_A),
                    _artifact(flow_b["id"], _STALE_HAND_TYPED_SUMMARY_B),
                ],
            )

            _run_generate(store_root, ac_root)
            index_before = _read_json(store_root / "index.json")
            derived_a_before = _artifact_summary(index_before, flow_a["id"])
            derived_b_before = _artifact_summary(index_before, flow_b["id"])
            flow_b_bytes_before = _flow_path(store_root, flow_b["id"]).read_bytes()

            # Edit ONLY the authoritative description of journey A — no other
            # field, no other file.
            edited_summary_a = _LONG_SUMMARY_A + " EDITED FOR THE PROPAGATION TEST."
            flow_a["summary"] = edited_summary_a
            _write_flow(store_root, flow_a)

            _run_generate(store_root, ac_root)
            index_after = _read_json(store_root / "index.json")
            derived_a_after = _artifact_summary(index_after, flow_a["id"])
            derived_b_after = _artifact_summary(index_after, flow_b["id"])
            flow_b_bytes_after = _flow_path(store_root, flow_b["id"]).read_bytes()

        self.assertNotEqual(
            derived_a_after,
            derived_a_before,
            "editing journey A's authoritative description must change EVERY place the "
            "shorter form appears — the index short form for A did not change",
        )
        self.assertTrue(
            edited_summary_a.startswith(derived_a_after[:20]),
            "the changed short form must derive from the NEW authoritative text, not a "
            f"stale cached value (got {derived_a_after!r})",
        )
        self.assertEqual(
            derived_b_before,
            derived_b_after,
            "journey B's authoritative description was not touched, so its derived short "
            "form must not change — 'no other edit'",
        )
        self.assertEqual(
            flow_b_bytes_before,
            flow_b_bytes_after,
            "regenerating after editing ONLY journey A's description must not rewrite "
            "journey B's flow file at all — 'no other edit'",
        )


class TestSecondAuthoredDescriptionIsReported(unittest.TestCase):
    """Failure: a stored short form that diverges from a fresh derivation (a
    hand-typed second authored description) must be reported, naming the
    journey and showing both the stale and the derived text — not merely
    silently detected as generic 'something changed'."""

    def test_a_second_authored_description_is_reported(self):
        # covers: UXP-700e-2
        # angle: failure
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            store_root = tmp / "docs" / "product-truth"
            ac_root = tmp / "docs" / "acceptance-criteria"
            flow = _flow("fixture-product/how-it-is-built", _LONG_SUMMARY_A)
            _build_store(store_root, ac_root, [flow], [_artifact(flow["id"], _STALE_HAND_TYPED_SUMMARY_A)])

            original_store, original_ac_store = gpt.STORE, gpt.AC_STORE
            gpt.STORE, gpt.AC_STORE = store_root, ac_root
            try:
                with self.assertLogs(level="WARNING") as captured:
                    changed = gpt.generate(check=True, run_date="2026-01-01")
            finally:
                gpt.STORE, gpt.AC_STORE = original_store, original_ac_store

        self.assertTrue(
            changed,
            "a stored short form that diverges from a fresh derivation must be reported "
            "as a pending change by --check",
        )
        combined_log = "\n".join(captured.output)
        self.assertIn(
            flow["id"],
            combined_log,
            "the report must NAME the journey holding the second authored description",
        )
        self.assertIn(
            _STALE_HAND_TYPED_SUMMARY_A,
            combined_log,
            "the report must show the stale, separately authored text — one of the 'both "
            "places its description is held'",
        )
        self.assertIn(
            _LONG_SUMMARY_A[:20],
            combined_log,
            "the report must show the freshly derived text (or enough of it to identify it) "
            "— the other of the 'both places its description is held'",
        )


def _build_minimal_cli_store(tmp: Path) -> Path:
    """Build a complete product-truth store inside tmp — the real script
    copied verbatim, one flow authored with a long authoritative summary, and
    a derived index.json whose artifacts[] entry carries a stale, separately
    hand-typed short summary (today's live duplication defect). Returns the
    path to the copied generate_product_truth.py CLI entry point.

    The store is normalized with ONE real `gpt.generate()` run so that every
    OTHER derived field (by_flow, node impl_status/impl_asof, impl_summary) is
    already fully self-consistent — meaning the ONLY thing left for `--check`
    to find stale is the summary duplication this AC targets; a `--check`
    failure the CLI already reports for an unrelated, pre-existing reason
    (e.g. an empty `by_flow` needing its first-ever build) would make this
    reachability test pass for the wrong reason.

    FIXTURE ORDER (repaired 2026-09-09, #EPIC-TruthfulProjectRecord/41): the
    hand-typed summary is written back AFTER that normalization run, not
    before. As first authored this helper seeded the stale summary first and
    relied on the note that "today's generate_product_truth.py never touches
    artifacts[].summary at all" to carry it through the run untouched. That
    was true only of the PRE-FIX generator: the moment UXP-700e-2's derivation
    is wired in, the normalization run derives the summary and erases the very
    duplication the assertion below then looks for, so the test could never
    pass once its own subject was implemented. Re-introducing the stale value
    after normalization preserves this docstring's stated intent exactly — one
    self-consistent store whose single remaining drift is the hand-typed
    description — without weakening the assertion.
    """
    pt_root = tmp / "docs" / "product-truth"
    shutil.copytree(_SCRIPTS_DIR, pt_root / "scripts")
    (pt_root / "flows").mkdir(parents=True)
    (pt_root / "mock-data").mkdir(parents=True)
    (pt_root / "mockups").mkdir(parents=True)

    ac_dir = tmp / "docs" / "acceptance-criteria"
    ac_dir.mkdir(parents=True)

    flow = _flow("fixture-product/how-it-is-built", _LONG_SUMMARY_A)
    _write_json(pt_root / "flows" / "fixture-product" / "how-it-is-built.flow.json", flow)

    index = {
        "artifacts": [_artifact(flow["id"], _STALE_HAND_TYPED_SUMMARY_A)],
        "entity_registry": [],
        "by_component": {},
        "by_entity": {},
        "by_flow": {},
        "by_ac": {},
    }
    _write_json(pt_root / "index.json", index)

    _run_generate(pt_root, ac_dir, check=False, run_date="2026-01-01")

    # Re-introduce the separately hand-typed description the normalization run
    # just derived away — see FIXTURE ORDER above.
    normalized = _read_json(pt_root / "index.json")
    for artifact in normalized["artifacts"]:
        if artifact["id"] == flow["id"]:
            artifact["summary"] = _STALE_HAND_TYPED_SUMMARY_A
    _write_json(pt_root / "index.json", normalized)

    return pt_root / "scripts" / "generate_product_truth.py"


class TestReachability(unittest.TestCase):
    """Reachability: the derivation must be provable through
    generate_product_truth.py's real CLI entry point, not merely through a
    direct call to gpt.generate()."""

    def test_uxp_700e_2_reachable_from_entry_point(self):
        # covers: UXP-700e-2
        # angle: reachability
        #
        # REQUIRED: invoke the production entry point as a subprocess and
        # assert the new derivation behaviour actually occurs via the real
        # process's own exit code — not by importing gpt and calling
        # generate()/write_index() directly (that is what the classes above
        # do; this test proves those functions are actually wired into
        # main()'s --check path).
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            cli_path = _build_minimal_cli_store(tmp)

            result = subprocess.run(
                [sys.executable, str(cli_path), "--check", "--quiet"],
                capture_output=True,
                text=True,
                timeout=30,
            )

        self.assertEqual(
            result.returncode,
            1,
            "a store whose index artifact summary was hand-typed independently of the "
            "flow's own (938-character-class) summary must be reported stale by the real "
            "CLI's --check mode once the derivation is wired in; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
