"""
MODULE: test_uxp_700e_2_i
GOAL: Pin UXP-700e-2-i -- the derived short form of a journey's description, at
    its real worst case: bounded, reproducible, visibly shortened, and never
    edited in place without being told where the real description lives.
BUSINESS CONTEXT: UXP-700e-2 made the index's per-journey summary a derivation
    of the journey's own description instead of a second hand-typed copy. This
    L3 pins the shape of that derivation where it matters most: the longest
    description in the store (how-acs-are-built, 938 characters). A short form
    that runs over the space it is shown in, changes between runs, or ends
    mid-sentence with no marker would each mislead a reader into taking it for
    the whole description. And a reader who edits the short form directly has
    edited the one copy that is regenerated away -- so the report must send
    them to the journey file, not merely say "stale".
ARCHITECTURE: Import-based tests call generate_product_truth's real
    derive_artifact_summary() and generate() against a tempdir store; the
    reachability test runs the REAL generate_product_truth.py CLI in --check
    mode as a subprocess, with the whole scripts/ directory copied the way
    build.py deploys it (the generator imports sibling modules).

    DESIGN DECISION (2026-09-14, user): the short form is the description's
    OPENING, cut at a word boundary, followed by a trailing ellipsis. #773 had
    cut from both ends ("opening ... closing") so an edit to the last sentence
    would still change the short form; that could not satisfy this AC's "ends
    in a way that shows a reader it was shortened". UXP-700e-2's "changing the
    authoritative description changes every place the shorter form appears,
    with no other edit" is a propagation guarantee -- the short form is always
    re-derived, never authored -- and still holds in full.
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
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402

_ELLIPSIS = "…"
_FLOW_ID = "fixture-product/how-it-is-built"
_FLOW_REL = "flows/fixture-product/how-it-is-built.flow.json"


def _description_of_length(n: int) -> str:
    """Return deterministic prose of exactly *n* characters, ending on a word."""
    words = (
        "When a ticket is dispatched the architect reviews the blast radius and "
        "classifies the change before any code is written then a test writer "
        "produces failing tests that pin the acceptance criteria before a coder "
        "touches production code"
    ).split()
    out: list[str] = []
    i = 0
    while len(" ".join(out)) < n:
        out.append(words[i % len(words)])
        i += 1
    text = " ".join(out)[:n]
    return text[:-1] + "x" if text.endswith(" ") else text


_LONGEST = _description_of_length(938)


def _flow(summary: str) -> dict:
    return {
        "id": _FLOW_ID,
        "component": "fixture-product",
        "name": _FLOW_ID,
        "summary": summary,
        "kind": "user",
        "source": "mock",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": [{"id": "only-step", "label": "only-step", "human": "the actor does the one thing", "order": 1}],
        "branches": [],
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_store(store_root: Path, ac_root: Path) -> None:
    """A store holding one journey with the worst-case description, and an index
    already regenerated from it, so the only thing a test changes is its subject."""
    (store_root / "mock-data").mkdir(parents=True, exist_ok=True)
    (store_root / "mockups").mkdir(parents=True, exist_ok=True)
    ac_root.mkdir(parents=True, exist_ok=True)
    _write_json(store_root / _FLOW_REL, _flow(_LONGEST))
    _write_json(
        store_root / "index.json",
        {
            "artifacts": [{"id": _FLOW_ID, "type": "flow", "component": "fixture-product",
                           "status": "active", "readiness": "draft", "version": 1}],
            "entity_registry": [], "by_component": {}, "by_entity": {}, "by_flow": {}, "by_ac": {},
        },
    )


def _run_generate(store_root: Path, ac_root: Path, check: bool) -> bool:
    original_store, original_ac_store = gpt.STORE, gpt.AC_STORE
    gpt.STORE, gpt.AC_STORE = store_root, ac_root
    try:
        return gpt.generate(check=check, run_date="2026-01-01")
    finally:
        gpt.STORE, gpt.AC_STORE = original_store, original_ac_store


def _hand_edit_short_form(store_root: Path, text: str) -> None:
    index = _read_json(store_root / "index.json")
    for artifact in index["artifacts"]:
        if artifact["id"] == _FLOW_ID:
            artifact["summary"] = text
    _write_json(store_root / "index.json", index)


class TestDerivedShortFormRespectsTheDeclaredBound(unittest.TestCase):
    def test_derived_short_form_respects_the_declared_bound(self) -> None:
        # covers: UXP-700e-2-i
        # angle: boundary
        self.assertEqual(len(_LONGEST), 938, "fixture must be the real worst case")
        derived = gpt.derive_artifact_summary(_LONGEST)

        self.assertLessEqual(
            len(derived), gpt._ARTIFACT_SUMMARY_LENGTH,
            f"the short form must fit the place it is shown ({gpt._ARTIFACT_SUMMARY_LENGTH}); "
            f"got {len(derived)}: {derived!r}",
        )
        self.assertTrue(
            derived.endswith(_ELLIPSIS),
            f"a shortened form must END with a marker so nobody reads it as the whole "
            f"description; got {derived!r}",
        )
        visible = derived[: -len(_ELLIPSIS)].rstrip()
        self.assertTrue(
            _LONGEST.startswith(visible),
            f"the visible text must be the description's own opening, not rewritten; got {visible!r}",
        )


class TestDerivationIsReproducible(unittest.TestCase):
    def test_derivation_is_reproducible(self) -> None:
        # covers: UXP-700e-2-i
        # angle: criterion
        self.assertEqual(gpt.derive_artifact_summary(_LONGEST), gpt.derive_artifact_summary(_LONGEST))

        short = "A description that already fits."
        self.assertEqual(
            gpt.derive_artifact_summary(short), short,
            "a description that fits is its own short form -- no marker, nothing to mislead a reader",
        )


class TestEditingTheDerivedFormInPlaceIsReported(unittest.TestCase):
    def test_editing_the_derived_form_in_place_is_reported(self) -> None:
        # covers: UXP-700e-2-i
        # angle: failure
        with tempfile.TemporaryDirectory() as tmp_name:
            store_root = Path(tmp_name) / "docs" / "product-truth"
            ac_root = Path(tmp_name) / "docs" / "acceptance-criteria"
            _build_store(store_root, ac_root)
            _run_generate(store_root, ac_root, check=False)
            _hand_edit_short_form(store_root, "A tidier summary somebody typed straight into the index.")

            with self.assertLogs(level="WARNING") as captured:
                changed = _run_generate(store_root, ac_root, check=True)

        self.assertTrue(changed, "an in-place edit to the derived form must be reported as pending by --check")
        log = "\n".join(captured.output)
        self.assertIn(_FLOW_ID, log, "the report must name the journey")
        self.assertIn(
            _FLOW_REL, log,
            f"the report must name the authoritative description's own location as the place "
            f"to edit instead; got:\n{log}",
        )
        self.assertIn("summary", log, "the report must name the field that holds the authoritative description")


class TestUxp700e2iReachableFromEntryPoint(unittest.TestCase):
    def test_uxp_700e_2_i_reachable_from_entry_point(self) -> None:
        # covers: UXP-700e-2-i
        # angle: reachability
        # Entry point: the generator's own CLI in --check mode, run as a subprocess --
        # the same command the product-truth drift hook runs.
        with tempfile.TemporaryDirectory() as tmp_name:
            store_root = Path(tmp_name) / "docs" / "product-truth"
            ac_root = Path(tmp_name) / "docs" / "acceptance-criteria"
            shutil.copytree(_SCRIPTS_DIR, store_root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            _build_store(store_root, ac_root)
            _run_generate(store_root, ac_root, check=False)
            _hand_edit_short_form(store_root, "A tidier summary somebody typed straight into the index.")

            result = subprocess.run(
                [sys.executable, str(store_root / "scripts" / "generate_product_truth.py"), "--check"],
                capture_output=True, text=True, timeout=60,
            )

        self.assertEqual(
            result.returncode, 1,
            f"--check must fail on a hand-edited short form; stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            _FLOW_REL, result.stdout + result.stderr,
            "the real CLI's report must point the reader at the journey file to edit instead",
        )


if __name__ == "__main__":
    unittest.main()
