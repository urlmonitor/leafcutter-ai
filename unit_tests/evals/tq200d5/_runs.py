"""MODULE: unit_tests/evals/tq200d5/_runs.py

GOAL: Run whole eval runs (``run_agent_eval.main`` with real argv) of a label, an artifact and a produced-tests
    agent against the fake claude of ``_fake.py``, for the tests of TQ-200d-5-i and TQ-200d-5-iii that read the
    written results file, the exit status and what the run printed.
ARCHITECTURE: ``run`` writes a throwaway config and eval set (absolute paths), installs the fake with a
    plan of outcomes, and calls ``main``. Artifact runs patch the product-truth store plumbing (sandbox copy,
    generator, validator) because only the agent launch is under test. Produced-tests runs use the real
    test-runner template, fixtures and gold transcript, so a row that starts really is scored.
"""

from __future__ import annotations

import copy
import json
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import unit_tests.evals.tq200d5._fake as fk

KINDS = ("label", "artifact", "produced", "produced-plain")
GOLD_TRANSCRIPT = fk.EVALS / "sets" / "test-runner" / "recorded" / "configured-database" / "transcript.jsonl"
LABEL_REPLY = json.dumps({"is_error": False, "result": json.dumps({"needs_flow": True})})


@dataclass
class Run:
    """What one ``main`` call did."""

    code: int
    payload: dict | None
    fake: fk.Fake
    printed: list[str] = field(default_factory=list)
    logged: list[tuple[int, str]] = field(default_factory=list)

    @property
    def rows(self) -> list[dict]:
        return (self.payload or {}).get("rows", [])

    def stop_lines(self) -> list[str]:
        """Lines the run printed, and log records of level ERROR or above."""
        return [*self.printed, *(m for lvl, m in self.logged if lvl >= logging.ERROR)]


def ok_reply(kind: str) -> dict:
    """An outcome in which the agent starts and answers well."""
    if kind == "label":
        return fk.ok(LABEL_REPLY)
    return fk.ok(stdout_file=GOLD_TRANSCRIPT) if kind == "produced" else fk.ok()


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8", newline="\n")
    return str(path)


def agent_config(kind: str, tmp: Path, rows: int, threshold: float) -> dict:
    """The config entry for *kind* plus its eval set and template written under *tmp*."""
    template = _write(tmp / "template.md", "You are the agent under test.\nAnswer briefly.\n")
    if kind == "label":
        lines = [{"id": f"r{i}", "request": f"request {i}", "expected": {"needs_flow": True}} for i in range(1, rows + 1)]
        base = {"scoring_mode": "label", "input_field": "request", "expected_field": "expected", "model": "haiku",
                "label_axes": ["needs_flow"], "threshold": threshold}
    elif kind == "artifact":
        lines = [{"id": f"a{i}", "input": f"make artifact {i}", "expected": {"negative": i == rows, "assertions": [], "gold_target": "gold.json"}}
                 for i in range(1, rows + 1)]
        base = {"scoring_mode": "artifact", "artifact_type": "mock", "input_field": "input", "expected_field": "expected",
                "model": "haiku", "tools": "Read,Write", "sandbox_copy": [], "timeout": 30, "threshold": threshold}
    else:
        real = json.loads((fk.EVALS / "agent_eval_config.json").read_text(encoding="utf-8"))["agents"]["test-runner"]
        row = json.loads(next(iter((fk.EVALS / "sets" / "test-runner.jsonl").read_text(encoding="utf-8").splitlines())))
        lines = []
        for i in range(1, rows + 1):
            line = copy.deepcopy(row)
            line["id"] = f"p{i}"
            line["expected"]["negative"] = i == rows
            lines.append(line)
        base = copy.deepcopy(real)
        base.update(threshold=threshold, timeout=30, capture_transcript=kind == "produced")
        template = str(fk.REPO / real["template"])
    eval_set = _write(tmp / "eval.jsonl", "".join(json.dumps(line) + "\n" for line in lines))
    return {**base, "template": template, "eval_set": eval_set, "triggers": []}


def _patch_artifact_store(monkeypatch) -> None:
    ev = fk.module("run_agent_eval")

    def make_sandbox(_repo_root, _copy_dirs):
        box = Path(tempfile.mkdtemp(prefix="lc_eval_"))
        (box / "docs" / "product-truth").mkdir(parents=True)
        (box / "docs" / "product-truth" / "index.json").write_text(json.dumps({"entity_registry": []}), encoding="utf-8")
        return box

    monkeypatch.setattr(ev, "make_sandbox", make_sandbox)
    monkeypatch.setattr(ev, "reconcile_store", lambda *_a, **_k: None)
    monkeypatch.setattr(ev, "validator_errors", lambda *_a, **_k: set())
    monkeypatch.setattr(ev, "normalize_baseline_registry", lambda *_a, **_k: None)


def run(kind: str, tmp_path: Path, monkeypatch, capsys, caplog, plan: list[dict], *, rows: int = 8, threshold: float = 0.5,
        before=None, args: tuple[str, ...] = (), repo_root: Path | None = None) -> Run:
    """Start ``run_agent_eval.main`` for a *kind* agent of *rows* rows with the fake claude following *plan*.

    *before(monkeypatch)* runs after the fake is in place and before the run (a platform, a PATH, a setting).
    With *repo_root* the run is given no ``--results-file``: it writes where it would by default, under that root.
    """
    fake = fk.setup(tmp_path, monkeypatch, plan)
    if before is not None:
        before(monkeypatch)
    if kind == "artifact":
        _patch_artifact_store(monkeypatch)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    config = cfg_dir / "config.json"
    config.write_text(json.dumps({"agents": {"agent-x": agent_config(kind, cfg_dir, rows, threshold)}}), encoding="utf-8")
    results = tmp_path / "results.json"
    caplog.set_level(logging.DEBUG)
    ev = fk.module("run_agent_eval")
    where = ["--results-file", str(results)]
    if repo_root is not None:
        monkeypatch.setattr(ev, "find_repo_root", lambda: repo_root)
        where = []
    code = ev.main(["--agent", "agent-x", "--config", str(config), *where, "--timeout", "30", *args])
    seen = capsys.readouterr()
    payload = json.loads(results.read_text(encoding="utf-8")) if results.is_file() else None
    return Run(code, payload, fake, (seen.out + seen.err).splitlines(), [(r.levelno, r.getMessage()) for r in caplog.records])


def launch_text(result: Run) -> str:
    """The launch-failure text a results file carries: the harness_failure detail, else the first row's error."""
    payload = result.payload or {}
    if "harness_failure" in payload:
        return payload["harness_failure"]["detail"]
    row = result.rows[0]
    return row.get("parse_error") or row.get("error") or ""
