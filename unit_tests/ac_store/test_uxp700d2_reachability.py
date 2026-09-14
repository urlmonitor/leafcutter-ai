"""
MODULE: test_uxp700d2_reachability
COVERS: UXP-700d-2 -- "the example product's criteria never appear in the store of
    work, the scan states how many it set aside, and they stay readable."

GOAL: The reachability proof this AC's ticket promised and never had. Its
    siblings pin the behaviour by importing scan_ac_store's helpers directly
    (angles: criterion, real_artifact, boundary, seam); none of them proves the
    behaviour survives the production entry point a human or a workflow actually
    runs. check-proof-promise-claim caught exactly that gap -- a ticket at
    status: done promising a reachability proof that no test claimed -- which is
    the same phantom-done this epic exists to remove, found in the epic's own
    bookkeeping.

REACHABILITY ENTRY-POINT RESOLUTION: the AC authored no test_spec, so the entry
    point is resolved here per the standard order. (1) CLI script -- YES:
    scripts/ac_store/scan_ac_store.py has a main() guarded by
    `if __name__ == "__main__":` with argparse, and is what the ticket-prioritizer
    and the /build-ac flow invoke to ask "what is ready to work on". Resolved to
    `python scripts/ac_store/scan_ac_store.py --json --ac-root <dir>` run as a
    SUBPROCESS. Importing _is_example_content and asserting on it does NOT
    satisfy this angle -- that is what the sibling tests already do, and it
    cannot show the exclusion is actually wired into the command anyone runs.

ARCHITECTURE: Builds a throwaway AC store in a tempdir holding both the
    project's own criteria and an example product's, then reads the real
    process's own stdout. Every assertion is made against that JSON, not against
    an imported function's return value.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI = _REPO_ROOT / "scripts" / "ac_store" / "scan_ac_store.py"

_EXAMPLE_PRODUCT = "fern-and-fig"
_OWN_IDS = ("ZZZ-100a", "ZZZ-100b")
_EXAMPLE_IDS = ("ZZZ-900a", "ZZZ-900b", "ZZZ-900c")


def _write_ac(root: Path, ac_id: str, *, product: str | None) -> Path:
    """Write one schema-shaped leaf AC, optionally marked as example content."""
    record = {
        "id": ac_id,
        "title": f"{ac_id} title",
        "level": "L3",
        "status": "active",
        "req_status": "approved",
        "work_status": "todo",
        "readiness": "approved",
        "priority": "medium",
        "criteria": f"Given {ac_id}, When it is scanned, Then it behaves.",
        "component": "ux-prototyping",
        "covered_by": [],
        "implemented_by": [],
        "depends_on": [],
    }
    if product is not None:
        record["product"] = product
    path = root / f"{ac_id}.yaml"
    lines = []
    for key, value in record.items():
        if isinstance(value, list):
            lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {json.dumps(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestUxp700d2ReachableFromEntryPoint(unittest.TestCase):
    """Reachability: the real CLI, as a subprocess, over a real store on disk."""

    def test_uxp700d2_reachable_from_entry_point(self) -> None:
        # covers: UXP-700d-2
        # angle: reachability
        with tempfile.TemporaryDirectory() as tmp_name:
            ac_root = Path(tmp_name) / "acceptance-criteria" / "zz-fixture"
            ac_root.mkdir(parents=True)
            for ac_id in _OWN_IDS:
                _write_ac(ac_root, ac_id, product=None)
            example_paths = {
                ac_id: _write_ac(ac_root, ac_id, product=_EXAMPLE_PRODUCT)
                for ac_id in _EXAMPLE_IDS
            }

            result = subprocess.run(
                [
                    sys.executable,
                    str(_CLI),
                    "--json",
                    "--ac-root",
                    str(ac_root.parent),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            self.assertEqual(
                result.returncode,
                0,
                f"the real CLI must complete; stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            payload = json.loads(result.stdout)

            listed = {
                str(entry.get("ac_id"))
                for key in ("ready", "blocked")
                for entry in payload.get(key, [])
                if isinstance(entry, dict)
            }

            # AC clause 1: none of the example product's criteria appears in
            # either set -- asserted on what the PROCESS printed.
            leaked = sorted(listed & set(_EXAMPLE_IDS))
            self.assertEqual(
                leaked,
                [],
                f"the example product's criteria must not be offered as work; the real "
                f"CLI listed {leaked}. Full payload: {payload!r}",
            )

            # The project's own criteria must still be offered -- otherwise the
            # exclusion above would pass just as well by listing nothing at all.
            self.assertEqual(
                sorted(listed & set(_OWN_IDS)),
                sorted(_OWN_IDS),
                f"the project's own criteria must still reach the store of work; got "
                f"{sorted(listed)!r}",
            )

            # AC clause 2: the scan STATES how many it set aside.
            self.assertEqual(
                payload.get("set_aside_count"),
                len(_EXAMPLE_IDS),
                f"the run must state how many criteria it set aside as example content; "
                f"payload={payload!r}",
            )

            # AC clause 3: set aside, not deleted -- they remain readable and
            # still describe the example product.
            for ac_id, path in example_paths.items():
                self.assertTrue(path.is_file(), f"{ac_id} must remain on disk, not be removed")
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    _EXAMPLE_PRODUCT,
                    text,
                    f"{ac_id} must still describe the example product after the scan",
                )


if __name__ == "__main__":
    unittest.main()
