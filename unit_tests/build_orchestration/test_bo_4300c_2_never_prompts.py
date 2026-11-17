"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
AC: BO-4300c-2 -- the workspace maker never reads stdin and never prompts
    (also BO-4300a-1 IT13, BO-4300e-2, BO-4300f-3 IT5, ADR-018 A1.2).
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    01_TICKET-20261022-maker-never-waits-for-input.md

Proofs run against the DEPLOYED maker layout (shared locator in
_workspace_maker_fixtures.py). Git runs with an isolated global/system config.
This module never spawns scripts/build.py itself and starts the maker with its
own Popen (it does not depend on run_maker's stdin handling).

The env-builder contract the coder must satisfy: ``worktree_git.git_env()``
(no arguments) returns ``{**os.environ, "GIT_TERMINAL_PROMPT": "0",
"GCM_INTERACTIVE": "never"}`` plus ``GIT_SSH_COMMAND="ssh -o BatchMode=yes"``
only when neither GIT_SSH_COMMAND nor GIT_SSH is set in os.environ.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/01, BO-4300c-2]:
  Created the red baseline.
====================================================================
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: it re-exports builders
    deployed_maker_path,
    make_project,
)
from unit_tests.build_orchestration._workspace_maker_builders import (  # noqa: I001
    _isolated_git_env,
    _run_git,
)

_SUBPROCESS_CALLS = {"run", "Popen", "check_output", "check_call", "call"}
# (file, enclosing function) of the five child-process sites named in the ticket.
_KNOWN_SITES = {
    ("worktree_git.py", "run_git"),
    ("workspace_root.py", "_git"),
    ("worktree_identity.py", "_show_bytes"),
    ("worktree_canaries.py", "install_shims"),
    ("worktree_log_root.py", "_run_build"),
}


def _deployed_sources() -> list[Path]:
    scripts = deployed_maker_path().parent
    files = sorted(scripts.glob("worktree*.py")) + [scripts / "workspace_root.py"]
    return [f for f in files if f.is_file()]


def _subprocess_calls(path: Path):
    """Yield (enclosing function name, ast.Call) for every subprocess launch in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def walk(node, func):
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else func
            if isinstance(child, ast.Call):
                f = child.func
                if (isinstance(f, ast.Attribute) and f.attr in _SUBPROCESS_CALLS
                        and isinstance(f.value, ast.Name) and f.value.id == "subprocess"):
                    yield func, child
            yield from walk(child, name)

    yield from walk(tree, "<module>")


def _is_devnull(node: ast.expr) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "DEVNULL"
            and isinstance(node.value, ast.Name) and node.value.id == "subprocess")


def _wait_without_touching_stdin(proc: subprocess.Popen) -> tuple[str, str]:
    """Wait for exit WITHOUT writing to or closing stdin; fail if it blocks past 60 s."""
    result: dict[str, str] = {}

    def drain(stream, key):
        result[key] = stream.read()

    threads = [threading.Thread(target=drain, args=(proc.stdout, "out"), daemon=True),
               threading.Thread(target=drain, args=(proc.stderr, "err"), daemon=True)]
    for t in threads:
        t.start()
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        msg = "maker did not exit within 60 s with stdin held open (waiting for input)"
        raise AssertionError(msg) from None
    for t in threads:
        t.join(timeout=10)
    return result.get("out", ""), result.get("err", "")


class TestMakerNeverPrompts(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300c2np-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_maker_with_open_stdin_and_credential_hub_answers_once_without_prompting(self):
        # covers: BO-4300c-2
        # covers: BO-4300a-1
        # angle: deployed
        """AC-1: held-open stdin + unreachable credential hub -> one FETCH_FAILED answer, exit 2."""
        proj = make_project(self.tmp)
        _run_git(["remote", "set-url", "origin", "https://127.0.0.1:9/x.git"], proj["project"])
        maker = deployed_maker_path()
        proc = subprocess.Popen(
            [sys.executable, str(maker), "ensure", "--kind", "scratch", "--slug", "np"],
            cwd=str(proj["project"]),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=_isolated_git_env(),
        )
        try:
            out, err = _wait_without_touching_stdin(proc)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if proc.stdin:
                proc.stdin.close()
        lines = [ln for ln in out.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"expected one JSON line, got {out!r} / stderr {err!r}")
        answer = json.loads(lines[0])
        self.assertEqual(answer.get("code"), "FETCH_FAILED", answer)
        self.assertEqual(proc.returncode, 2, answer)

    def test_every_maker_child_process_closes_stdin(self):
        # covers: BO-4300c-2
        # covers: BO-4300e-2
        # covers: BO-4300f-3
        # angle: deployed
        """AC-2: every subprocess launch in the deployed maker files passes stdin=subprocess.DEVNULL."""
        seen_sites = set()
        offenders = []
        for path in _deployed_sources():
            for func, call in _subprocess_calls(path):
                seen_sites.add((path.name, func))
                kw = {k.arg: k.value for k in call.keywords if k.arg}
                if "stdin" not in kw or not _is_devnull(kw["stdin"]):
                    offenders.append(f"{path.name}:{call.lineno} in {func}")
        self.assertLessEqual(_KNOWN_SITES, seen_sites, "a named child-process site was not found")
        self.assertEqual(offenders, [], f"subprocess calls without stdin=subprocess.DEVNULL: {offenders}")

    def test_git_sites_carry_the_no_prompt_environment(self):
        # covers: BO-4300c-2
        # angle: criterion
        """AC-2: each site passes env= and its file carries GIT_TERMINAL_PROMPT (or the git_env helper)."""
        problems = []
        for path in _deployed_sources():
            calls = list(_subprocess_calls(path))
            if not calls:
                continue
            text = path.read_text(encoding="utf-8")
            if "GIT_TERMINAL_PROMPT" not in text and "git_env" not in text:
                problems.append(f"{path.name}: no GIT_TERMINAL_PROMPT / git_env")
            for func, call in calls:
                if not any(k.arg == "env" for k in call.keywords):
                    problems.append(f"{path.name}:{call.lineno} in {func}: no env=")
        self.assertEqual(problems, [])
        scripts = deployed_maker_path().parent
        self.assertIn("GIT_TERMINAL_PROMPT", (scripts / "worktree_git.py").read_text(encoding="utf-8"))
        self.assertIn("GIT_TERMINAL_PROMPT", (scripts / "workspace_root.py").read_text(encoding="utf-8"))

    def _env_of(self, caller_env: dict[str, str]) -> dict[str, str]:
        """Call the DEPLOYED worktree_git.git_env() in a fresh subprocess with *caller_env* applied."""
        scripts = deployed_maker_path().parent
        code = (
            "import json, sys\n"
            f"sys.path.insert(0, {str(scripts)!r})\n"
            "import worktree_git\n"
            "print(json.dumps(worktree_git.git_env()))\n"
        )
        env = {k: v for k, v in os.environ.items() if k not in ("GIT_SSH", "GIT_SSH_COMMAND")}
        env.update(caller_env)
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              env=env, timeout=60, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_git_env_disables_prompts_and_adds_batchmode_when_no_ssh_command(self):
        # covers: BO-4300c-2
        # angle: criterion
        """AC-3: no caller SSH command -> prompts off and BatchMode=yes added."""
        env = self._env_of({})
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GCM_INTERACTIVE"], "never")
        self.assertEqual(env["GIT_SSH_COMMAND"], "ssh -o BatchMode=yes")

    def test_git_env_keeps_user_ssh_command_byte_identical(self):
        # covers: BO-4300c-2
        # angle: failure
        """AC-3: a caller's GIT_SSH_COMMAND is never overridden or extended."""
        mine = "ssh -i  /my/key -o StrictHostKeyChecking=no"
        env = self._env_of({"GIT_SSH_COMMAND": mine})
        self.assertEqual(env["GIT_SSH_COMMAND"], mine)
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")

    def test_git_env_adds_no_batchmode_when_git_ssh_is_set(self):
        # covers: BO-4300c-2
        # angle: boundary
        """AC-3: GIT_SSH set (and no GIT_SSH_COMMAND) -> no GIT_SSH_COMMAND is invented."""
        env = self._env_of({"GIT_SSH": "/usr/bin/my-ssh"})
        self.assertEqual(env["GIT_SSH"], "/usr/bin/my-ssh")
        self.assertNotIn("GIT_SSH_COMMAND", env)
        self.assertEqual(env["GCM_INTERACTIVE"], "never")

    def _both_envs(self, global_config_text: str) -> tuple[dict[str, str], dict[str, str]]:
        """Return (worktree_git.git_env(), workspace_root._git_env()) from the DEPLOYED modules.

        Runs in a fresh subprocess with an isolated GIT_CONFIG_GLOBAL file holding
        *global_config_text*, GIT_CONFIG_NOSYSTEM=1, and GIT_SSH/GIT_SSH_COMMAND unset.
        ``ssh_command_configured.cache_clear()`` is called in the child before each
        builder so one case can never leak into another.
        """
        scripts = deployed_maker_path().parent
        cfg = self.tmp / "gitconfig"
        cfg.write_text(global_config_text, encoding="utf-8")
        cwd = self.tmp / "not-a-repo"
        cwd.mkdir(exist_ok=True)
        code = (
            "import json, sys\n"
            f"sys.path.insert(0, {str(scripts)!r})\n"
            "import workspace_root, worktree_git\n"
            "workspace_root.ssh_command_configured.cache_clear()\n"
            "a = worktree_git.git_env()\n"
            "workspace_root.ssh_command_configured.cache_clear()\n"
            "b = workspace_root._git_env()\n"
            "workspace_root.ssh_command_configured.cache_clear()\n"
            "print(json.dumps([a, b]))\n"
        )
        env = {k: v for k, v in os.environ.items() if k not in ("GIT_SSH", "GIT_SSH_COMMAND")}
        env["GIT_CONFIG_GLOBAL"] = str(cfg)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              env=env, cwd=str(cwd), timeout=60, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        a, b = json.loads(proc.stdout)
        return a, b

    def test_core_ssh_command_in_git_config_suppresses_batchmode_in_both_builders(self):
        # covers: BO-4300c-2
        # angle: failure
        """Guard: core.sshCommand configured -> neither builder invents GIT_SSH_COMMAND; empty config -> both add it."""
        configured = self._both_envs('[core]\n\tsshCommand = ssh -i /my/key\n')
        for name, env in zip(("worktree_git.git_env", "workspace_root._git_env"), configured):
            self.assertNotIn("GIT_SSH_COMMAND", env, f"{name} overrode core.sshCommand")
        empty = self._both_envs("")
        for name, env in zip(("worktree_git.git_env", "workspace_root._git_env"), empty):
            self.assertEqual(env.get("GIT_SSH_COMMAND"), "ssh -o BatchMode=yes", name)

    def test_the_two_git_env_copies_agree_on_prompt_and_ssh_keys(self):
        # covers: BO-4300c-2
        # angle: seam
        """Guard: workspace_root._git_env and worktree_git.git_env must not drift apart."""
        keys = ("GIT_TERMINAL_PROMPT", "GCM_INTERACTIVE", "GIT_SSH_COMMAND")
        for label, text in (("empty config", ""), ("core.sshCommand set", '[core]\n\tsshCommand = ssh -i /k\n')):
            a, b = self._both_envs(text)
            self.assertEqual({k: a.get(k) for k in keys}, {k: b.get(k) for k in keys}, label)
            self.assertEqual(a["GIT_TERMINAL_PROMPT"], "0", label)
            self.assertEqual(a["GCM_INTERACTIVE"], "never", label)


if __name__ == "__main__":
    unittest.main()
