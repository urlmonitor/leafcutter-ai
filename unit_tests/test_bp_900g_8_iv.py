"""
MODULE: test_bp_900g_8_iv
GOAL: Pin BP-900g-8-iv: inside one guard pass, the closure guard walks each
    file's module tree once and builds each scope's name map once, and its
    closures and WARNING lines are identical to the unmemoised computation.
BUSINESS CONTEXT: BP-900g-8-i's per-build cache made the guard analyse each
    file once per pass, but one analysis still walked the tree six times (the
    parent annotation plus five detectors) and rebuilt the scope's assignments,
    including a whole-module rescan, for every path expression it evaluated.
    A fresh-consumer build still spent about a third of its time there.

CONTRACT FOR THE CODER:
    build_referential_integrity_closure_eval gains two memoising wrappers,
    imported by the closure and resolvers modules and used by every detector:
      * ``_tree_nodes(tree)`` -> the list ``list(ast.walk(tree))``, built once
        per tree and kept on the tree.
      * ``_scope_assignments(scope, tree)`` -> the same mapping
        ``_build_local_assignments(scope, tree)`` returns, built once per scope.
    ``ast.walk`` and ``_build_local_assignments`` stay unmemoised, so patching
    the wrappers back to them reproduces the pre-change computation.

RED BEFORE THE FIX: the two counting tests fail by assertion (six walks per
    module tree; one map per path expression), and the comparison test fails
    by absence of the wrappers.
"""

from __future__ import annotations

import ast
import contextlib
import io
import logging
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 -- after sys.path setup
import build_referential_integrity as _bri  # noqa: E402 -- after sys.path setup
import build_referential_integrity_closure as _brc  # noqa: E402
import build_referential_integrity_closure_eval as _bre  # noqa: E402
import build_referential_integrity_closure_resolvers as _brr  # noqa: E402

# Every Nth real root is compared; each comparison analyses its whole closure
# twice (memoised and unmemoised), so the full set would cost ~2 build guards.
_SAMPLE_STRIDE = 40

_DETECTOR_MODULES = (_brc, _brr, _bre)

_MODULE_BODY = '''\
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
CFG = _HERE / "cfg.json"
OTHER = _HERE / "other.json"


def load():
    data = _HERE / "data.json"
    extra = _HERE / "extra.json"
    return data.read_text(), extra.read_text(), CFG.read_text(), OTHER.read_text()
'''

_FILES = {
    "a.py": _MODULE_BODY,
    "b.py": "import a\n" + _MODULE_BODY,
    "cfg.json": "{}\n",
    "other.json": "{}\n",
    "data.json": "{}\n",
    "extra.json": "{}\n",
}


def _write_package(tmp: Path) -> set[str]:
    """Write the fixture package under *tmp*/scripts and return its Set B."""
    (tmp / "scripts").mkdir(parents=True, exist_ok=True)
    for name, body in _FILES.items():
        (tmp / "scripts" / name).write_text(body, encoding="utf-8")
    return {f"scripts/{name}" for name in _FILES}


def _run_guard_on_temp_package(tmp: Path, deployed: set[str]) -> tuple[int, str]:
    """Run the REAL build guard with Set B and the root resolver pointed at *tmp*."""

    def _resolve(_package_root: Path, deploy_path: str):
        return tmp / deploy_path, tmp, ""

    stderr = io.StringIO()
    with (
        mock.patch.object(_build, "_get_source_deployable_scripts", return_value=set(deployed)),
        mock.patch.object(_build, "_source_file_for_deploy_path", side_effect=_resolve),
        contextlib.redirect_stderr(stderr),
    ):
        code = _build._check_intra_package_closure_guard(tmp)
    return code, stderr.getvalue()


def _real_roots() -> list[tuple[str, Path, Path, str]]:
    """Return (deploy_path, source_file, root, prefix) for every real .py root."""
    out = []
    for deploy_path in sorted(_build._get_source_deployable_scripts(_REPO_ROOT)):
        if not deploy_path.endswith(".py"):
            continue
        resolved = _build._source_file_for_deploy_path(_REPO_ROOT, deploy_path)
        if resolved is None or not resolved[0].is_file():
            continue
        out.append((deploy_path, *resolved))
    return out


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _pass_over(roots) -> tuple[dict, list[str]]:
    """One guard-shaped pass over *roots* with a fresh cache; return results + warnings."""
    logger = logging.getLogger("build_referential_integrity")
    handler = _Capture()
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    cache: dict = {}
    try:
        results = {}
        for deploy_path, source, root, prefix in roots:
            closure, drr = _bri.compute_intra_package_closure_with_deploy_root_relative(
                source, root, _REPO_ROOT, closure_cache=cache
            )
            namespaced = {d if d in drr else f"{prefix}{d}" for d in closure}
            results[deploy_path] = (closure, drr, namespaced)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    return results, handler.messages


class TestPerFileWorkIsNotRepeated(unittest.TestCase):

    def test_each_module_tree_is_walked_once_per_pass(self):
        # covers: BP-900g-8-iv
        # angle: discrimination
        """Every module tree reaches ast.walk exactly once in one guard pass."""
        real_walk = ast.walk
        walked: list[ast.AST] = []

        def _counting_walk(node):
            if isinstance(node, ast.Module):
                walked.append(node)
            return real_walk(node)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            deployed = _write_package(tmp)
            with mock.patch.object(ast, "walk", side_effect=_counting_walk):
                result = _run_guard_on_temp_package(tmp, deployed)
        self.assertEqual(result, (0, ""))
        per_tree = Counter(id(tree) for tree in walked)
        self.assertEqual(len(per_tree), 2, "expected one module tree per .py file")
        self.assertEqual(sorted(per_tree.values()), [1, 1], per_tree)

    def test_each_scope_assignment_map_is_built_once_per_pass(self):
        # covers: BP-900g-8-iv
        # angle: discrimination
        """_build_local_assignments runs once per scope, not once per path expression."""
        real_build = _bre._build_local_assignments
        scopes: list[ast.AST] = []

        def _counting_build(scope, tree=None):
            scopes.append(scope)
            return real_build(scope, tree)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            deployed = _write_package(tmp)
            with contextlib.ExitStack() as stack:
                for module in _DETECTOR_MODULES:
                    if hasattr(module, "_build_local_assignments"):
                        stack.enter_context(mock.patch.object(
                            module, "_build_local_assignments", side_effect=_counting_build
                        ))
                result = _run_guard_on_temp_package(tmp, deployed)
        self.assertEqual(result, (0, ""))
        per_scope = Counter(id(scope) for scope in scopes)
        labels = Counter(
            getattr(scope, "name", "<module>")
            for scope in {id(s): s for s in scopes}.values()
        )
        # Two files, each with a module scope and one function scope.
        self.assertEqual(labels, Counter({"<module>": 2, "load": 2}), labels)
        self.assertEqual(sorted(per_scope.values()), [1, 1, 1, 1], per_scope)

    def test_closures_and_warnings_match_the_unmemoised_path_on_real_roots(self):
        # covers: BP-900g-8-iv
        # angle: criterion
        """Same closures, same namespaced findings, same WARNING lines without the memos."""
        sample = _real_roots()[::_SAMPLE_STRIDE]
        self.assertGreaterEqual(len(sample), 5, "expected the real deployed root set")

        memoised, memoised_warnings = _pass_over(sample)

        with contextlib.ExitStack() as stack:
            for module in _DETECTOR_MODULES:
                stack.enter_context(mock.patch.object(
                    module, "_tree_nodes", side_effect=lambda tree: ast.walk(tree)
                ))
                stack.enter_context(mock.patch.object(
                    module, "_scope_assignments", side_effect=_bre._build_local_assignments
                ))
            reference, reference_warnings = _pass_over(sample)

        self.assertEqual(set(memoised), set(reference))
        for deploy_path, expected in reference.items():
            self.assertEqual(memoised[deploy_path], expected, deploy_path)
        self.assertTrue(reference_warnings, "the sample must exercise the warning path")
        self.assertEqual(memoised_warnings, reference_warnings)


if __name__ == "__main__":
    unittest.main()
