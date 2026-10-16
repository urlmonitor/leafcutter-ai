"""Shared helpers for test_bo_4400f_1.py.

ASSUMED PRODUCTION CONTRACT (python-coder implements against exactly this):
    * Source ``templates/scripts/scratch.py`` (stdlib only), deployed by
      build.py to ``<layout>/.leafcutter/scripts/scratch.py`` (named
      deploy-manifest entry).
    * ``scratch_root() -> str`` -- absolute; default
      ``$XDG_CACHE_HOME/leafcutter/scratch`` when no config overrides it.
    * ``new_item(owner_run_id: str, route: str) -> str`` -- a fresh item
      folder holding ``label.json`` with keys owner_run_id, route, pid, host,
      created_at (UTC ISO-8601, offset-aware). ``pid`` is the CALLING process.
    * ``classify(item, now, age_limit_hours) -> dict`` -- ``now`` is an
      offset-aware datetime; returns {"expired": bool, "reason": one of
      "owner_active" | "within_age" | "owner_ended_and_old" |
      "owner_unknown_and_old"}. Owner liveness = process liveness of the
      label's pid; a missing or unreadable label means owner unknown, with the
      item folder's mtime as its age.
    * ``durable_paths() -> list[str]`` -- includes test-logs and debugging/logs.
    * ``python scratch.py sweep`` (BO-4400f-1-i / -1-ii) -- removes exactly
      what classify() calls expired, among the scratch root's items and the
      declared third-party leftovers (pre-commit stash patch FILES in
      PRE_COMMIT_HOME or <user cache dir>/pre-commit), and prints one JSON
      line ``{"removed": {"scratch": N}, "removed_paths": [...], ...}``.
    * ``python scratch.py new-item <owner> <route> --owner-pid <pid>`` --
      records ``<pid>`` (the run's long-lived process) as the label's pid.
The deployed module is only ever driven in a SEPARATE process, below.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

DRIVER = '''
import json, sys
sys.path.insert(0, sys.argv[1])
import scratch
action = sys.argv[2]
payload = json.loads(sys.argv[3])
if action == "new_item":
    item = scratch.new_item(payload["owner"], payload["route"])
    print(json.dumps({"item": item}), flush=True)
    if payload.get("hold"):
        sys.stdin.readline()
elif action == "classify":
    from datetime import datetime
    result = scratch.classify(
        payload["item"], datetime.fromisoformat(payload["now"]), payload["age_limit_hours"]
    )
    print(json.dumps(result))
elif action == "locations":
    print(json.dumps({"root": scratch.scratch_root(), "durable": list(scratch.durable_paths())}))
'''


@dataclass
class Sandbox:
    """A redirected HOME / cache / temp stand-in plus a fake project."""

    base: Path
    scripts_dir: Path

    @property
    def home(self) -> Path:
        return self.base / "home"

    @property
    def temp_standin(self) -> Path:
        return self.base / "systemtmp"

    @property
    def project(self) -> Path:
        return self.base / "project"

    @property
    def env(self) -> dict:
        return {
            **os.environ,
            "HOME": str(self.home),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "TMPDIR": str(self.temp_standin),
            "TEMP": str(self.temp_standin),
            "TMP": str(self.temp_standin),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def _argv(self, action: str, payload: dict) -> list[str]:
        module = self.scripts_dir / "scratch.py"
        assert module.is_file(), (
            f"deployed layout has no {module} -- the scratch module must exist in "
            "templates/scripts/ and be in the build deploy manifest"
        )
        driver = self.base / "driver.py"
        driver.write_text(DRIVER, encoding="utf-8")
        return [sys.executable, str(driver), str(self.scripts_dir), action, json.dumps(payload)]

    def call(self, action: str, payload: dict) -> dict:
        done = subprocess.run(  # noqa: S603
            self._argv(action, payload), cwd=self.project, env=self.env,
            capture_output=True, text=True, timeout=60, check=False,
        )
        if done.returncode != 0:
            raise AssertionError(f"scratch {action} failed: {done.stderr[-1500:]}")  # noqa: TRY003
        return json.loads(done.stdout.strip().splitlines()[-1])

    def sweep(self, extra_env: dict | None = None) -> dict:
        """Run the DEPLOYED sweep (``scratch.py sweep``) as a separate process.

        PRE_COMMIT_HOME is dropped from the inherited environment unless the
        caller supplies it, so the sweep can never reach a real cache folder.
        """
        module = self.scripts_dir / "scratch.py"
        assert module.is_file(), f"deployed layout has no {module}"
        env = {key: value for key, value in self.env.items() if key != "PRE_COMMIT_HOME"}
        env.update(extra_env or {})
        done = subprocess.run(  # noqa: S603
            [sys.executable, str(module), "sweep"], cwd=self.project, env=env,
            capture_output=True, text=True, timeout=60, check=False,
        )
        if done.returncode != 0:
            raise AssertionError(f"scratch sweep failed ({done.returncode}): {done.stderr[-1500:]}")  # noqa: TRY003
        return json.loads(done.stdout.strip().splitlines()[-1])

    def start_holding_owner(self, owner: str, route: str) -> tuple[subprocess.Popen, str]:
        """An owner run that is still alive: creates an item then waits."""
        proc = subprocess.Popen(  # noqa: S603
            self._argv("new_item", {"owner": owner, "route": route, "hold": True}),
            cwd=self.project, env=self.env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        line = proc.stdout.readline()
        if not line:
            proc.kill()
            raise AssertionError(f"owner failed: {proc.stderr.read()[-1500:]}")  # noqa: TRY003
        return proc, json.loads(line)["item"]


def make_sandbox(scripts_dir: Path) -> tuple[Sandbox, tempfile.TemporaryDirectory]:
    """Build the sandbox (including a fake project with durable folders)."""
    holder = tempfile.TemporaryDirectory(prefix="bo4400f1_")
    box = Sandbox(Path(holder.name), scripts_dir)
    for folder in (box.home, box.temp_standin, box.project / "test-logs",
                   box.project / "debugging" / "logs"):
        folder.mkdir(parents=True)
    return box, holder


def snapshot(*roots: Path) -> set[str]:
    """Every path (recursive) under the given roots, plus the roots' own listing."""
    seen: set[str] = set()
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            for name in dirnames + filenames:
                seen.add(str(Path(dirpath, name)))
    return seen


def read_label(item: str) -> dict:
    return json.loads((Path(item) / "label.json").read_text(encoding="utf-8"))


def backdate(path: Path, hours: float) -> None:
    """Set ``path``'s mtime (and every entry under it) ``hours`` into the past."""
    stamp = time.time() - hours * 3600
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            os.utime(Path(dirpath, name), (stamp, stamp))
    os.utime(path, (stamp, stamp))


def backdate_item(item: str, hours: float) -> None:
    """Make a labelled item ``hours`` old: its label's created_at and its mtimes."""
    label = read_label(item)
    label["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    (Path(item) / "label.json").write_text(json.dumps(label), encoding="utf-8")
    backdate(Path(item), hours)


def tree_digest(root: Path) -> str:
    """sha256 over every entry's relative path and every file's bytes."""
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in sorted(os.walk(root)):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath, name)
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
        for name in dirnames:
            digest.update(str(Path(dirpath, name).relative_to(root)).encode() + b"/")
    return digest.hexdigest()
