"""
MODULE: test_bo_4300b_4
GOAL: Red-first behavioural tests for BO-4300b-4 -- on a machine where the user may
    not create links (Windows without Developer Mode), a requested workspace is
    still answered ready, with nothing in it a link, and is the same as the one a
    link-permitted machine gets.
PROOF SHAPE: the DEPLOYED maker (shared reference layout, read-only; never the
    templates/ source copy, never a build.py spawn) runs as a separate process
    against real temporary git repositories and a real bare hub. Link denial is
    injected into the maker process (and so its build child) by a real
    ``sitecustomize.py`` on PYTHONPATH that makes ``os.symlink`` raise. No mock
    of git, no import of the maker, no grep of its source.
ARM 2 (every platform): the injected denial above. ARM 1 (real Windows runner
    without Developer Mode): ``test_real_windows_without_link_permission`` runs
    only there and is SKIPPED, i.e. reported "not run", everywhere else, never
    passed. ``test_ci_runs_this_module_on_a_windows_runner`` pins the job.
ASSUMED PRODUCTION CONTRACT (python-coder implements against exactly this):
    * The ok answer's ``checks`` dict carries ``install_paths_regular``: True
      only when every path under the workspace's ``.leafcutter`` install and its
      ``.pre-commit-config.yaml`` (and its installed hook files) is a regular
      file or folder, found by lstat: no symlink and no Windows junction.
    * A workspace whose install holds a link is NOT_READY (``checks`` names
      ``install_paths_regular`` False) and is removed, as any failed ensure is.
    * No link is attempted anywhere on the ensure path (decision 2): the
      injected denial records every ``os.symlink`` attempt and none is made.
ENTRY POINT (reachability): the deployed CLI ``python <install>/scripts/worktree.py
    ensure --kind feature --slug beta`` run with real argv under link denial.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest
import yaml

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import KNOWN_BAD, STUB_BUILD, find_marker, git, git_ok, run_maker
from ._bo4300b1_helpers import build_world

REPO_ROOT = Path(__file__).resolve().parents[2]

# A build entry point that behaves like STUB_BUILD, and additionally makes the
# kind of link named by $BO4300B4_LINK inside the install, the way a build that
# prefers links would. Inert when the variable is unset.
LINKING_BUILD = STUB_BUILD + '''
_kind = os.environ.get("BO4300B4_LINK")
if _kind:
    _install = target / ".leafcutter"
    if _kind == "file":
        os.symlink(scripts / "install_marker.txt", scripts / "linked_tool.txt")
    elif _kind == "dir":
        os.symlink(scripts, _install / "linked_folder", target_is_directory=True)
    elif _kind == "junction":
        import subprocess as _sp
        _sp.run(["cmd", "/c", "mklink", "/J", str(_install / "junction"), str(scripts)],
                check=True, capture_output=True)
'''

DENY_SITECUSTOMIZE = '''\
import errno, os
_log = os.environ.get("BO4300B4_DENIED_LOG")


def _denied(src, dst, *args, **kwargs):
    if _log:
        with open(_log, "a", encoding="utf-8") as handle:
            handle.write(f"{src} -> {dst}\\n")
    raise OSError(errno.EPERM, "symlink creation denied for this user (test injection)", str(dst))


os.symlink = _denied
'''

_ISO = re.compile(r"\d{4}-\d\d-\d\d[T ][0-9:.+\-Z]+")
_SHA = re.compile(r"\b[0-9a-f]{40}\b")


def _scripts_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"


def _can_make_symlinks() -> bool:
    with tempfile.TemporaryDirectory(prefix="bo4300b4_probe_") as holder:
        try:
            os.symlink(Path(holder) / "a", Path(holder) / "b")
        except (OSError, NotImplementedError):
            return False
    return True


def _snap(done, payload) -> str:
    return f"payload={json.dumps(payload)[:900]} stderr={done.stderr[-600:]!r}"


class Arm:
    """One world plus the environment of its maker process."""

    def __init__(self, deny: bool, link: str | None = None):
        self.world = build_world(_scripts_dir())
        self.base = self.world.base
        self.denied_log = self.base / "denied_symlink_attempts.log"
        _push_build(self.world, LINKING_BUILD)
        env = dict(self.world.env)
        env["BO4300B4_DENIED_LOG"] = str(self.denied_log)
        if link:
            env["BO4300B4_LINK"] = link
        if deny:
            shim = self.base / "deny_shim"
            shim.mkdir()
            (shim / "sitecustomize.py").write_text(DENY_SITECUSTOMIZE, encoding="utf-8")
            env["PYTHONPATH"] = str(shim)
        self.world.env = env

    def cleanup(self) -> None:
        self.world.holder.cleanup()

    def attempts(self) -> list[str]:
        if not self.denied_log.exists():
            return []
        return self.denied_log.read_text(encoding="utf-8").splitlines()

    def ensure(self, slug: str = "beta", cwd: Path | None = None):
        return run_maker(self.world, ["ensure", "--kind", "feature", "--slug", slug,
                                      "--repo-root", str(self.world.project)], cwd=cwd)


def _push_build(world, text: str) -> None:
    """Replace the hub's tracked build entry point with ``text`` (a real push)."""
    seed = world.base / "seeds2" / "seed"
    seed.parent.mkdir()
    git_ok(seed.parent, world.env, "clone", str(world.hub), "seed")
    (seed / "scripts" / "build.py").write_text(text, encoding="utf-8")
    git_ok(seed, world.env, "add", "-A")
    git_ok(seed, world.env, "commit", "-m", "linking build")
    git_ok(seed, world.env, "push", "origin", "HEAD:main")


def _walk_links(root: Path) -> list[str]:
    """Every symlink or junction under the install and the protection files."""
    found = []
    spots = [root / ".leafcutter", root / ".pre-commit-config.yaml", root / ".git" / "hooks"]
    for spot in spots:
        if spot.is_symlink() or _is_junction(spot):
            found.append(str(spot))
        for dirpath, dirnames, filenames in os.walk(spot):
            for name in [*dirnames, *filenames]:
                path = Path(dirpath, name)
                if path.is_symlink() or _is_junction(path):
                    found.append(str(path))
    return found


def _is_junction(path: Path) -> bool:
    check = getattr(os.path, "isjunction", None)
    if check is not None:
        return bool(check(path))
    try:
        attrs = os.lstat(path).st_file_attributes  # type: ignore[attr-defined]
    except (OSError, AttributeError):
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)) and not path.is_symlink()


def _normalise(arm: Arm, payload: dict) -> dict:
    """Blank paths, timestamps and shas so two worlds' answers can be compared."""
    text = json.dumps(payload, sort_keys=True)
    for form in {str(arm.base), os.path.realpath(arm.base), arm.base.as_posix()}:
        text = text.replace(json.dumps(form)[1:-1], "<BASE>").replace(form, "<BASE>")
    text = _SHA.sub("<SHA>", _ISO.sub("<TS>", text))
    return json.loads(text)


def _tree(root: Path) -> dict:
    """The workspace as relative path -> kind, outside .git objects."""
    listing = {}
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        if rel_dir.parts[:1] == (".git",):
            continue
        dirnames[:] = [d for d in dirnames if not (rel_dir == Path(".") and d == ".git")]
        for name in [*dirnames, *filenames]:
            path = Path(dirpath, name)
            kind = "link" if path.is_symlink() else ("dir" if path.is_dir() else "file")
            listing[(rel_dir / name).as_posix()] = kind
    marker_dir = {k for k in listing if k.endswith("workspace.json")}
    for key in marker_dir:  # the marker's own content differs by path/time, not its presence
        listing[key] = "marker"
    return listing


@pytest.mark.shared_layout_reader
class TestBo4300b4(unittest.TestCase):
    maxDiff = None

    def _arm(self, deny: bool, link: str | None = None) -> Arm:
        arm = Arm(deny, link)
        self.addCleanup(arm.cleanup)
        return arm

    def test_denial_injection_really_denies_links_control(self):
        # covers: BO-4300b-4
        # angle: discrimination
        """Control: the injected denial makes os.symlink fail in a child process and logs it."""
        arm = self._arm(deny=True)
        victim = arm.base / "victim"
        done = subprocess.run(  # noqa: S603
            [sys.executable, "-c",
             "import os,sys\ntry:\n os.symlink(sys.argv[1], sys.argv[2])\n"
             "except OSError as e:\n print('denied', e.errno)\n sys.exit(0)\nsys.exit(9)\n",
             str(arm.base), str(victim)],
            env=arm.world.env, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("denied", done.stdout)
        self.assertFalse(victim.is_symlink())
        self.assertEqual(len(arm.attempts()), 1)

    def test_ensure_is_ready_when_symlinks_are_denied(self):
        # covers: BO-4300b-4
        # angle: criterion
        """AC-1: with symlink creation denied, ensure answers ok, exit 0, install proven link-free."""
        arm = self._arm(deny=True)
        done, payload = arm.ensure()
        self.assertEqual(payload.get("status"), "ok", _snap(done, payload))
        self.assertEqual(done.returncode, 0, _snap(done, payload))
        self.assertEqual(payload.get("state"), "ready", _snap(done, payload))
        checks = payload.get("checks") or {}
        self.assertIs(checks.get("install_paths_regular"), True, _snap(done, payload))
        self.assertEqual([k for k, v in checks.items() if v is not True], [], checks)
        # the ensure path never even tried to make a link (decision 2)
        self.assertEqual(arm.attempts(), [])

    def test_install_and_protection_paths_are_regular_files(self):
        # covers: BO-4300b-4
        # angle: real_artifact
        """AC-2: every path under the install and the protection files is a regular file/folder."""
        arm = self._arm(deny=True)
        done, payload = arm.ensure()
        self.assertEqual(payload.get("status"), "ok", _snap(done, payload))
        ws = Path(payload["workspace_path"])
        self.assertTrue((ws / ".leafcutter" / "scripts" / "install_marker.txt").is_file())
        self.assertTrue((ws / ".pre-commit-config.yaml").is_file())
        self.assertTrue((ws / ".git" / "hooks" / "pre-commit").is_file())
        self.assertEqual(_walk_links(ws), [])
        self.assertIs((payload.get("checks") or {}).get("install_paths_regular"), True)
        # exact count: the install really has content to have inspected
        files = [p for p in (ws / ".leafcutter").rglob("*") if p.is_file()]
        self.assertEqual(len(files), 1, files)

    def test_known_bad_commit_is_rejected_when_symlinks_are_denied(self):
        # covers: BO-4300b-4
        # angle: criterion
        """AC-3: a commit of the known-bad file inside the workspace is rejected by its hook."""
        arm = self._arm(deny=True)
        done, payload = arm.ensure()
        self.assertEqual(payload.get("status"), "ok", _snap(done, payload))
        self.assertIs((payload.get("checks") or {}).get("install_paths_regular"), True)
        ws = Path(payload["workspace_path"])
        env = arm.world.env
        head = git_ok(ws, env, "rev-parse", "HEAD")
        (ws / KNOWN_BAD).write_text("def broken(:\n", encoding="utf-8")
        git_ok(ws, env, "add", "--", KNOWN_BAD)
        rejected = git(ws, env, "commit", "-m", "known bad")
        self.assertNotEqual(rejected.returncode, 0, rejected.stdout)
        self.assertIn("commit rejected", rejected.stderr)
        self.assertEqual(git_ok(ws, env, "rev-parse", "HEAD"), head)
        # control: the same commit without the hook goes through, so the rejection was the hook's
        control = git(ws, env, "commit", "--no-verify", "-m", "known bad, control")
        self.assertEqual(control.returncode, 0, control.stderr)
        self.assertNotEqual(git_ok(ws, env, "rev-parse", "HEAD"), head)

    def test_link_in_install_is_not_ready(self):
        # covers: BO-4300b-4
        # angle: failure
        """A build that leaves a file or folder link in the install is NOT_READY, never ready."""
        if not _can_make_symlinks():
            self.skipTest("this machine cannot make links: nothing to detect (not run)")
        problems = []
        for kind in ("file", "dir"):
            arm = self._arm(deny=False, link=kind)
            done, payload = arm.ensure(slug=f"linked-{kind}")
            if payload.get("code") != "NOT_READY" or payload.get("status") == "ok":
                problems.append(f"{kind}: not answered NOT_READY: {_snap(done, payload)}")
                continue
            if done.returncode == 0:
                problems.append(f"{kind}: exit 0 on a not-ready answer")
            if (payload.get("checks") or {}).get("install_paths_regular") is not False:
                problems.append(f"{kind}: checks do not name install_paths_regular False: "
                                f"{payload.get('checks')}")
            leftovers = list((arm.world.landing).glob("*")) if arm.world.landing.exists() else []
            if leftovers:
                problems.append(f"{kind}: half-made workspace left behind: {leftovers}")
        self.assertEqual(problems, [])

    def test_answers_with_and_without_link_permission_are_equivalent(self):
        # covers: BO-4300b-4
        # angle: boundary
        """AC-4: after normalising paths, timestamps and shas, the two answers and workspaces match."""
        permitted = self._arm(deny=False)
        denied = self._arm(deny=True)
        done_p, answer_p = permitted.ensure()
        done_d, answer_d = denied.ensure()
        self.assertEqual(answer_p.get("status"), "ok", _snap(done_p, answer_p))
        self.assertEqual(answer_d.get("status"), "ok", _snap(done_d, answer_d))
        self.assertIs((answer_d.get("checks") or {}).get("install_paths_regular"), True)
        self.assertIs((answer_p.get("checks") or {}).get("install_paths_regular"), True)
        self.assertEqual(done_p.returncode, done_d.returncode)
        self.assertEqual(_normalise(permitted, answer_p), _normalise(denied, answer_d))
        tree_p = _tree(Path(answer_p["workspace_path"]))
        tree_d = _tree(Path(answer_d["workspace_path"]))
        self.assertEqual(tree_p, tree_d)
        self.assertNotIn("link", set(tree_p.values()))
        self.assertGreater(len(tree_p), 3)
        _path, marker_p = find_marker(Path(answer_p["workspace_path"]))
        _path, marker_d = find_marker(Path(answer_d["workspace_path"]))
        self.assertEqual(marker_p.get("state"), marker_d.get("state"))

    def test_bo_4300b_4_reachable_from_entry_point(self):
        # covers: BO-4300b-4
        # angle: reachability
        """The deployed CLI, real argv, no --repo-root, under denial: a ready, link-free workspace."""
        arm = self._arm(deny=True)
        done, payload = run_maker(
            arm.world, ["ensure", "--kind", "feature", "--slug", "beta"],
            cwd=arm.world.project)
        self.assertEqual(payload.get("status"), "ok", _snap(done, payload))
        self.assertEqual(done.returncode, 0)
        ws = Path(payload["workspace_path"])
        # consumed in control flow: the workspace exists, its record says ready, and
        # the readiness answer that produced "ok" was the link-free proof
        self.assertTrue((ws / ".git").is_dir())
        _path, marker = find_marker(ws)
        self.assertEqual(marker.get("state"), "ready")
        self.assertIs((payload.get("checks") or {}).get("install_paths_regular"), True)
        self.assertEqual(_walk_links(ws), [])
        self.assertEqual(arm.attempts(), [])

    def test_ci_runs_this_module_on_a_windows_runner(self):
        # covers: BO-4300b-4
        # angle: criterion
        """Arm 1: ci.yml has a windows job running this module and never enables Developer Mode."""
        text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        jobs = (yaml.safe_load(text) or {}).get("jobs") or {}
        windows = {}
        for name, job in jobs.items():
            runs_on = job.get("runs-on")
            if "windows" in json.dumps(runs_on).lower():
                windows[name] = job
        self.assertEqual(len(windows) >= 1, True, f"no windows job in ci.yml jobs: {list(jobs)}")
        runners = [step.get("run", "") for job in windows.values()
                   for step in job.get("steps") or []]
        self.assertTrue(any("test_bo_4300b_4" in r for r in runners),
                        "no windows step runs unit_tests/build_orchestration/test_bo_4300b_4.py")
        blob = json.dumps(windows).lower()
        for forbidden in ("allowdevelopmentwithoutdevlicense", "developer mode", "developermode",
                          "seCreateSymbolicLinkPrivilege".lower()):
            self.assertNotIn(forbidden, blob)

    @unittest.skipUnless(sys.platform == "win32" and not _can_make_symlinks(),
                         "arm 1 not run: needs a real Windows machine without link permission")
    def test_real_windows_without_link_permission(self):
        # covers: BO-4300b-4
        # angle: real_artifact
        """Arm 1: on real Windows with no link permission, ensure is ready and link/junction-free."""
        arm = self._arm(deny=False)
        done, payload = arm.ensure()
        self.assertEqual(payload.get("status"), "ok", _snap(done, payload))
        self.assertIs((payload.get("checks") or {}).get("install_paths_regular"), True)
        self.assertEqual(_walk_links(Path(payload["workspace_path"])), [])

    @unittest.skipUnless(sys.platform == "win32", "junction check not run: Windows only")
    def test_junction_in_install_is_not_ready(self):
        # covers: BO-4300b-4
        # angle: failure
        """A directory junction in the install is NOT_READY, exactly like a symlink."""
        arm = self._arm(deny=False, link="junction")
        done, payload = arm.ensure(slug="linked-junction")
        self.assertEqual(payload.get("code"), "NOT_READY", _snap(done, payload))
        self.assertIs((payload.get("checks") or {}).get("install_paths_regular"), False)


if __name__ == "__main__":
    unittest.main()
