"""CLI operational failures are JSON results, not tracebacks or empty success."""

import importlib
import json
import pytest


@pytest.mark.parametrize("fault", ["backend", "missing_sdk"])
def test_cli_reports_typed_nonzero_failure(monkeypatch, capsys, fault):
    # covers: KM-400e-4
    # angle: reachability
    cli = importlib.import_module("knowledge.__main__")
    errors = importlib.import_module("knowledge.errors")

    def unavailable(config):
        if fault == "missing_sdk":
            raise ModuleNotFoundError("neo4j")
        raise errors.BackendUnavailable()

    monkeypatch.setattr(cli, "build_retriever", unavailable)
    monkeypatch.setattr("sys.argv", ["knowledge", "capabilities", "--backend", "neo4j"])
    assert cli.main() != 0
    output = json.loads(capsys.readouterr().err)
    assert output["status"] == "unavailable"
    assert "Traceback" not in str(output)
