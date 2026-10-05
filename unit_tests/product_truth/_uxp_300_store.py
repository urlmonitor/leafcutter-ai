"""Authentic, dependency-closed stores for UXP-300 behavioral tests.

Keep every real product-truth artifact and the real tools. Only the AC corpus
is reduced: copy records named by authored nodes or confirmation state, plus
explicit negative-control records and the component registry. The separate
deployed-store test retains the complete AC corpus.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PT_SOURCE = REPO_ROOT / "docs" / "product-truth"
AC_SOURCE = REPO_ROOT / "docs" / "acceptance-criteria"


def select_ac_paths(source: Path, required: set[str]) -> dict[str, Path]:
    """Resolve repository AC filenames, then verify selected YAML identities.

    Do not parse thousands of unrelated records to construct a small fixture.
    A missing/ambiguous filename, mismatched record ID, or escaping path is an
    error, never a reason to discard a flow pointer. This helper does not
    audit the identities of unselected records; full-corpus checks stay intact.
    """
    candidates: dict[str, list[Path]] = {}
    for path in source.rglob("*.yaml"):
        if path.stem in required:
            candidates.setdefault(path.stem, []).append(path)
    selected: dict[str, Path] = {}
    for ac_id in sorted(required):
        matches = candidates.get(ac_id, [])
        if len(matches) != 1:
            raise ValueError(f"AC {ac_id}: expected one file, found {len(matches)}")
        path = matches[0]
        if not path.resolve().is_relative_to(source.resolve()):
            raise ValueError(f"AC {ac_id}: file escapes the AC fixture source")
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("id") != ac_id:
            raise ValueError(f"AC {ac_id}: filename and YAML identity disagree")
        selected[ac_id] = path
    return selected


def copy_contract_dependencies(store: Path) -> None:
    """Keep real contract models and declared schema/receipt dependencies in the fixture.

    This copies source bytes, never substitutes validation models or drops flows.
    Model imports need the kernel, integration and knowledge source packages;
    schemas and receipts remain limited to paths declared by the real artifacts.
    """
    paths: set[str] = set()
    has_models = False
    for path in (store / "flows").rglob("*.flow.json"):
        flow = json.loads(path.read_text(encoding="utf-8"))
        for definition in flow.get("contract_definitions", {}).values():
            has_models = has_models or "model" in definition
            if "schema" in definition:
                paths.add(definition["schema"])
        for node in flow.get("steps", []) + flow.get("branches", []):
            for example in node.get("io_contracts", {}).get("examples", []):
                if "source" in example:
                    paths.add(example["source"]["path"])
    destination_root = store.parent.parent.resolve()
    if has_models:
        for package in ("kernel", "integrations", "knowledge"):
            paths.update(source.relative_to(REPO_ROOT).as_posix()
                         for source in (REPO_ROOT / package).rglob("*.py")
                         if "__pycache__" not in source.parts)
    for relative in sorted(paths):
        source = (REPO_ROOT / relative).resolve()
        destination = (destination_root / relative).resolve()
        if not source.is_relative_to(REPO_ROOT.resolve()) or not destination.is_relative_to(destination_root):
            raise ValueError(f"contract dependency escapes fixture: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def copy_bounded_store(docs: Path, *, extra_ac_ids: tuple[str, ...] = ()) -> Path:
    """Copy real bytes without changing authored pointers or derived fields."""
    store = docs / "product-truth"
    shutil.copytree(PT_SOURCE, store, ignore=shutil.ignore_patterns("__pycache__"))
    copy_contract_dependencies(store)
    required = set(extra_ac_ids)
    for path in (store / "flows").rglob("*.flow.json"):
        flow = json.loads(path.read_text(encoding="utf-8"))
        for node in flow.get("steps", []) + flow.get("branches", []):
            required.update(node.get("implements", []))
        required.update(flow.get("confirmed", {}).get("state", {}))
    selected = select_ac_paths(AC_SOURCE, required)
    ac_dest = docs / "acceptance-criteria"
    ac_dest.mkdir(parents=True)
    shutil.copy2(AC_SOURCE / "index.yaml", ac_dest / "index.yaml")
    for path in selected.values():
        destination = ac_dest / path.relative_to(AC_SOURCE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    return store


def ac_path(store: Path, ac_id: str) -> Path:
    return select_ac_paths(store.parent / "acceptance-criteria", {ac_id})[ac_id]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def replace_backlinks(store: Path, ac_id: str, entries: list[dict]) -> Path:
    """Mutate a real AC through the YAML serializer, never an invented blob."""
    path = ac_path(store, ac_id)
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    record["product_truth"] = entries
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def write_duplicate_plant(store: Path, component: str = "ux-prototyping") -> Path:
    """Clone the real Plant dataset with its real example-product identity."""
    original = json.loads((store / "mock-data/fern-and-fig/catalog.mock.json").read_text(encoding="utf-8"))
    keys = ("id", "component", "example_product", "status", "readiness", "realization", "entities")
    payload = {key: value for key, value in original.items() if key in keys}
    payload.update(id="fern-and-fig/catalog-dup", component=component, readiness="draft")
    payload["entities"] = {"Plant": original["entities"]["Plant"]}
    destination = store / "mock-data/fern-and-fig/catalog-dup.mock.json"
    write_json(destination, payload)
    return destination
