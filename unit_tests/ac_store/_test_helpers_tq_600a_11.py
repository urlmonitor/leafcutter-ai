"""Helpers for unit_tests/ac_store/test_tq_600a_11.py (TQ-600a-11).

Holds the mechanical C-parser call-site deriver, the counting walk-arm runner
and the tmp-root builder so the test file keeps only its tests, tags and
docstrings. No test lives here; nothing here reads the declared set while
deriving (the derivation must stay independent of it).
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import time
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
AC_STORE_DIR = SCRIPTS_DIR / "ac_store"
STORE_ROOT = REPO_ROOT / "docs" / "acceptance-criteria"

# The DECLARED set of C-backed-parser call sites (the AC's admission test).
# Each is (repo-relative POSIX path, enclosing function; "<module>" at module
# scope). This is the short list that needs maintaining -- the ~81 files that
# name the pure-Python parser are the DEFAULT and are deliberately not listed
# or asserted on anywhere.
DECLARED_C_PARSER_SITES = frozenset(
    {
        ("scripts/generate_agent_cards.py", "_scan_ac_assignments"),
        ("scripts/generate_agent_cards.py", "_scan_all_ac_assignments"),
        ("scripts/render_effective_prompt.py", "<module>"),
    }
)

_ACCESSOR_MODULE = "yaml_safe_loader"
_ACCESSOR_DEFINITION = "scripts/ac_store/yaml_safe_loader.py"
_ACCESSOR_NAMES = frozenset({"get_safe_yaml_loader", "load_yaml_text", "load_yaml_file"})
_SOURCE_ROOTS = (REPO_ROOT / "scripts", REPO_ROOT / "templates")

# Modules that decide BLOCK or PASS (admission part 4). A C-parser site in any
# of these is a defect by the AC's own text.
_DECISION_POINT_BASENAMES = frozenset(
    {"validate_ac_schema.py", "validate_ac.py", "done_proof.py"}
)


def is_decision_point(rel: str) -> bool:
    parts = rel.split("/")
    return (
        "commit_guardian" in parts
        or parts[-1] in _DECISION_POINT_BASENAMES
        or parts[-1].startswith("check_")
    )


class _ResolutionFinder(ast.NodeVisitor):
    """Collect the scope of every place a file resolves the C parser."""

    def __init__(self, accessor_names: set[str], module_aliases: set[str]):
        self._names = accessor_names
        self._modules = module_aliases
        self._scope: list[str] = []
        self.hits: list[str] = []

    def _scope_name(self) -> str:
        return ".".join(self._scope) or "<module>"

    def _visit_scoped(self, node):
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _visit_scoped

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if (node.module or "").split(".")[-1] == "yaml" and any(
            a.name == "CSafeLoader" for a in node.names
        ):
            self.hits.append(self._scope_name())

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "CSafeLoader":
            self.hits.append(self._scope_name())
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in self._names:
            self.hits.append(self._scope_name())
        elif (
            isinstance(func, ast.Attribute)
            and func.attr in _ACCESSOR_NAMES
            and isinstance(func.value, ast.Name)
            and func.value.id in self._modules
        ):
            self.hits.append(self._scope_name())
        elif isinstance(func, ast.Name) and func.id == "getattr":
            # The inline idiom: getattr(yaml, "CSafeLoader", yaml.SafeLoader).
            if any(
                isinstance(a, ast.Constant) and a.value == "CSafeLoader"
                for a in node.args[1:]
            ):
                self.hits.append(self._scope_name())
        self.generic_visit(node)


def derive_c_parser_resolutions() -> set[tuple[str, str]]:
    """Mechanically derive every (file, scope) that resolves the C parser.

    Counts BOTH the shared accessor (import + call, including aliased imports)
    and the inline getattr(yaml, "CSafeLoader", ...) idiom, per the AC: copying
    the inline idiom must not be a way round the seam. Never reads the declared
    set. Comments and docstrings are ignored (AST, not text). Fail-closed: a
    file that mentions either marker but cannot be parsed is reported as an
    undeclared "<unparseable>" site instead of being skipped.
    """
    found: set[tuple[str, str]] = set()
    for root in _SOURCE_ROOTS:
        for path in root.rglob("*.py"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel == _ACCESSOR_DEFINITION:
                continue  # the accessor's own definition is not a call site
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # Cheap pre-filter: both statically-detectable shapes contain one
            # of these substrings, so a file without either cannot resolve it.
            if "CSafeLoader" not in text and _ACCESSOR_MODULE not in text:
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                found.add((rel, "<unparseable>"))
                continue
            names: set[str] = set()
            modules: set[str] = set()
            imports_accessor = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] == _ACCESSOR_MODULE:
                    imports_accessor = True
                    names.update(a.asname or a.name for a in node.names)
                elif isinstance(node, ast.Import):
                    for a in node.names:
                        if a.name.split(".")[-1] == _ACCESSOR_MODULE:
                            imports_accessor = True
                            modules.add(a.asname or a.name)
            finder = _ResolutionFinder(names, modules)
            finder.visit(tree)
            hits = set(finder.hits)
            if imports_accessor and not hits:
                hits.add("<import>")  # imported but used in a shape we cannot see
            found.update((rel, scope) for scope in hits)
    return found


def yaml_files_on_disk() -> int:
    """Files the card generator's walk would parse: every .yaml/.yml, index.yaml included."""
    return sum(
        1
        for _dp, _dirs, names in os.walk(STORE_ROOT)
        for name in names
        if name.endswith((".yaml", ".yml"))
    )


def real_store_paths() -> list[Path]:
    return sorted(
        p
        for p in (*STORE_ROOT.rglob("*.yaml"), *STORE_ROOT.rglob("*.yml"))
        if p.is_file() and p.name != "index.yaml"
    )


def run_walk_arm(gac, resolver):
    """Time one ``_scan_all_ac_assignments`` walk with *resolver* as its loader.

    Returns (output, parsed_file_count, seconds). The resolver is wrapped so
    each call -- one per parse inside the walk -- is counted.
    """
    parsed = []

    def counting_resolver():
        parsed.append(1)
        return resolver()

    with mock.patch.object(gac, "get_safe_yaml_loader", counting_resolver):
        start = time.perf_counter()
        output = gac._scan_all_ac_assignments(REPO_ROOT)
        elapsed = time.perf_counter() - start
    return output, len(parsed), elapsed


def build_card_phase_root(root: Path, agent: str, record: Path) -> None:
    """Lay out a minimal tmp target root: one agent template, a registry made
    by json.dumps, and the REAL AC record *record* copied verbatim."""
    (root / "templates" / "agents").mkdir(parents=True)
    (root / "templates" / "agents" / f"{agent}.md").write_text(
        f"---\nname: {agent}\ndescription: reachability stub\n---\nbody\n",
        encoding="utf-8",
    )
    (root / "config").mkdir()
    (root / "config" / "agent_registry.json").write_text(
        json.dumps([{"id": agent}]), encoding="utf-8"
    )
    store_dir = root / "docs" / "acceptance-criteria" / "testing-quality"
    store_dir.mkdir(parents=True)
    shutil.copyfile(record, store_dir / record.name)
