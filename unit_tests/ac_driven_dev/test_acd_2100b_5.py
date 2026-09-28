"""
MODULE: test_acd_2100b_5
GOAL: Behavioral tests for ACD-2100b-5 -- "The startup check reads the registry
    itself instead of asking an agent to read it" -- SCRIPT-LEVEL half.

    This file covers the three test_spec entries whose `target_dir` is
    `unit_tests/ac_driven_dev/`: the pre-flight script itself, run as a real
    subprocess against a real, on-disk, repository-anchored registry. The
    companion WORKFLOW-level tests (driving templates/workflows-js/
    plan-feature.js through the E2 harness) live in
    unit_tests/workflows/test_acd_2100b_5.py.

SURFACE CHANGE (read before touching this file): ACD-2100b-5's own AC YAML
    (docs/acceptance-criteria/ac-driven-dev/ACD-2100-entry-point-unblocked/
    ACD-2100b-5.yaml) was amended in place on 2026-09-07 ("SURFACE CHANGE --
    THE CHECK MOVES TO THE SKILL PRE-FLIGHT") after a prior build attempt on
    this exact ticket ran aground on the E2 engine's sandboxing (ADR-030): the
    workflow body has no filesystem primitive, so "the check reads the
    registry itself" is unimplementable INSIDE templates/workflows-js/
    plan-feature.js. The corrected design moves the local read to a new,
    real, executable script that the plan-feature SKILL invokes BEFORE the
    workflow starts (the skill runs in the main agent loop, with real
    Bash/Read access) -- the same pattern SKILL.md sec-PRR already uses for
    scripts/ac_store/scan_ac_orphans.py. The verdict then crosses into the
    workflow through `args` (the only injected global that carries
    caller-supplied data). Any earlier test file in this repo written against
    the pre-amendment "the workflow itself reads the file" design is stale
    relative to this AC and must be reconciled to this contract (Source-of-
    Truth Discipline Rule 1: production_drift/consumer_drift -- here the AC
    itself moved, so both the eventual implementation and any existing tests
    written under the old design are the stale side, not the AC).

CONTRACT THIS FILE PINS (read it_requirements in the AC YAML for the full
    rationale; this is the concrete shape python-coder must implement):

    Script:  scripts/worktree/check_workspace_setup_permission.py
             (doc_links: "creates", "New primary landing site").
    CLI:     python3 check_workspace_setup_permission.py [--agent-id ID]
             --agent-id defaults to "worktree-agent" (the same fallback
             plan-feature.js's own workspaceSetupAgentId already uses).
             NO --registry-path override: "The registry-location semantics
             must not fork ... rather than a second, independent,
             cwd-relative resolution" (it_requirements). The script resolves
             the registry the SAME repository-anchored way ACD-2100a-1 /
             ACD-2100a-3 already established (git-common-dir based), driven
             purely by the process's cwd -- so these tests set `cwd` to a
             real git repository rather than passing a path flag.
    Output:  exactly one JSON object on stdout, exit code 0, with at least:
               - "permits": bool
               - "outcome": one of "granted", "read_failure", "parse_failure",
                            "agent_not_found", "no_entries_collection",
                            "permission_denied"
             This file only asserts the GRANTED case's shape (permits=True);
             the denial vocabulary is exercised by the WORKFLOW-level failure
             test in unit_tests/workflows/test_acd_2100b_5.py, which consumes
             this same script's real output for a denying registry.
    Args:    the skill passes this script's own stdout JSON through, verbatim,
             as `args.workspace_setup_permission` when it invokes the
             workflow -- see unit_tests/workflows/test_acd_2100b_5.py.

TDD note: scripts/worktree/check_workspace_setup_permission.py does not exist
    yet. Every test below is expected to be RED (FileNotFoundError-shaped: a
    non-zero subprocess exit and/or empty stdout) until python-coder creates it.

TICKET: 12_TICKET-20260826-ACD-2100b-5.md
AC: ACD-2100b-5
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PREFLIGHT_SCRIPT = (
    _WORKTREE_ROOT / "scripts" / "worktree" / "check_workspace_setup_permission.py"
)
_SCRIPTS_DIR = _WORKTREE_ROOT / "scripts"

_TIMEOUT = 20  # seconds; real git I/O only, no network, no dispatch.
_DEFAULT_AGENT_ID = "worktree-agent"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_registry_repo(tmp_path: Path, *, agents: list[dict] | None) -> Path:
    """Build a REAL git repository ("the project") whose
    `.leafcutter/config/agent_registry.json` is a REAL, on-disk file produced
    by `json.dumps` (the real serializer for this format), never a hand-typed
    JSON literal -- Fixture Authenticity Rule (2h.2).

    `agents=None` means the file is written with an `agents` key holding an
    empty list (no agent listed at all).
    """
    repo_dir = tmp_path / "project"
    repo_dir.mkdir(parents=True)
    _run(["git", "init", "-b", "main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test"])
    (repo_dir / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "seed"])

    registry_path = repo_dir / ".leafcutter" / "config" / "agent_registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps({"agents": agents if agents is not None else []}),
        encoding="utf-8",
    )
    return repo_dir


def _run_preflight(script_path: Path, cwd: Path, agent_id: str = _DEFAULT_AGENT_ID):
    """Invoke the pre-flight script as a real subprocess, fresh process, no
    agent dispatch, no network -- the "surface_invoked" the AC's test_spec
    names for the criterion/seam tests below.
    """
    return subprocess.run(
        [sys.executable, str(script_path), "--agent-id", agent_id],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )


def _parse_stdout_json(proc: subprocess.CompletedProcess) -> dict:
    if not proc.stdout.strip():
        raise AssertionError(
            "Pre-flight script produced no stdout at all.\n"
            f"returncode={proc.returncode}\nstderr={proc.stderr[:2000]!r}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Pre-flight script produced non-JSON stdout: {exc}\n"
            f"stdout={proc.stdout[:2000]!r}\nstderr={proc.stderr[:2000]!r}"
        ) from exc


class TestPreflightScriptCriterionAndSeam(unittest.TestCase):

    def test_preflight_returns_the_permitted_verdict_from_the_registry_alone(self):
        # covers: ACD-2100b-5
        # angle: criterion
        """AC-1/AC-2: with no agent dispatch reachable and no network, the
        pre-flight script -- executed as a subprocess in a fresh process,
        against a temporary repository whose config/agent_registry.json lists
        the worktree-creation agent with permission to run repository
        commands -- emits the permitted verdict from the registry file alone.
        """
        if not _PREFLIGHT_SCRIPT.is_file():
            self.fail(
                f"Pre-flight script does not exist yet at {_PREFLIGHT_SCRIPT}. "
                "AC ACD-2100b-5 requires scripts/worktree/"
                "check_workspace_setup_permission.py to exist as a real, "
                "executable pre-flight."
            )

        with tempfile.TemporaryDirectory(prefix="acd2100b5_script_criterion_") as tmp:
            repo_dir = _make_registry_repo(
                Path(tmp),
                agents=[{"id": _DEFAULT_AGENT_ID, "permits_shell": True}],
            )
            proc = _run_preflight(_PREFLIGHT_SCRIPT, repo_dir)

            self.assertEqual(
                proc.returncode,
                0,
                "Pre-flight script exited non-zero for a registry that "
                f"permits the agent. stdout={proc.stdout!r} stderr={proc.stderr!r}",
            )
            payload = _parse_stdout_json(proc)
            self.assertIsInstance(
                payload, dict, f"Pre-flight stdout did not parse to a JSON object: {payload!r}"
            )
            self.assertIn(
                "permits",
                payload,
                f"Pre-flight verdict is missing the required 'permits' field: {payload!r}",
            )
            self.assertIs(
                payload["permits"],
                True,
                "Pre-flight did not report permits=True for a registry that "
                f"lists '{_DEFAULT_AGENT_ID}' with permits_shell=True. verdict={payload!r}",
            )

    def test_verdict_is_identical_with_and_without_dispatch_available(self):
        # covers: ACD-2100b-5
        # angle: seam
        """AC-2/AC-4: the pre-flight script, run TWICE against the exact same
        on-disk registry -- once in an environment with no agent transport
        configured at all, once with a normal environment -- must produce the
        identical verdict both times. The check makes no agent dispatch and
        no network call in either run, so the verdict must be a pure function
        of the registry's contents, never of whether a transport happens to
        be available. This is the check that stops the fix from being "skip
        the check (default to permitted) when dispatch is unavailable".
        """
        if not _PREFLIGHT_SCRIPT.is_file():
            self.fail(
                f"Pre-flight script does not exist yet at {_PREFLIGHT_SCRIPT}."
            )

        with tempfile.TemporaryDirectory(prefix="acd2100b5_script_seam_") as tmp:
            # A DENYING registry (not merely a permitting one) is the sharper
            # proof: a permitted default masquerading as "always permitted"
            # would still look identical across both runs on a permitting
            # fixture, but would diverge (or never diverge, by coincidence)
            # on a denying one.
            repo_dir = _make_registry_repo(
                Path(tmp),
                agents=[{"id": _DEFAULT_AGENT_ID, "permits_shell": False}],
            )

            proc_a = _run_preflight(_PREFLIGHT_SCRIPT, repo_dir)
            payload_a = _parse_stdout_json(proc_a)

            # Second run: simulate "dispatch impossible" by stripping any
            # network/agent-transport-shaped environment variables a real
            # transport might read -- proving by direct execution (not by
            # assertion about the source) that the verdict does not consult
            # them. The script must never make a network call in the first
            # place, so this run should be indistinguishable from the first.
            stripped_env = {
                k: v
                for k, v in __import__("os").environ.items()
                if "ANTHROPIC" not in k.upper() and "API_KEY" not in k.upper()
            }
            proc_b = subprocess.run(
                [sys.executable, str(_PREFLIGHT_SCRIPT), "--agent-id", _DEFAULT_AGENT_ID],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                env=stripped_env,
            )
            payload_b = _parse_stdout_json(proc_b)

            self.assertIs(
                payload_a.get("permits"),
                False,
                f"Test construction error: first run did not deny. verdict={payload_a!r}",
            )
            self.assertEqual(
                payload_a,
                payload_b,
                "The pre-flight produced DIFFERENT verdicts for the identical "
                "on-disk registry across two runs (one with a stripped "
                "transport-shaped environment) -- the verdict must be a pure "
                f"function of the registry's contents.\nrun_a={payload_a!r}\n"
                f"run_b={payload_b!r}",
            )


class TestPreflightScriptDeployedLayout(unittest.TestCase):

    def test_preflight_is_reachable_and_runnable_from_the_deployed_layout(self):
        # covers: ACD-2100b-5
        # angle: deployed
        """AC-1: the pre-flight exists at the DEPLOYED path and produces a
        verdict when run there. A source-tree-only script would pass every
        other test in this set and still fail on first real use, because the
        skill invokes the DEPLOYED copy, not the repository source tree
        (it_requirements: "A new script under scripts/ that the DEPLOYED
        skill invokes must be added to the build deploy manifest in the same
        change.").

        Real-artifact behavioral test (BP-1100f-2): runs the REAL build.py
        into a fresh temporary target directory and exercises the DEPLOYED
        copy of the file -- never the source-tree copy.
        """
        if str(_SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS_DIR))
        import build as _build  # noqa: E402 — after sys.path setup

        with tempfile.TemporaryDirectory(prefix="acd2100b5_deployed_") as tmp:
            target_dir = Path(tmp) / "consumer"
            target_dir.mkdir(parents=True)

            exit_code = _build.main(["--target-dir", str(target_dir)])
            self.assertEqual(
                exit_code,
                0,
                f"build.py --target-dir exited {exit_code!r}; expected 0. "
                "The deployed-layout assertions below cannot run against a "
                "failed build.",
            )

            candidates = [
                p
                for p in target_dir.rglob("check_workspace_setup_permission.py")
            ]
            self.assertTrue(
                candidates,
                "No deployed copy of check_workspace_setup_permission.py was "
                f"found anywhere under {target_dir} after a real build.py run. "
                "AC ACD-2100b-5's it_requirements: 'A new script under "
                "scripts/ that the DEPLOYED skill invokes must be added to "
                "the build deploy manifest in the same change.' Add "
                "scripts/worktree/check_workspace_setup_permission.py to the "
                "appropriate deploy_map in scripts/build_phases.py.",
            )

            deployed_script = candidates[0]
            self.assertIn(
                str(Path("scripts") / "worktree"),
                str(deployed_script.relative_to(target_dir)),
                "The deployed pre-flight script was found, but not under a "
                f"scripts/worktree/ path (found at {deployed_script}). The "
                "skill invokes it at a specific relative path; a script "
                "deployed to the wrong location still fails on first real use.",
            )

            # Run the DEPLOYED copy (not the source-tree one) against a real,
            # permitting registry, exactly as the skill would.
            with tempfile.TemporaryDirectory(prefix="acd2100b5_deployed_repo_") as tmp2:
                repo_dir = _make_registry_repo(
                    Path(tmp2),
                    agents=[{"id": _DEFAULT_AGENT_ID, "permits_shell": True}],
                )
                proc = _run_preflight(deployed_script, repo_dir)

                self.assertEqual(
                    proc.returncode,
                    0,
                    "The DEPLOYED pre-flight script exited non-zero when run "
                    f"from its deployed location {deployed_script}. "
                    f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
                )
                payload = _parse_stdout_json(proc)
                self.assertIs(
                    payload.get("permits"),
                    True,
                    "The DEPLOYED pre-flight script did not produce a "
                    f"permitted verdict when run from its deployed location. "
                    f"verdict={payload!r}",
                )


if __name__ == "__main__":
    unittest.main()
