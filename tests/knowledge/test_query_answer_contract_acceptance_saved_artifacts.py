"""Exercise public consumers of real saved local evaluation and Neo4j artifacts.

The historical executions are not rerun here, and local artifacts do not claim
real-model quality, remote tracing, deployment or representative coverage.
"""
import json
import subprocess
import sys

from tests.knowledge.query_answer_contract_acceptance_support import ROOT


def test_saved_evaluation_report_cold_consumer_preserves_limited_and_invalidated_states(tmp_path):
    # covers: KM-500d-3
    # angle: real_artifact
    # angle: reachability
    # angle: criterion
    baseline = ROOT / "reports/knowledge-answer-evaluation.json"
    saved = json.loads(baseline.read_text(encoding="utf-8"))
    assert saved["denominators"] == {"total": 12, "executed": 12, "passed": 12, "failed": 0, "not_run": 0}
    assert saved["coverage"]["representative"] is False
    assert saved["coverage"]["families"] == 6 and saved["coverage"]["total_families"] == 8
    def compare(proposal, gates=None):
        command = [sys.executable, "-m", "knowledge", "compare", "--baseline", str(baseline), "--proposal", str(proposal)]
        if gates is not None:
            command += ["--gates", str(gates)]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert process.returncode == 0, process.stderr
        return json.loads(process.stdout)
    missing = compare(baseline)
    assert missing["status"] == "not_run" and missing["promotion"] == "blocked"
    gates = tmp_path / "controlled-artifact-comparison-gates.json"
    gates.write_text(json.dumps({"baseline_review_fingerprint": saved["review_fingerprint"],
        "min_pass_rate": 1, "max_p95_latency_ms": 1000000, "min_executed_cases": 12}), encoding="utf-8")
    limited = compare(baseline, gates)
    assert limited["status"] == "evaluated" and limited["promotion"] == "limited"
    assert limited["automatic_activation"] is False and limited["model_weight_training"] is False
    changed = tmp_path / "controlled-changed-source-report.json"
    changed.write_text(json.dumps({**saved, "source_sha": "b" * 40}), encoding="utf-8")
    rejected = compare(changed, gates)
    assert rejected["status"] == "invalidated" and rejected["promotion"] == "blocked"


def test_saved_actual_dependency_outputs_reach_public_comparison_and_reject_slices(monkeypatch, tmp_path, capsys):
    # covers: KM-500f-1
    # angle: reachability
    # angle: criterion
    # angle: seam
    # angle: discrimination
    # angle: real_artifact
    saved = json.loads((ROOT / "reports/knowledge-answer-impact.json").read_text(encoding="utf-8"))
    before, after = saved["before"], saved["after"]
    repository = after["evidence"][0]["entity"]["source"]["repository_id"]
    packet = {"kind": "impact", "repository_id": repository, "source_sha": after["source_sha"],
              "evidence": [], "before": before, "after": after}
    # Invoke actual argv/main consumer with the report's own repository scope.
    from knowledge import __main__ as cli
    def call(value):
        path = tmp_path / "actual-dependency-comparison.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["knowledge", "assess", "--repository-id", repository, "--request", str(path)])
        code = cli.main()
        output = json.loads(capsys.readouterr().out)
        assert code == 0
        return output
    result = call(packet)
    assert result["status"] == "fulfilled"
    assert result["before_sha"] == saved["source_revision_before"]
    assert result["after_sha"] == saved["source_revision_after"]
    assert result["added"] == [] and result["removed"] == []
    assert result["complete_code_impact"] is False
    for incomplete in [saved["partial"], saved["dependency_pages"][-1]]:
        output = call({**packet, "after": incomplete})
        assert output["status"] == "unresolved"
        assert output["added"] is None and output["removed"] is None
