r"""
MODULE: test_uxp_700c_3_i
GOAL: Pin the cross-platform verdict contract for the product-truth store: the
    store-relative paths generate_product_truth.py writes into index.json are
    identifiers, not filesystem paths, and must render identically on every
    platform.
BUSINESS CONTEXT: load_flows() built each path with str(path.relative_to(STORE)),
    which renders with os.sep. The committed index.json was generated on a POSIX
    host and holds 'flows/a/b.flow.json'; a Windows rebuild produced
    'flows\a\b.flow.json', so _check_derived_indexes reported drift against an
    unmodified, correct store. Because check-product-truth-validate fires on
    (^docs/product-truth/|^docs/acceptance-criteria/.*\.yaml$), a Windows
    contributor could not commit ANY acceptance-criteria YAML — the only escape
    being --no-verify, which disables every other gate at the same time. The
    write direction was worse: a Windows run in write mode rewrote index.json
    with backslashes, breaking every POSIX contributor and CI, so the file
    flipped separator on each platform's turn. See KI-BP-20260907-0812.
ARCHITECTURE: Asserts on STRING CONTENT, never on a pathlib round-trip. A
    round-trip comparison would pass vacuously on POSIX — the platform that
    cannot reproduce the bug — and so would never have caught it. Two levels of
    guard: a synthetic tempdir store proves the producer emits POSIX separators
    on the host running the suite, and a check of the committed index.json
    proves no Windows-written path has already landed in the repository.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402

_BACKSLASH = chr(92)


class TestFlowPathsArePlatformIndependent(unittest.TestCase):
    """The producer must emit POSIX separators regardless of host platform."""

    def test_load_flows_emits_no_backslash_on_any_platform(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            nested = store / "flows" / "demo-product" / "sub"
            nested.mkdir(parents=True)
            (nested / "a-journey.flow.json").write_text(
                json.dumps({"id": "demo-product/a-journey"}), encoding="utf-8"
            )

            original_store = gpt.STORE
            gpt.STORE = store
            try:
                _flows, paths = gpt.load_flows()
            finally:
                gpt.STORE = original_store

        emitted = paths["demo-product/a-journey"]
        self.assertNotIn(
            _BACKSLASH,
            emitted,
            f"store-relative path must use POSIX separators, got {emitted!r}",
        )
        self.assertEqual(emitted, "flows/demo-product/sub/a-journey.flow.json")

    def test_committed_index_holds_no_windows_written_path(self) -> None:
        index_path = _REPO_ROOT / "docs" / "product-truth" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))

        offenders = [
            (flow_id, entry.get("path", ""))
            for flow_id, entry in index.get("by_flow", {}).items()
            if _BACKSLASH in entry.get("path", "")
        ]
        self.assertEqual(
            offenders,
            [],
            "index.json contains platform-separator paths — a Windows write has "
            f"landed in the repository: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
