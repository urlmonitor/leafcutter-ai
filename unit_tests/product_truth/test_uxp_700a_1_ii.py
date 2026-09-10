"""
MODULE: test_uxp_700a_1_ii
GOAL: Pin that re-running the tooling's installer over a project whose
    product-truth record is already populated (>=1 journey, >=1 example
    dataset, >=1 screen, all project-authored) never replaces what is already
    there: every pre-existing artifact stays byte-identical, and the store
    index still lists exactly the artifact ids it listed before the reinstall.
BUSINESS CONTEXT: UXP-700a-1 (still work_status: todo in this repo at
    authoring time -- see docs/acceptance-criteria/ux-prototyping/
    UXP-700-truthful-project-record/UXP-700a-1.yaml) is the AC that
    introduces the scaffold-writer this record's overwrite guard constrains:
    "a record is written into that project with a place for each artifact
    type ... each of those places present and empty ... a store index is
    written that declares zero artifacts". UXP-700a-1-ii's own "Expects
    From" contract names that exact scaffold-writing behaviour as its
    prerequisite. It has not landed yet -- confirmed directly against this
    repo's own code (DIRECTLY OBSERVED below) -- so the guard this AC
    describes has nothing to guard today. Per architect-review's sign-off on
    this ticket (04_TICKET-20260909-UXP-700a-1-ii.md, 2026-09-09 15:35):
    "test-writer/python-coder on this ticket will need either (a)
    UXP-700a-1 to land first, or (b) to build the minimal scaffold-write
    path as part of this ticket's own scope, reusing the existing
    _should_overwrite() / _write() guard rather than inventing a new one."
    This file specifies the minimal contract for (b): the "Product-truth
    tooling" phase (build_product_truth() in scripts/build_phases.py,
    dispatched from build.py's scaffold_phases list -- "Phases that write
    user-curated scaffolds at target_root (write-if-absent)") must, on an
    install into a project with NO existing docs/product-truth/{flows,
    mock-data,mockups} record, create those three directories and an
    index.json declaring zero artifacts (this is UXP-700a-1's own contract,
    used here only as an unavoidable precondition -- without it there is no
    scaffold write to guard, and a content-preservation assertion against a
    phase that never touches this data at all would pass VACUOUSLY today,
    which is exactly the phantom-green failure mode this project's own
    CLAUDE.md ("Real-artifact behavioral spot-check") exists to catch).

    DIRECTLY OBSERVED (2026-09-09, this repo, this ticket's test-writer
    pass): running `python scripts/build.py --target-dir <fresh tmp>
    --self-description-enforcement warning` (PYTHONIOENCODING=utf-8 to dodge
    an unrelated Windows console cp1252 crash in an unrelated later phase)
    exits 0 and its "Product-truth tooling" phase deploys ONLY
    docs/product-truth/{scripts,schemas}/ -- no flows/, mock-data/,
    mockups/ or index.json are created. build_product_truth()'s own
    docstring confirms this is deliberate today: "the project-authored
    product-truth DATA (flows, mock-data, mockups, index.json) is never
    touched by this phase." That is the gap UXP-700a-1 exists to close, and
    the reason every test below is red until it does.

ARCHITECTURE / THE CONTRACT THIS TEST FILE SPECIFIES:
    setUpClass runs the REAL CLI entry point (`python scripts/build.py
    --target-dir <tmp>`, subprocess, the tooling's actual installer) TWICE
    against the same fresh target directory:
      1. First install into a project with no product-truth record at all.
         Asserts (this is the precondition the guard needs, and is where
         today's red comes from) that docs/product-truth/flows/,
         mock-data/, mockups/ and index.json now exist.
      2. Between the two installs, this file hand-authors one real,
         schema-valid journey (flow), one example dataset (mock-data) and
         one screen (mockup) into the freshly-scaffolded directories --
         standing in for a project author's own work after adopting the
         tooling -- and appends their ids to index.json's "artifacts" list,
         producing the "at least one journey, one example dataset and one
         screen, all authored by that project" state the AC's Given clause
         names. Byte snapshots of all four files are taken at this point.
      3. Second install ("the tooling is installed into the same project a
         second time") into the SAME target directory.
    Individual test methods assert against the class-level snapshots so the
    (~13s each) real installer subprocess only runs twice for the whole
    file, not once per test.

    completion_manifest.cross_layer_seam_answer:
      result: not_applicable
      reason: "This AC constrains a single deploy phase's own idempotency
        (build.py's installer writing into a project's docs/product-truth/
        tree) -- there is no second, independent producer/consumer pair
        whose real output needs to be piped through a real consumer; the
        installer IS both the thing under test and its own boundary. The
        reachability test below already exercises the real CLI entry point
        end to end rather than importing build_product_truth() directly."

    completion_manifest.reachability_entry_point_answer:
      result: resolved
      entry_point: "python scripts/build.py --target-dir <dir> --self-description-enforcement warning (CLI via subprocess) -- the tooling's real installer, dispatching build_product_truth() from its scaffold_phases list"
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"

_SUBPROCESS_TIMEOUT_SECONDS = 120

# Windows dev boxes default the child interpreter's stdout to the console
# codepage (cp1252), which crashes on the checkmark glyphs build.py prints
# in later, unrelated phases (build_doc_index -> build_colors.success()).
# Forcing UTF-8 here keeps this file's red state attributable to the
# product-truth scaffold gap this AC actually describes, not to an
# unrelated console-encoding crash.
_SUBPROCESS_ENV = dict(os.environ)
_SUBPROCESS_ENV["PYTHONIOENCODING"] = "utf-8"

_COMPONENT = "acme-widgets"


def _run_build(target_dir: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL production installer as a subprocess -- the tooling's
    own CLI entry point -- exactly as an adopter running it a second time
    would.
    """
    return subprocess.run(
        [
            sys.executable,
            str(_BUILD_PY),
            "--target-dir",
            str(target_dir),
            "--self-description-enforcement",
            "warning",
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        env=_SUBPROCESS_ENV,
    )


def _flow_fixture() -> dict:
    """A minimal, schema-valid journey (flow.schema.json required fields)."""
    return {
        "id": f"{_COMPONENT}/customer-journey",
        "component": _COMPONENT,
        "name": "Customer journey",
        "summary": "Fixture journey authored by the project after adopting the tooling.",
        "kind": "user",
        "source": "real",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": ["Widget"],
        "steps": [
            {
                "id": "browse",
                "label": "Browse widgets",
                "human": "Look at the widget catalog.",
                "order": 1,
                "impl_status": "not_started",
            }
        ],
    }


def _mock_data_fixture() -> dict:
    """A minimal, schema-valid example dataset (mock-data.schema.json)."""
    return {
        "id": f"{_COMPONENT}/catalog",
        "component": _COMPONENT,
        "status": "active",
        "readiness": "draft",
        "entities": {
            "Widget": {
                "fields": {"id": "string", "name": "string", "stock": "integer"},
                "records": [
                    {"id": "widget-1", "name": "Widget One", "stock": 4},
                ],
            }
        },
    }


def _mockup_fixture() -> dict:
    """A minimal, schema-valid screen (mockup.schema.json required fields)."""
    return {
        "id": f"{_COMPONENT}/widget-detail",
        "component": _COMPONENT,
        "screen": "widget-detail",
        "title": "Widget detail",
        "summary": "Fixture screen authored by the project after adopting the tooling.",
        "entities": ["Widget"],
        "source": "mock",
        "renders": None,
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "provenance": [
            {"action": "authored", "by": "test-writer fixture", "date": "2026-09-09"}
        ],
    }


class TestReinstallOverPopulatedRecord(unittest.TestCase):
    """UXP-700a-1-ii: reinstalling the tooling over a populated product-truth
    record must not replace what is already there.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.target = Path(cls._tmp.name)
        cls.pt_root = cls.target / "docs" / "product-truth"

        # --- Install 1: a project with no product-truth record at all. ---
        cls.first_install = _run_build(cls.target)

        cls._flow_path = cls.pt_root / "flows" / _COMPONENT / "customer-journey.flow.json"
        cls._mock_path = cls.pt_root / "mock-data" / _COMPONENT / "catalog.mock.json"
        cls._mockup_path = cls.pt_root / "mockups" / _COMPONENT / "widget-detail.mockup.json"
        cls._index_path = cls.pt_root / "index.json"

        cls._precondition_error = None
        for label, path in (
            ("flows/", cls.pt_root / "flows"),
            ("mock-data/", cls.pt_root / "mock-data"),
            ("mockups/", cls.pt_root / "mockups"),
            ("index.json", cls._index_path),
        ):
            if not path.exists():
                cls._precondition_error = (
                    f"UXP-700a-1's scaffold-writer has not landed: after a fresh "
                    f"install, docs/product-truth/{label} does not exist at "
                    f"{path}. This is the still-open dependency architect-review "
                    f"named on this ticket (UXP-700a-1-ii expects_from UXP-700a-1). "
                    f"first_install returncode={cls.first_install.returncode}\n"
                    f"stdout tail={cls.first_install.stdout[-1500:]}\n"
                    f"stderr tail={cls.first_install.stderr[-1500:]}"
                )
                break

        if cls._precondition_error is not None:
            # Nothing further can be exercised without the scaffold existing.
            # Leave snapshots undefined; each test method fails loudly below
            # rather than raising an opaque AttributeError.
            return

        # --- Author one journey, one example dataset, one screen, plus the
        # index entries that declare them -- "authored by that project". ---
        cls._flow_path.parent.mkdir(parents=True, exist_ok=True)
        cls._mock_path.parent.mkdir(parents=True, exist_ok=True)
        cls._mockup_path.parent.mkdir(parents=True, exist_ok=True)

        cls._flow_path.write_text(
            json.dumps(_flow_fixture(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        cls._mock_path.write_text(
            json.dumps(_mock_data_fixture(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        cls._mockup_path.write_text(
            json.dumps(_mockup_fixture(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        index = json.loads(cls._index_path.read_text(encoding="utf-8"))
        index.setdefault("artifacts", [])
        index["artifacts"].extend(
            [
                {
                    "id": f"{_COMPONENT}/customer-journey",
                    "type": "flow",
                    "path": f"flows/{_COMPONENT}/customer-journey.flow.json",
                },
                {
                    "id": f"{_COMPONENT}/catalog",
                    "type": "mock-data",
                    "path": f"mock-data/{_COMPONENT}/catalog.mock.json",
                },
                {
                    "id": f"{_COMPONENT}/widget-detail",
                    "type": "mockup",
                    "path": f"mockups/{_COMPONENT}/widget-detail.mockup.json",
                },
            ]
        )
        cls._index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        # --- Snapshot every pre-existing artifact BEFORE the second install. ---
        cls._before_bytes = {
            p: p.read_bytes()
            for p in (cls._flow_path, cls._mock_path, cls._mockup_path, cls._index_path)
        }
        cls._before_artifact_ids = sorted(
            a["id"] for a in json.loads(cls._index_path.read_text(encoding="utf-8"))["artifacts"]
        )

        # --- Install 2: the tooling installed into the SAME, now-populated
        # project a second time. ---
        cls.second_install = _run_build(cls.target)

        cls._after_bytes = {
            p: (p.read_bytes() if p.exists() else None)
            for p in (cls._flow_path, cls._mock_path, cls._mockup_path, cls._index_path)
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _require_precondition(self) -> None:
        if self._precondition_error is not None:
            self.fail(self._precondition_error)

    def test_reinstall_leaves_existing_artifacts_byte_identical(self):
        # covers: UXP-700a-1-ii
        # angle: real_artifact
        """AC-1: every pre-existing artifact has the same content after the
        install as before it. Also the direct evidence for AC-3 (any
        scaffold the install would otherwise write is left untouched
        wherever a file of that name already exists): the flow/mock-data/
        mockup files below are exactly the kind of per-artifact file the
        scaffold-writer would create for an EMPTY project -- here they
        already exist by that name, so the second install must leave them
        alone.
        """
        self._require_precondition()
        self.assertEqual(
            self.second_install.returncode,
            0,
            "the second install must exit 0; "
            f"stdout={self.second_install.stdout[-1500:]!r} "
            f"stderr={self.second_install.stderr[-1500:]!r}",
        )
        for path in (self._flow_path, self._mock_path, self._mockup_path):
            self.assertEqual(
                self._after_bytes[path],
                self._before_bytes[path],
                f"reinstall changed the content of a pre-existing artifact: {path}",
            )

    def test_reinstall_does_not_reset_the_store_index(self):
        # covers: UXP-700a-1-ii
        # angle: real_artifact
        """AC-2: the store index still lists exactly the artifacts it listed
        before the install -- not reset to the zero-artifact scaffold a
        fresh install would declare.
        """
        self._require_precondition()
        after_index = json.loads(self._after_bytes[self._index_path].decode("utf-8"))
        after_ids = sorted(a["id"] for a in after_index["artifacts"])
        self.assertEqual(
            after_ids,
            self._before_artifact_ids,
            "the store index's artifact id list changed across the reinstall "
            f"(before={self._before_artifact_ids!r} after={after_ids!r})",
        )
        self.assertEqual(
            len(after_ids),
            3,
            "expected exactly the 3 project-authored artifacts (1 journey, "
            "1 example dataset, 1 screen); an index reset to zero artifacts "
            "would also fail the id-list equality assertion above, but this "
            "makes the failure mode explicit.",
        )

    def test_uxp_700a_1_ii_reachable_from_entry_point(self):
        # covers: UXP-700a-1-ii
        # angle: reachability
        """REQUIRED reachability test: the second install is invoked through
        the tooling's real CLI entry point (`python scripts/build.py
        --target-dir <dir>`, subprocess) -- not by importing
        build_product_truth() and calling it directly. Asserts both that
        the "Product-truth tooling" phase actually ran (its heading is
        printed to stdout by the real phase-runner loop in
        scripts/build.py's _run_phases()) AND that its result is consumed:
        the on-disk state of the previously-authored artifacts after this
        exact subprocess call is what the other two tests assert on, so a
        change here is what would turn them red.
        """
        self._require_precondition()
        self.assertEqual(
            self.second_install.returncode,
            0,
            "python scripts/build.py --target-dir <dir> must exit 0 on a "
            "reinstall over a populated product-truth record; "
            f"stdout={self.second_install.stdout[-1500:]!r} "
            f"stderr={self.second_install.stderr[-1500:]!r}",
        )
        self.assertIn(
            "Product-truth tooling",
            self.second_install.stdout,
            "the real installer's phase-runner loop must have dispatched the "
            "'Product-truth tooling' phase (build_product_truth()) for this "
            "to be a reachability proof rather than a direct function call; "
            f"stdout={self.second_install.stdout[-2000:]!r}",
        )
        # The behaviour's result is consumed, not merely printed: the files
        # on disk after this real subprocess call must still exist and must
        # still be the project-authored artifacts (not vanished, not reset).
        for path in (self._flow_path, self._mock_path, self._mockup_path, self._index_path):
            self.assertIsNotNone(
                self._after_bytes[path],
                f"{path} no longer exists after the real installer's second run",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
