"""MODULE: unit_tests/evals/tq200d5iv/_lock.py

GOAL: Fake a Windows file-in-use lock (PermissionError on delete) for the temp folders of a produced-tests row,
    so the tests of TQ-200d-5-iv run on Linux CI. Only ``shutil.rmtree`` is patched; nothing needs a real lock.
"""

from __future__ import annotations

import shutil
from pathlib import Path

REAL_RMTREE = shutil.rmtree
LOCK_ERROR = PermissionError(13, "The process cannot access the file because it is being used by another process")
PREFIX = "produced-tests-"


class Lock:
    """Records every delete attempt and fails those the *scope* selects.

    scope "row": only the row folder itself; "all": the row folder and anything under it;
    "sandbox": only folders named like the agent/scoring sandbox. *first_only* locks just the first row folder seen.
    *fail_first* makes each selected path fail only that many times, then succeed.
    """

    def __init__(self, scope: str, *, first_only: bool = False, fail_first: int | None = None, sandbox_name: str = "sandbox"):
        self.scope, self.first_only, self.fail_first, self.sandbox_name = scope, first_only, fail_first, sandbox_name
        self.roots: list[Path] = []
        self.attempts: dict[str, int] = {}

    def _root(self, path: Path) -> Path | None:
        for i, part in enumerate(path.parts):
            if part.startswith(PREFIX):
                root = Path(*path.parts[: i + 1])
                if root not in self.roots:
                    self.roots.append(root)
                return root
        return None

    def selected(self, path: Path) -> bool:
        root = self._root(path)
        if root is None:
            return False
        if self.first_only and root != self.roots[0]:
            return False
        if self.scope == "row":
            return path == root
        if self.scope == "sandbox":
            return path.name == self.sandbox_name
        return True

    def __call__(self, path, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        p = Path(path)
        if self.selected(p):
            key = str(p)
            self.attempts[key] = self.attempts.get(key, 0) + 1
            if self.fail_first is None or self.attempts[key] <= self.fail_first:
                if kwargs.get("ignore_errors") or (len(args) > 0 and args[0] is True):
                    return None  # the real rmtree swallows the error when told to ignore errors
                raise LOCK_ERROR
        return REAL_RMTREE(path, *args, **kwargs)

    def left_behind(self) -> list[Path]:
        return [r for r in self.roots if r.exists()]

    def cleanup(self) -> None:
        for r in self.roots:
            REAL_RMTREE(r, ignore_errors=True)


def install(monkeypatch, scope: str, **kw) -> Lock:
    lock = Lock(scope, **kw)
    monkeypatch.setattr(shutil, "rmtree", lock)
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
    return lock
