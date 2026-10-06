"""MODULE: artifact_dependencies.py
GOAL: Build a bounded, dependency-complete Product Truth evaluation sandbox.
BUSINESS CONTEXT: Missing model or receipt inputs must never conceal invalid handoffs.
ARCHITECTURE: Copy declared data and statically resolved reviewed Python imports; no execution.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import sys
from pathlib import Path, PurePosixPath

STORE = "docs/product-truth"
PACKAGES = {"kernel", "integrations", "knowledge"}
SCHEMA_ROOTS = ("docs/product-truth/schemas/", "kernel/schemas/", "config/")
RECEIPT_ROOTS = ("docs/product-truth/", "reports/")
GAP_ROOTS = ("docs/product-truth/", "docs/analysis/")


def _private(name: str) -> bool:
    """Exclude environment files, VCS metadata and interpreter caches."""
    return name.startswith(".") or name == "__pycache__" or name.endswith((".pyc", ".pyo"))


def checked_path(root: Path, relative: str, allowed: tuple[str, ...] = ()) -> Path:
    """Resolve a literal relative path, rejecting traversal, links and private files."""
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError(f"invalid sandbox dependency path: {relative!r}")
    parts = PurePosixPath(relative).parts
    if PurePosixPath(relative).is_absolute() or ".." in parts or any(_private(p) for p in parts):
        raise ValueError(f"unsafe sandbox dependency path: {relative}")
    if allowed and not relative.startswith(allowed):
        raise ValueError(f"dependency is outside allowed roots: {relative}")
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError(f"linked sandbox dependency is not allowed: {relative}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"dependency escapes repository: {relative}")
    return path


def _copy_file(source: Path, destination: Path, relative: str, allowed: tuple[str, ...] = ()) -> None:
    """Copy one checked source file without widening its declared scope."""
    src = checked_path(source, relative, allowed)
    dst = checked_path(destination, relative)
    if not src.is_file():
        raise ValueError(f"missing sandbox dependency: {relative}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_directory(source: Path, destination: Path, relative: str) -> None:
    """Copy configured store files, checking directories before traversing them."""
    directory = checked_path(source, relative)
    if not directory.is_dir():
        raise ValueError(f"missing sandbox directory: {relative}")
    for current, directories, files in os.walk(directory, followlinks=False):
        directories[:] = [name for name in directories if not _private(name)]
        for name in directories:
            checked_path(source, (Path(current) / name).relative_to(source).as_posix())
        for name in files:
            if not _private(name):
                _copy_file(source, destination, (Path(current) / name).relative_to(source).as_posix())


def _read_json(path: Path) -> dict:
    """Read a required JSON object; callers wrap file and parse failures."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def _node_dependencies(node: dict) -> list[tuple[str, tuple[str, ...]]]:
    """Collect only receipts and planning sources named by the node."""
    io = node.get("io_contracts", {})
    references: list[tuple[str, tuple[str, ...]]] = [
        (e["source"]["path"], RECEIPT_ROOTS) for e in io.get("examples", []) if "source" in e]
    references.extend((gap["source"], GAP_ROOTS) for gap in io.get("missing_bindings", []))
    return references


def _flow_dependencies(store: Path) -> tuple[set[tuple[str, tuple[str, ...]]], set[str], bool]:
    """Discover declarations without importing or trusting authored model names."""
    references: set[tuple[str, tuple[str, ...]]] = set()
    ac_ids: set[str] = set()
    has_models = False
    for path in (store / "flows").rglob("*.flow.json"):
        flow = _read_json(path)
        for definition in flow.get("contract_definitions", {}).values():
            has_models = has_models or "model" in definition
            if "schema" in definition:
                references.add((definition["schema"], SCHEMA_ROOTS))
        for node in flow.get("steps", []) + flow.get("branches", []):
            references.update(_node_dependencies(node))
            ac_ids.update(node.get("implements", []))
        ac_ids.update(flow.get("confirmed", {}).get("state", {}))
    return references, ac_ids, has_models


def _module_paths(root: Path, module: str, *, required: bool) -> list[Path]:
    """Find local modules and package initializers, never third-party packages."""
    if module.split(".")[0] not in PACKAGES:
        return []
    base = root.joinpath(*module.split("."))
    found = next((p for p in (base.with_suffix(".py"), base / "__init__.py") if p.is_file()), None)
    if found is None:
        if required and not base.is_dir():
            raise ValueError(f"missing reviewed model import: {module}")
        return []
    paths = [found]
    paths.extend(root / parent / "__init__.py" for parent in found.relative_to(root).parents
                 if parent.parts and (root / parent / "__init__.py").is_file())
    return [checked_path(root, path.relative_to(root).as_posix()) for path in paths]


def _import_names(path: Path, root: Path, node: ast.Import | ast.ImportFrom) -> list[tuple[str, bool]]:
    """Resolve static import statements, including relative package imports."""
    if isinstance(node, ast.Import):
        return [(alias.name, True) for alias in node.names]
    module = node.module or ""
    if node.level:
        package = path.relative_to(root).parent.parts
        module = ".".join((*package[:len(package) - node.level + 1], module)).rstrip(".")
    return [(module, True), *((module + "." + alias.name, False) for alias in node.names if alias.name != "*")]


def _copy_model_imports(source: Path, destination: Path) -> None:
    """Copy the reviewed resolver's static local import closure as source bytes."""
    seed = checked_path(source, f"{STORE}/scripts/product_truth_contract_sources.py")
    pending, seen = [seed], set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for module, required in _import_names(path, source, node):
                    pending.extend(_module_paths(source, module, required=required))
    for path in sorted(seen - {seed}):
        _copy_file(source, destination, path.relative_to(source).as_posix())


def _copy_policy_marker(source: Path, destination: Path) -> None:
    """Preserve the existing capability-presence gate without copying its package."""
    policy = source / STORE / "scripts/product_truth_contract_policy.py"
    if not policy.is_file():
        return
    tree = ast.parse(policy.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CAPABILITY_MARKER" for t in node.targets):
            relative = ast.literal_eval(node.value)
            path = checked_path(source, relative, ("integrations/",))
            if path.is_file():
                _copy_file(source, destination, relative)


def _copy_acs(source: Path, destination: Path, required: set[str]) -> None:
    """Copy the component registry and exact referenced AC records, verifying identities."""
    ac_root = source / "docs/acceptance-criteria"
    index = "docs/acceptance-criteria/index.yaml"
    if (source / index).is_file() or required:
        _copy_file(source, destination, index)
    if not required:
        return
    import yaml

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ac_store"))
    from yaml_safe_loader import get_safe_yaml_loader

    candidates: dict[str, list[Path]] = {}
    for path in ac_root.rglob("*.yaml"):
        if path.stem in required:
            candidates.setdefault(path.stem, []).append(path)
    for ac_id in sorted(required):
        matches = candidates.get(ac_id, [])
        if len(matches) != 1:
            raise ValueError(f"AC {ac_id}: expected one source record, found {len(matches)}")
        relative = matches[0].relative_to(source).as_posix()
        path = checked_path(source, relative, ("docs/acceptance-criteria/",))
        record = yaml.load(path.read_text(encoding="utf-8"), Loader=get_safe_yaml_loader())
        if not isinstance(record, dict) or record.get("id") != ac_id:
            raise ValueError(f"AC {ac_id}: filename and record identity disagree")
        _copy_file(source, destination, relative)


def copy_sandbox_inputs(source: Path, destination: Path, copy_dirs: list[str]) -> None:
    """Copy configured inputs plus declared contract dependencies; raise on unavailable input.

    The harness wraps OSError/ValueError/ImportError as EvalDataError at this I/O boundary.
    No models are executed, no private neighbors or third-party modules are copied.
    """
    source = source.resolve()
    for relative in copy_dirs:
        _copy_directory(source, destination, relative)
    references, required, has_models = _flow_dependencies(destination / STORE)
    for relative, roots in sorted(references):
        _copy_file(source, destination, relative, roots)
    if has_models:
        _copy_model_imports(source, destination)
    _copy_policy_marker(source, destination)
    _copy_acs(source, destination, required)


# DECISION HISTORY
# ================================================================================
# - 2026-10-05 06:37 [python-coder]: Close eval dependencies without copying private neighbors. (#TICKETLESS reason=user-authorized-evaluation-repair)
