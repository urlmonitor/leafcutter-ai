"""
MODULE: unit_tests/commit_guardian/test_tq500g1viii_hook_deployed.py
GOAL: RED test for TQ-500g-1-viii, the DEPLOYED copy of the new hook: build.py into a temporary target, then the
    hook is in the deployed hooks manifest and the generated pre-commit config, its record module is deployed
    beside it, and the deployed hook, run by the entry pre-commit would run, blocks B2.
BUSINESS CONTEXT: A source-tree read is blind to a deploy-manifest gap (CLAUDE.md, 'New Hook / Gate Dependencies
    Must Be in the Build Deploy-Manifest'): the hook sits in <output_root>/scripts/commit_guardian and imports
    gate_verdict_records from <output_root>/scripts/build_orchestration, a layout the source tree does not have.
    The sandbox repo is the deployed target itself (git init after the build), so the hook finds the deployed
    commit_guardian.json next to it. No PYTHONPATH is given: the import must resolve from the deployed layout.
    Today the hook is in neither the manifest nor the config, so the first assertion fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

import unit_tests.commit_guardian._tq500g1viii_fixtures as fx

HOOK_ID, KEY = "check-build-epic-gate-verdicts", "07_deployed_ticket"
BUILD_PY = fx.REPO_ROOT / "scripts" / "build.py"


def _build(target: Path) -> Path:
    target.mkdir(parents=True)
    proc = subprocess.run([sys.executable, str(BUILD_PY), "--target-dir", str(target)], cwd=fx.REPO_ROOT,
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"build.py failed: {proc.stdout[-400:]!r} {proc.stderr[-400:]!r}"
    return target / ".leafcutter" / "scripts"


def test_deployed_hook_registered_and_blocks(tmp_path: Path):
    # covers: TQ-500g-1-viii
    # angle: deployed
    # must_catch: hook module or its imports missing from the deploy manifest
    target = tmp_path / "deployed"
    scripts = _build(target)
    guardian, orchestration = scripts / "commit_guardian", scripts / "build_orchestration"

    config = json.loads((guardian / "commit_guardian.json").read_text(encoding="utf-8"))
    manifest = [h for h in config["hooks_manifest"]["hooks"] if h["id"] == HOOK_ID]
    assert len(manifest) == 1, f"the deployed hooks manifest must hold exactly one {HOOK_ID}: {len(manifest)}"
    assert config.get("build_epic_gate_verdicts", {}).get("severity") == "block", config.get("build_epic_gate_verdicts")
    precommit = yaml.safe_load((target / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    wired = [h for repo in precommit["repos"] for h in repo["hooks"] if h["id"] == HOOK_ID]
    assert len(wired) == 1, f"the generated .pre-commit-config.yaml must wire {HOOK_ID} once: {len(wired)}"
    assert wired[0]["entry"].endswith("check_build_epic_gate_verdicts.py"), wired[0]["entry"]
    assert (guardian / "check_build_epic_gate_verdicts.py").is_file(), "the hook script is not deployed"
    assert (orchestration / "gate_verdict_records.py").is_file(), "gate_verdict_records.py is not deployed beside build_orchestration"

    # Run the deployed copy through the entry pre-commit would run (run_hook.py), in the target as a git repo.
    fx.git(["init", "-b", "main", "-q"], target)
    for k, v in (("user.email", "tw@example.com"), ("user.name", "Test Writer"), ("core.autocrlf", "false")):
        fx.git(["config", k, v], target)
    fx.write_bytes(target / fx.CODE, fx.CODE_V0)
    fx.write_bytes(target / fx.ticket_rel(KEY), fx.TICKET_V0)
    fx.stage(target, fx.CODE, fx.ticket_rel(KEY))
    fx.git(["commit", "-q", "-m", "base"], target)
    records = orchestration / "gate_verdict_records.py"
    fx.open_marker(target, KEY, records=records, source_tree=False)  # the deployed producer, no PYTHONPATH
    fx.stage_work(target, KEY)
    ac_id, rb_pass, _ = fx.real_red_baseline_verdicts()
    fx.write_record(target, KEY, "red_baseline", rb_pass, ids=[ac_id])  # B2: no wrong-version record
    tokens = wired[0]["entry"].split()
    assert tokens[0] == "python" and tokens[1].endswith("run_hook.py"), wired[0]["entry"]
    argv = [sys.executable, *tokens[1:]]
    proc = subprocess.run(argv, cwd=target, capture_output=True, text=True, timeout=120, env=fx.env(source_tree=False))
    text = proc.stdout + proc.stderr
    assert proc.returncode != 0 and fx.names_reason(text, r"wrong[-_ ]?version", r"missing"), (
        f"the deployed hook must block B2, naming the missing wrong-version verdict: rc={proc.returncode} {text!r}")
    assert "ModuleNotFoundError" not in text and "ImportError" not in text, f"the deployed hook could not import its record module: {text!r}"
