"""UXP-300 behavioral proofs using real product-truth tools and artifacts.

Behavioral cases retain every authored truth artifact but copy only referenced
ACs and an unreferenced sentinel. The deployed positive integration deliberately
keeps the complete corpus. Every producer/consumer invocation is a fresh CLI
process; fixture mutations use the real JSON/YAML serializers.

Fixture repair classification: test_drift. The original unbounded fixture
timed out, lacked example_product, and its backlink-named test proved only
duplicates. New backlink tests also expose a production YAML-corruption bug;
the format regression protects that separate repair. Bounded cases retain the
90-second deadline; the unpruned deployed corpus has a separate bounded limit.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from unit_tests.product_truth._uxp_300_store import (
    AC_SOURCE, PT_SOURCE, REPO_ROOT, copy_bounded_store, copy_contract_dependencies,
    replace_backlinks, select_ac_paths, write_duplicate_plant, write_json,
)

_SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_SUBPROCESS_TIMEOUT_SECONDS = 90
# The real deployed corpus took 92.970s on 2026-10-02; its correctness
# contract has no 90s latency requirement. Keep all data and assertions.
_FULL_STORE_TIMEOUT_SECONDS = 180
_EXPECTED_DUP_SUBSTR = (
    "entity 'Plant' already has a canonical mock-data artifact "
    "for component 'ux-prototyping': 'fern-and-fig/catalog'; "
    "'fern-and-fig/catalog-dup' is a duplicate"
)


def _run_script(
    store: Path, name: str, *args: str, timeout: int = _SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(store / "scripts" / name), *args],
        capture_output=True, text=True, timeout=timeout,
    )


def _run_validator(
    store: Path, *, timeout: int = _SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    return _run_script(store, "validate_product_truth.py", timeout=timeout)


def _run_generator(store: Path, *args: str) -> subprocess.CompletedProcess:
    return _run_script(store, "generate_product_truth.py", *args)


def _output(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout + proc.stderr


def _failures(proc: subprocess.CompletedProcess) -> list[str]:
    return [line.removeprefix("FAIL: ") for line in _output(proc).splitlines() if line.startswith("FAIL: ")]


def _outcome(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestUxp300BoundedBehavior(unittest.TestCase):
    """Each negative starts with a real, independently valid private store."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = copy_bounded_store(Path(self._tmp.name) / "docs", extra_ac_ids=("UXP-300",))
        self.baseline = _run_validator(self.store)
        self.assertEqual(self.baseline.returncode, 0, _output(self.baseline))
        self.assertEqual(_failures(self.baseline), [])
        self.assertEqual(_outcome(self.baseline)["outcome"], "checked-and-sound")
        self.assertGreater(_outcome(self.baseline)["resolved_pointers"], 0)

    def generate(self, *args: str) -> None:
        proc = _run_generator(self.store, *args)
        self.assertEqual(proc.returncode, 0, _output(proc))

    def assert_only_duplicate(self, proc: subprocess.CompletedProcess) -> None:
        self.assertEqual(proc.returncode, 1, _output(proc))
        self.assertEqual(_failures(proc), [_EXPECTED_DUP_SUBSTR], _output(proc))
        self.assertEqual(_outcome(proc)["outcome"], "failed")

    def test_dependency_closed_store_passes_the_real_validator(self) -> None:
        # covers: UXP-300
        # angle: real_artifact
        outcome = _outcome(self.baseline)
        expected_flows = len(list((PT_SOURCE / "flows").rglob("*.flow.json")))
        self.assertGreater(expected_flows, 0)
        self.assertEqual(outcome["examined"], expected_flows)
        self.assertEqual(outcome["unresolvable_pointers"], 0)
        self.assertEqual(outcome["empty_types"], [])

    def test_every_registered_artifact_resolves_under_a_declared_store_directory(self) -> None:
        # covers: UXP-300
        # angle: real_artifact
        path = self.store / "index.json"
        index = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(index["artifacts"])
        artifact = index["artifacts"][0]
        artifact["path"] = "not-a-declared-directory/bogus.json"
        write_json(path, index)
        proc = _run_validator(self.store)
        expected = (
            f"[index] artifact '{artifact['id']}' path '{artifact['path']}' "
            "is outside the declared store directories (flows/, mock-data/, mockups/)"
        )
        self.assertEqual(proc.returncode, 1, _output(proc))
        self.assertEqual(_failures(proc), [expected], _output(proc))

    def test_one_canonical_dataset_per_entity_per_component(self) -> None:
        # covers: UXP-300
        # angle: real_artifact
        write_duplicate_plant(self.store)
        self.assert_only_duplicate(_run_validator(self.store))

    def test_duplicate_is_rejected_after_the_real_generator_writes_its_index(self) -> None:
        # covers: UXP-300
        # angle: seam
        write_duplicate_plant(self.store)
        index_path = self.store / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        # A no-op producer must fail even though the original copied index
        # already contained Plant and the consumer also scans source mocks.
        index["by_entity"] = {}
        write_json(index_path, index)
        poisoned_bytes = index_path.read_bytes()
        self.generate()
        self.assertNotEqual(index_path.read_bytes(), poisoned_bytes)
        written = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertIn("Plant", written["by_entity"])
        self.assertIn("ux-prototyping", written["by_entity"]["Plant"]["canonical_mock_data"])
        self.assert_only_duplicate(_run_validator(self.store))

    def test_same_entity_in_a_different_component_is_allowed(self) -> None:
        # covers: UXP-300
        # angle: boundary
        index = json.loads((self.store / "index.json").read_text(encoding="utf-8"))
        component = next(name for name in sorted(index["by_component"]) if name != "ux-prototyping")
        write_duplicate_plant(self.store, component=component)
        self.generate()
        proc = _run_validator(self.store)
        self.assertEqual(proc.returncode, 0, _output(proc))
        self.assertEqual(_failures(proc), [])
        self.assertEqual(_outcome(proc)["outcome"], "checked-and-sound")
        index = json.loads((self.store / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["by_entity"]["Plant"]["canonical_mock_data"]["ux-prototyping"], "fern-and-fig/catalog")
        self.assertEqual(index["by_entity"]["Plant"]["canonical_mock_data"][component], "fern-and-fig/catalog-dup")

    def test_flow_to_ac_is_authored_and_the_reverse_edge_is_derived(self) -> None:
        # covers: UXP-300
        # angle: seam
        flow_path = self.store / "flows/fern-and-fig/customer-buys-a-plant.flow.json"
        flow = json.loads(flow_path.read_text(encoding="utf-8"))
        browse = next(step for step in flow["steps"] if step["id"] == "browse")
        index = json.loads((self.store / "index.json").read_text(encoding="utf-8"))
        self.assertNotIn("UXP-300", index["by_ac"])
        self.assertEqual(browse["implements"], ["UXP-210a"])
        # The existing on-disk backlink is the authentic expected shape for
        # this SAME node; only its new derivation date changes for the new AC.
        expected = [dict(index["by_ac"]["UXP-210a"][0], asof="2026-10-02")]
        browse["implements"].append("UXP-300")
        write_json(flow_path, flow)
        target = replace_backlinks(self.store, "UXP-300", [])
        self.generate("--now", "2026-10-02")
        written_ac = yaml.safe_load(target.read_text(encoding="utf-8"))
        written_index = json.loads((self.store / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(written_ac["product_truth"], expected)
        self.assertEqual(written_index["by_ac"]["UXP-300"], expected)
        written_flow = json.loads(flow_path.read_text(encoding="utf-8"))
        self.assertEqual(next(step for step in written_flow["steps"] if step["id"] == "browse")["implements"],
                         ["UXP-210a", "UXP-300"])
        proc = _run_validator(self.store)
        self.assertEqual(proc.returncode, 0, _output(proc))
        self.assertEqual(_failures(proc), [])

    def test_unsupported_backlink_is_reported_and_removed_by_the_generator(self) -> None:
        # covers: UXP-300
        # angle: seam
        index_path = self.store / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertNotIn("UXP-300", index["by_ac"])
        # Keep a real unreferenced AC: a references-only fixture would never
        # exercise removal of a hand-authored reverse link.
        unsupported = [dict(index["by_ac"]["UXP-210a"][0])]
        target = replace_backlinks(self.store, "UXP-300", unsupported)
        proc = _run_validator(self.store)
        self.assertEqual(proc.returncode, 1, _output(proc))
        self.assertEqual(_failures(proc), [
            "[product_truth] AC 'UXP-300': has a product_truth block but no flow node references it"
        ], _output(proc))
        self.generate()
        self.assertNotIn("product_truth", yaml.safe_load(target.read_text(encoding="utf-8")))
        self.assertNotIn("UXP-300", json.loads(index_path.read_text(encoding="utf-8"))["by_ac"])
        proc = _run_validator(self.store)
        self.assertEqual(proc.returncode, 0, _output(proc))
        self.assertEqual(_failures(proc), [])

    def test_uxp_300_reachable_from_entry_point(self) -> None:
        # covers: UXP-300
        # angle: reachability
        # Both real CLIs' exit statuses are consumed. Baseline success in
        # setUp and an exact single finding prevent an unrelated failure
        # from masquerading as a working duplicate gate.
        write_duplicate_plant(self.store)
        self.assert_only_duplicate(_run_validator(self.store))


class TestBoundedFixtureIdentity(unittest.TestCase):
    """A fixture must reject unresolved identities rather than prune pointers."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.source = Path(self._tmp.name)
        self.original = select_ac_paths(AC_SOURCE, {"UXP-300"})["UXP-300"]

    def test_missing_ac_is_not_silently_omitted(self) -> None:
        # covers: UXP-300
        # angle: failure
        with self.assertRaisesRegex(ValueError, "UXP-300: expected one file, found 0"):
            select_ac_paths(self.source, {"UXP-300"})

    def test_duplicate_filenames_are_rejected(self) -> None:
        # covers: UXP-300
        # angle: failure
        for name in ("first", "second"):
            destination = self.source / name
            destination.mkdir()
            shutil.copy2(self.original, destination / self.original.name)
        with self.assertRaisesRegex(ValueError, "UXP-300: expected one file, found 2"):
            select_ac_paths(self.source, {"UXP-300"})

    def test_selected_yaml_identity_must_match_its_filename(self) -> None:
        # covers: UXP-300
        # angle: failure
        shutil.copy2(self.original, self.source / "UXP-301.yaml")
        with self.assertRaisesRegex(ValueError, "UXP-301: filename and YAML identity disagree"):
            select_ac_paths(self.source, {"UXP-301"})


class TestBacklinkYamlBoundaries(unittest.TestCase):
    """Real serializer variants must survive the surgical YAML-text edit."""

    def setUp(self) -> None:
        scripts = PT_SOURCE / "scripts"
        spec = importlib.util.spec_from_file_location("uxp300_yaml_generator", scripts / "generate_product_truth.py")
        self.generator = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(scripts))
        try:
            spec.loader.exec_module(self.generator)
        finally:
            sys.path.remove(str(scripts))
        original = select_ac_paths(AC_SOURCE, {"UXP-300"})["UXP-300"]
        self.prefix = original.read_text(encoding="utf-8")
        self.assertNotIn("product_truth", yaml.safe_load(self.prefix))
        index = json.loads((PT_SOURCE / "index.json").read_text(encoding="utf-8"))
        self.entries = [dict(index["by_ac"]["UXP-210a"][0])]

    def test_removal_and_replacement_preserve_yaml_comments_neighbors_and_idempotency(self) -> None:
        # covers: UXP-300
        # angle: boundary
        for style in ("indentless", "indented"):
            if style == "indentless":
                block = yaml.safe_dump({"product_truth": self.entries}, sort_keys=False)
            else:
                block = self.generator.serialize_product_truth(self.entries)
            for placement in ("eof", "before_metadata"):
                suffix = "" if placement == "eof" else (
                    "# Following metadata must survive verbatim.\n"
                    + yaml.safe_dump({"fixture_sentinel": {"keep": "unchanged"}}, sort_keys=False)
                )
                authored = self.prefix + block + suffix
                # Assert authenticity and validity before the operation;
                # a malformed input cannot manufacture the corruption bug.
                original = yaml.safe_load(authored)
                self.assertEqual(original["product_truth"], self.entries)
                for operation in ("remove", "replace"):
                    with self.subTest(style=style, placement=placement, operation=operation):
                        desired = [] if operation == "remove" else [dict(self.entries[0], node="replacement-node")]
                        result = self.generator.apply_product_truth_text(authored, desired)
                        parsed = yaml.safe_load(result)
                        expected = dict(original)
                        expected.pop("product_truth")
                        if desired:
                            expected["product_truth"] = desired
                        self.assertEqual(parsed, expected)
                        self.assertTrue(result.startswith(self.prefix))
                        if suffix:
                            self.assertIn(suffix, result)
                        self.assertEqual(self.generator.apply_product_truth_text(result, desired), result)

    def test_comments_inside_a_sequence_do_not_end_the_backlink_block(self) -> None:
        # covers: UXP-300
        # angle: boundary
        entries = self.entries + [dict(self.entries[0], node="second-node")]
        suffix = "# Unrelated scalar and list metadata.\n" + yaml.safe_dump(
            {"fixture_scalar": "keep", "fixture_list": ["alpha", "beta"]}, sort_keys=False
        )
        for style in ("indentless", "indented"):
            block = (yaml.safe_dump({"product_truth": entries}, sort_keys=False) if style == "indentless"
                     else self.generator.serialize_product_truth(entries))
            lines = block.splitlines(keepends=True)
            # Only comments are inserted by hand; all YAML data comes from
            # the actual serializer. Both comment positions are valid YAML.
            block = "".join(("# Backlink comment.\n" if line.lstrip().startswith("- flow:") else "") + line
                            for line in lines)
            authored = self.prefix + block + suffix
            original = yaml.safe_load(authored)
            self.assertEqual(original["product_truth"], entries)
            for operation in ("remove", "replace"):
                with self.subTest(style=style, operation=operation):
                    desired = [] if operation == "remove" else self.entries
                    result = self.generator.apply_product_truth_text(authored, desired)
                    expected = dict(original)
                    expected.pop("product_truth")
                    if desired:
                        expected["product_truth"] = desired
                    self.assertEqual(yaml.safe_load(result), expected)
                    self.assertTrue(result.startswith(self.prefix))
                    self.assertIn(suffix, result)
                    self.assertEqual(result.count("# Backlink comment.\n"), 2)
                    self.assertEqual(self.generator.apply_product_truth_text(result, desired), result)


class TestTheStorePassesItsOwnValidator(unittest.TestCase):
    """Exercise the actual deployment, including one unpruned corpus run."""

    def setUp(self) -> None:
        from build_phases import build_product_truth

        self._build_product_truth = build_product_truth
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _deploy(self) -> Path:
        target = Path(self._tmp.name) / self.id().rsplit(".", 1)[-1]
        target.mkdir(parents=True)
        written = self._build_product_truth(target, {"output_root": ".leafcutter"}, dry_run=False, force=True)
        self.assertGreater(written, 0)
        return target / "docs" / "product-truth"

    def test_the_store_passes_its_own_validator(self) -> None:
        # covers: UXP-300
        # angle: deployed
        """Full-corpus integration: no dependency-closure filtering here."""
        store = self._deploy()
        shutil.copytree(AC_SOURCE, store.parent / "acceptance-criteria")
        for name in ("flows", "mock-data", "mockups", "classifier", "evals", "index.json"):
            src, dst = PT_SOURCE / name, store / name
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        copy_contract_dependencies(store)
        expected_flows = len(list((PT_SOURCE / "flows").rglob("*.flow.json")))
        expected_mocks = len(list((PT_SOURCE / "mock-data").rglob("*.mock.json")))
        expected_acs = len([path for path in AC_SOURCE.rglob("*.yaml") if path.name != "index.yaml"])
        self.assertGreater(expected_flows, 0)
        self.assertGreater(expected_acs, 0)
        proc = _run_validator(store, timeout=_FULL_STORE_TIMEOUT_SECONDS)
        self.assertEqual(proc.returncode, 0, _output(proc))
        result = _outcome(proc)
        self.assertEqual(result["outcome"], "checked-and-sound")
        self.assertEqual(result["examined"], expected_flows)
        self.assertEqual(result["examined_by_check"]["example-data-shape"], expected_mocks)
        self.assertEqual(result["examined_by_check"]["product-truth-links"], expected_acs)

    def test_deployed_validator_degrades_informatively_on_an_empty_store(self) -> None:
        # covers: UXP-300
        # angle: deployed
        # Current installer scaffolds a valid empty record. UXP-700b-1 owns
        # its truthful "nothing-examined" outcome; emptiness is not a crash
        # or a duplicate-data validation error.
        proc = _run_validator(self._deploy())
        self.assertNotIn("Traceback (most recent call last):", _output(proc))
        self.assertEqual(proc.returncode, 0, _output(proc))
        result = _outcome(proc)
        self.assertEqual(result["outcome"], "nothing-examined")
        self.assertEqual(result["examined"], 0)
        self.assertEqual(set(result["empty_types"]), {"flows", "mock-data", "mockups"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
