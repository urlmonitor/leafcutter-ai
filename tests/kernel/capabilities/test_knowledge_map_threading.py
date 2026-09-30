"""
MODULE: tests.kernel.capabilities.test_knowledge_map_threading
GOAL: Prove the knowledge-map bridge loads scripts/knowledge_query.py safely when many retrieval
    workers ask for it at the same moment on a fresh process.
BUSINESS CONTEXT: A live demo showed the knowledge-map source failing intermittently with
    "module 'knowledge_frontmatter_reader' has no attribute '_find_frontmatter_end'": a thread
    saw a sibling module another thread was still executing (design part 4 risk list).
ARCHITECTURE: The sibling modules are evicted from sys.modules and the bridge caches cleared, so
    each run starts like a fresh import; a barrier releases all threads together. Originals are
    restored afterwards so other tests are unaffected.
"""

from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

from kernel.capabilities.retrieval import knowledge_map as km

REAL_ROOT = Path(__file__).resolve().parents[3]
SIBLINGS = ("knowledge_frontmatter_reader", "knowledge_file_nodes", "knowledge_surface_check")
THREADS = 24
ROUNDS = 6


class TestConcurrentBridgeLoad(unittest.TestCase):
    """Many threads loading the bridge on a fresh import must all get a complete module."""

    def setUp(self) -> None:
        self._saved = {n: sys.modules.get(n) for n in SIBLINGS}
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        for name, module in self._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        km.clear_caches()

    def _fresh(self) -> None:
        for name in SIBLINGS:
            sys.modules.pop(name, None)
        km.clear_caches()

    def test_parallel_workers_all_get_a_fully_loaded_module(self) -> None:
        for _ in range(ROUNDS):
            self._fresh()
            barrier = threading.Barrier(THREADS)
            outcomes: list[object] = []
            lock = threading.Lock()

            def worker() -> None:
                barrier.wait()
                try:
                    module = km._load_module(REAL_ROOT)
                    result: object = module.build_knowledge_map
                except km.KnowledgeMapUnavailable as exc:
                    result = exc
                with lock:
                    outcomes.append(result)

            threads = [threading.Thread(target=worker) for _ in range(THREADS)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            failures = [o for o in outcomes if isinstance(o, Exception)]
            self.assertEqual(failures, [], f"{len(failures)} of {THREADS} loads failed")
            self.assertEqual(len({id(o) for o in outcomes}), 1, "workers got different modules")
            for name in SIBLINGS:
                self.assertTrue(hasattr(sys.modules[name], "__file__"))
            self.assertTrue(hasattr(sys.modules["knowledge_frontmatter_reader"],
                                    "_find_frontmatter_end"))


if __name__ == "__main__":
    unittest.main()
