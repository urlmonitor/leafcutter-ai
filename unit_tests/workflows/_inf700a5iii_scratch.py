"""
MODULE: unit_tests/workflows/_inf700a5iii_scratch.py
GOAL: Real-artifact scratch install and a released-together process launcher
    for INF-700a-5-iii's concurrency tests (test_inf_700a_5_iii.py).

WHAT THE SCRATCH INSTALL IS: a bare ``origin`` repository whose ``main`` is
    the base branch (origin/main); one ordinary clone of it (``base``) that
    plays the part of whoever merges pull requests; and linked worktrees of
    that clone (``git worktree add``), each on its own branch -- the isolated
    working directories two units of work run in. Because linked worktrees
    share one object store and one set of remote-tracking refs, a fetch in one
    worktree is seen by the other, exactly as in a real install. The sink and
    the claim store (``harvest_state.json``) live OUTSIDE every worktree, and
    every run is handed the SAME two paths: INF-700a-5-iii's it_requirements
    line 1 makes "the two runs share ONE state file" a precondition of the
    suite meaning anything.

THE CHOSEN SYNCHRONISATION (recorded per it_requirements line 6, so a reader
    can tell a real overlap from an accidental sequence): each run is a
    separate Python process. It loads its target module (the real
    ``completion_routing_cli.py``, or ``completion_routing.py`` for the claim
    step whose off switch is deliberately not on the CLI) BEFORE the barrier,
    touches a ``ready`` file, then spins on a shared ``go`` file. The test
    creates ``go`` only after every run is ready, so all runs leave the
    barrier within about a millisecond of each other and the import cost is
    paid outside the measured window. Each run records wall-clock time on
    entering and leaving the call; ``assert_overlapped`` then requires every
    run to have entered before any run left. For the claim step alone -- an
    arbitrated claim is shorter than the barrier's release skew -- the test
    additionally holds the claim store's real lock until every run is inside
    the claim, so all of them contend for it at once (claim_together). No
    sleep is added between the runs, nothing serialises them, and nothing is
    retried until green.
"""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import workflows._inf700a5_fixtures as fx

CLI_PATH = fx._REPO_ROOT / "scripts" / "knowledge" / "completion_routing_cli.py"
ROUTING_PATH = fx._REPO_ROOT / "scripts" / "knowledge" / "completion_routing.py"
BARRIER_TIMEOUT_SECONDS = 60
RUN_TIMEOUT_SECONDS = 120
# How long the test keeps holding the claim store's lock after every claim run
# has entered claim_and_confirm_routed, so each is blocked on the flock when it
# is released (see ScratchInstall.claim_together). It only ever delays the
# release of runs that are already waiting together.
CONTENTION_HOLD_SECONDS = 0.2

# Runs the REAL completion_routing_cli.main(argv) -- the function the CLI's
# `if __name__ == "__main__"` block calls -- after the shared barrier.
_CLI_LAUNCHER = r"""
import importlib.util, json, sys, time
from pathlib import Path
cfg = json.loads(sys.argv[1])
spec = importlib.util.spec_from_file_location("completion_routing_cli_concurrent", cfg["cli"])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
Path(cfg["ready"]).touch()
deadline = time.time() + cfg["barrier_timeout"]
while not Path(cfg["go"]).exists():
    if time.time() > deadline:
        sys.exit(97)
    time.sleep(0.001)
start = time.time()
rc = mod.main(cfg["argv"])
sys.stdout.flush()
Path(cfg["timing"]).write_text(json.dumps({"start": start, "end": time.time()}))
sys.exit(rc)
"""

# The claim step of one completion path, as stage_completion runs it: find the
# sink records whose text is already on the base branch (the real git read),
# then claim them through the real claim_and_confirm_routed -- with the
# arbitration on or off. `extra_ids` lets a run claim ids of its own as well.
_CLAIM_LAUNCHER = r"""
import importlib.util, json, sys, time
from pathlib import Path
cfg = json.loads(sys.argv[1])
spec = importlib.util.spec_from_file_location("completion_routing_claim_concurrent", cfg["routing"])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ids = []
if cfg["sink"]:
    wd = Path(cfg["working_dir"])
    ids = [h for h, text, dest in mod._state.read_eligible_sink_records(Path(cfg["sink"]))
           if mod._git.text_on_ref(wd, cfg["base"], dest, text)]
ids += cfg["extra_ids"]
Path(cfg["ready"]).touch()
deadline = time.time() + cfg["barrier_timeout"]
while not Path(cfg["go"]).exists():
    if time.time() > deadline:
        sys.exit(97)
    time.sleep(0.001)
start = time.time()
Path(cfg["started"]).touch()
newly = mod.claim_and_confirm_routed(
    state_path=Path(cfg["state"]), record_ids=ids,
    lock_path=Path(cfg["lock"]) if cfg["lock"] else None,
    arbitration_enabled=cfg["arbitration"],
)
end = time.time()
print(json.dumps({"ids": ids, "newly": newly}))
Path(cfg["timing"]).write_text(json.dumps({"start": start, "end": end}))
"""


def _git(args: list[str], cwd: Path) -> str:
    return fx._run_git(args, cwd).stdout


class ScratchInstall:
    """origin (bare) + a base clone + linked worktrees + one shared sink/state."""

    def __init__(self, root: Path, destinations: dict[str, str]) -> None:
        self.root = root
        self.origin = root / "origin.git"
        self.base = root / "base"
        self.logs = root / "install-logs"
        self.sink = self.logs / "knowledge_emissions.jsonl"
        self.state = self.logs / "harvest_state.json"
        self._barriers = 0
        root.mkdir(parents=True, exist_ok=True)
        _git(["init", "--bare", "-b", "main", str(self.origin)], root)
        _git(["clone", str(self.origin), str(self.base)], root)
        _git(["checkout", "-B", "main"], self.base)
        for rel_path, content in destinations.items():
            target = self.base / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        fx.commit_paths(self.base, list(destinations), "seed install")
        _git(["push", "-u", "origin", "main"], self.base)

    def worktree(self, branch: str) -> Path:
        """A linked worktree of the base clone on a new branch off origin/main."""
        _git(["fetch", "origin", "main"], self.base)
        path = self.root / f"wt-{branch}"
        _git(["worktree", "add", "-b", branch, str(path), "origin/main"], self.base)
        return path

    def discard(self, wt: Path, branch: str) -> None:
        """Abandon a unit of work: remove its worktree and delete its branch unmerged."""
        _git(["worktree", "remove", "--force", str(wt)], self.base)
        _git(["branch", "-D", branch], self.base)

    def merge(self, branch: str) -> None:
        """Merge *branch* into main and publish it: origin/main now carries it."""
        _git(["merge", "--no-edit", branch], self.base)
        _git(["push", "origin", "main"], self.base)

    def on_origin_main(self, rel_path: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.origin), "show", f"main:{rel_path}"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        return proc.stdout if proc.returncode == 0 else ""

    def emit(self, text: str, destination: str) -> None:
        fx.emit(self.sink, agent="python-coder", component="infrastructure",
                destination=destination, entry_kind="memory-project", text=text)

    def claims(self) -> list[str]:
        """The claim store as it is on disk; [] when absent. Raises on a torn file."""
        if not self.state.exists():
            return []
        return json.loads(self.state.read_text(encoding="utf-8"))

    def push_from_outside(self, rel_path: str, text: str) -> None:
        """Publish *text* onto origin/main from a separate clone, so the base
        clone's (and every worktree's) origin/main stays stale until fetched."""
        outside = self.root / "outside"
        if not outside.exists():
            _git(["clone", str(self.origin), str(outside)], self.root)
        _git(["pull", "--no-edit", "origin", "main"], outside)
        target = outside / rel_path
        target.write_text(fx.read_file(target) + text + "\n", encoding="utf-8")
        fx.commit_paths(outside, [rel_path], "published from outside")
        _git(["push", "origin", "HEAD:main"], outside)

    def cli_argv(self, command: str, wt: Path | None, *extra: str) -> list[str]:
        where = ["--working-dir", str(wt)] if wt is not None else []
        return [command, *where, "--sink", str(self.sink), "--state", str(self.state), *extra]

    def cli(self, command: str, wt: Path | None, *extra: str) -> tuple[int, dict]:
        """One sequential CLI call in a fresh process: (exit status, reply)."""
        proc = subprocess.run(
            [sys.executable, str(CLI_PATH), *self.cli_argv(command, wt, *extra)],
            capture_output=True, text=True, timeout=RUN_TIMEOUT_SECONDS, check=False,
        )
        return proc.returncode, _last_json(proc.stdout, proc.stderr)

    def _barrier_dir(self) -> Path:
        self._barriers += 1
        path = self.root / "barriers" / str(self._barriers)
        path.mkdir(parents=True)
        return path

    def cli_together(self, argvs: list[list[str]]) -> list[dict[str, Any]]:
        """Run the real CLI once per argv, all released from one barrier."""
        cfgs = [{"cli": str(CLI_PATH), "argv": argv} for argv in argvs]
        return self._together(_CLI_LAUNCHER, cfgs)

    def claim_together(self, runs: list[dict[str, Any]], *, arbitration: bool,
                       state: Path | None = None) -> list[dict[str, Any]]:
        """Run the claim step once per run spec, all released from one barrier.

        A run spec may name ``working_dir`` (find published records from the
        sink against origin/main there), ``extra_ids`` and ``lock``.

        An arbitrated claim lasts well under a millisecond -- shorter than the
        barrier's release skew -- so released runs would mostly pass each
        other in sequence. To make the claims overlap for certain, the test
        itself holds the claim store's real lock (the production default,
        ``<state>.lock``) while the runs are released, waits until every run
        has entered ``claim_and_confirm_routed``, gives them
        ``CONTENTION_HOLD_SECONDS`` to reach the lock, then lets go: every
        arbitrated run is then contending for the lock at once. This makes
        the overlap MORE reliable and never serialises the pair (the
        it_requirements line 6 rule). With the arbitration disabled the runs
        never touch the lock, so the hold changes nothing for them.
        """
        state_path = Path(state or self.state)
        cfgs = [{
            "routing": str(ROUTING_PATH), "state": str(state_path),
            "arbitration": arbitration, "base": "origin/main",
            "sink": str(self.sink) if run.get("working_dir") else "",
            "working_dir": str(run.get("working_dir", "")),
            "extra_ids": run.get("extra_ids", []), "lock": str(run.get("lock", "")),
        } for run in runs]
        lock_path = state_path.with_suffix(".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as held:
            fcntl.flock(held.fileno(), fcntl.LOCK_EX)

            def _release_when_all_contend() -> None:
                _wait_for([Path(c["started"]) for c in cfgs])
                time.sleep(CONTENTION_HOLD_SECONDS)
                fcntl.flock(held.fileno(), fcntl.LOCK_UN)

            return self._together(_CLAIM_LAUNCHER, cfgs, after_go=_release_when_all_contend)

    def _together(self, launcher: str, cfgs: list[dict[str, Any]],
                  after_go: Callable[[], None] | None = None) -> list[dict[str, Any]]:
        barrier = self._barrier_dir()
        go = barrier / "go"
        procs = []
        for i, cfg in enumerate(cfgs):
            cfg.update(ready=str(barrier / f"ready{i}"), go=str(go),
                       started=str(barrier / f"started{i}"),
                       timing=str(barrier / f"timing{i}"),
                       barrier_timeout=BARRIER_TIMEOUT_SECONDS)
            procs.append(subprocess.Popen(
                [sys.executable, "-c", launcher, json.dumps(cfg)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ))
        _wait_for([Path(c["ready"]) for c in cfgs], procs)
        go.touch()
        if after_go is not None:
            after_go()
        results = []
        for cfg, proc in zip(cfgs, procs):
            out, err = proc.communicate(timeout=RUN_TIMEOUT_SECONDS)
            timing_path = Path(cfg["timing"])
            timing = json.loads(timing_path.read_text()) if timing_path.exists() else None
            results.append({"returncode": proc.returncode, "reply": _last_json(out, err),
                            "timing": timing, "stderr": err})
        return results


def _wait_for(paths: list[Path], procs: list[subprocess.Popen] | None = None) -> None:
    """Spin until every path exists, a process has exited, or the barrier times out."""
    deadline = time.time() + BARRIER_TIMEOUT_SECONDS
    while not all(p.exists() for p in paths):
        if time.time() > deadline or any(p.poll() is not None for p in procs or []):
            return
        time.sleep(0.001)


def _last_json(stdout: str, stderr: str) -> dict:
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    if not lines:
        raise AssertionError(f"process printed no JSON; stderr={stderr}")  # noqa: TRY003
    return json.loads(lines[-1])


def assert_overlapped(case: Any, results: list[dict[str, Any]]) -> None:
    """Every run entered its call before any run left it -- a real overlap."""
    timings = [r["timing"] for r in results]
    case.assertTrue(all(timings), f"a run did not complete its call: {results!r}")
    latest_start = max(t["start"] for t in timings)
    earliest_end = min(t["end"] for t in timings)
    case.assertLess(
        latest_start, earliest_end,
        f"the runs did not overlap (one finished before the other began), so "
        f"this exercised a sequence, not a race: {timings!r}",
    )
