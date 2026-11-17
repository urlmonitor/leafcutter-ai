"""
MODULE: test_bp_900g_8_closure_cache
GOAL: Pin the per-pass analysis cache of the deploy-completeness closure guard
    (BP-900g-8 / BP-900g-8-i): a faster guard must return exactly the verdicts
    the uncached guard returns, and must parse each file once per pass.
BUSINESS CONTEXT: build.py's _check_intra_package_closure_guard calls
    compute_intra_package_closure_with_deploy_root_relative once per deployed
    root (~390), each with a fresh visited set, so shared modules are read,
    parsed and walked again for every root (~4.4x redundant) and a fresh-consumer
    build takes ~27 s against a 30 s test budget.

CONTRACT FOR THE CODER (the new pass-level API this file expects):
    compute_intra_package_closure_with_deploy_root_relative(
        script, root, data_root=None, closure_cache: dict | None = None
    )
    * ``closure_cache=None`` (default) keeps today's behaviour exactly.
    * A caller passes ONE plain ``dict`` per guard pass and the SAME dict for
      every root of that pass; the function stores each file's analysis in it
      (keyed on script path as reached, root and data_root) and reuses it.
    * The per-root ``visited`` set and the closure union stay per call.
    * _check_intra_package_closure_guard creates the dict itself, once per
      call, so nothing survives the pass (no module-level state).

GREEN/RED: AC-1 is red today only by absence (no ``closure_cache`` parameter
    yet) and is a guard once it exists; AC-2 is green before and after (a
    guard); AC-3 is red today by assertion (shared file parsed twice).
"""

from __future__ import annotations

import ast
import contextlib
import io
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

# Uncached reference runs per sampled root are the slow half; compare every
# Nth real root uncached (the cached pass still walks ALL roots, in order).
_UNCACHED_SAMPLE_STRIDE = 40


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


def _write_package(tmp: Path, files: dict[str, str]) -> None:
    (tmp / "scripts").mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (tmp / "scripts" / name).write_text(body, encoding="utf-8")


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


def _namespaced(closure: set[str], drr: set[str], prefix: str) -> set[str]:
    return {d if d in drr else f"{prefix}{d}" for d in closure}


def _cached_pass(roots, cache: dict) -> dict:
    """One guard-shaped pass: every root through the SAME closure_cache dict."""
    return {
        deploy_path: _bri.compute_intra_package_closure_with_deploy_root_relative(
            source, root, _REPO_ROOT, closure_cache=cache
        )
        for deploy_path, source, root, _prefix in roots
    }


_CHAIN = {"a.py": "import b\n", "b.py": "import c\n", "c.py": "X = 1\n"}


class TestClosureCache(unittest.TestCase):
    """The two ~4.5 s cached passes run once in setUpClass (setup, not test time)."""

    @classmethod
    def setUpClass(cls):
        cls.roots = _real_roots()
        cls.forward_cache: dict = {}
        cls.forward = _cached_pass(cls.roots, cls.forward_cache)
        # Fresh dict, reverse order: a key leak that only hits some root shows
        # up as a per-root mismatch against the forward pass.
        cls.reverse = _cached_pass(list(reversed(cls.roots)), {})

    def test_cached_closure_equals_uncached_for_every_real_root(self):
        # covers: BP-900g-8
        # covers: BP-900g-8-i
        # angle: criterion
        """AC-1: the shared-dict pass over the real roots equals independent,
        cache-free calls on a deterministic spread of roots (same closure and
        same namespaced findings).

        Needs the closure_cache kwarg (module docstring); red by absence before.
        """
        self.assertGreater(len(self.roots), 100, "expected the real deployed root set")
        self.assertTrue(self.forward_cache, "the pass-level cache must be populated")
        sample = self.roots[::_UNCACHED_SAMPLE_STRIDE]
        self.assertGreaterEqual(len(sample), 5)
        for deploy_path, source, root, prefix in sample:
            reference = _bri.compute_intra_package_closure_with_deploy_root_relative(
                source, root, _REPO_ROOT
            )
            self.assertEqual(self.forward[deploy_path], reference, deploy_path)
            self.assertEqual(
                _namespaced(*self.forward[deploy_path], prefix),
                _namespaced(*reference, prefix),
            )

    def test_cached_closure_is_independent_of_root_order_for_every_real_root(self):
        # covers: BP-900g-8
        # angle: discrimination
        """AC-1: forward and reverse cached passes agree on ALL real roots.

        Catches a cache keyed so coarsely that an earlier root's result leaks
        into a later one (only visible on some orderings).
        """
        prefixes = {r[0]: r[3] for r in self.roots}
        self.assertEqual(set(self.forward), set(self.reverse))
        for deploy_path, forward in self.forward.items():
            self.assertEqual(self.reverse[deploy_path], forward, deploy_path)
            self.assertEqual(
                _namespaced(*self.reverse[deploy_path], prefixes[deploy_path]),
                _namespaced(*forward, prefixes[deploy_path]),
            )

    def test_second_hop_missing_module_still_refused_with_cache(self):
        # covers: BP-900g-8-i
        # angle: failure
        """AC-2: A imports B imports undeployed C; the guard refuses naming C.

        Guard test: green before the change and must stay green with the cache.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_package(tmp, _CHAIN)
            code, err = _run_guard_on_temp_package(tmp, {"scripts/a.py", "scripts/b.py"})
        self.assertEqual(code, 1)
        self.assertIn("UNDEPLOYED DEPENDENCY", err)
        self.assertIn("'scripts/c.py'", err)
        # Control: with C deployed too the same package is clean.
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_package(tmp, _CHAIN)
            deployed = {"scripts/a.py", "scripts/b.py", "scripts/c.py"}
            self.assertEqual(_run_guard_on_temp_package(tmp, deployed), (0, ""))

    def test_each_file_is_parsed_once_per_pass(self):
        # covers: BP-900g-8
        # angle: discrimination
        """AC-3: two roots share a module; one guard pass parses it exactly once.

        Red today: each root re-parses shared.py (count 2). Wrong versions this
        catches: no cache at all; a cache cleared per root.
        """
        real_parse = ast.parse
        parses: Counter[str] = Counter()

        def _counting_parse(source, filename="<unknown>", *args, **kwargs):
            parses[str(filename)] += 1
            return real_parse(source, filename, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_package(
                tmp,
                {"a.py": "import shared\n", "b.py": "import shared\n", "shared.py": "X = 1\n"},
            )
            deployed = {"scripts/a.py", "scripts/b.py", "scripts/shared.py"}
            with mock.patch.object(ast, "parse", side_effect=_counting_parse):
                result = _run_guard_on_temp_package(tmp, deployed)
            ours = {Path(k).name: v for k, v in parses.items() if str(tmp) in k}
        self.assertEqual(result, (0, ""))
        self.assertEqual(ours, {"a.py": 1, "b.py": 1, "shared.py": 1})


if __name__ == "__main__":
    unittest.main()
