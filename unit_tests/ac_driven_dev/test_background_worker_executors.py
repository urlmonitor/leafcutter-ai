"""Behavioral contracts for sandboxed local and SDK executor boundaries."""

import json
import subprocess

import pytest

from scripts.background_worker.executors import (
    ExecutorError,
    LocalCodexExecutor,
    SDKReviewer,
    validate_review,
    check_evidence,
)


def test_local_checks_do_not_inherit_provider_or_host_credentials(tmp_path, monkeypatch):
    # covers: ACD-1300g-1, ACD-1300b-1
    monkeypatch.setenv("GH_TOKEN", "must-not-leak")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "must-not-leak")
    monkeypatch.setenv("CUSTOM_PASSWORD", "must-not-leak")
    calls = []
    executor = LocalCodexExecutor(
        {"model": "qwen3.5:9b"}, invoke=lambda *args, **kwargs: calls.append(kwargs)
    )
    executor.check(tmp_path, ["python", "check.py"], timeout=10)
    assert not any("must-not-leak" == value for value in calls[0]["env"].values())
    assert "CODEX_HOME" in calls[0]["env"]
    assert calls[0]["env"]["AC_ENFORCE_STRICT"] == "1"


def test_masked_ac_failure_cannot_become_positive_check_evidence():
    # covers: ACD-1300g-2
    output = 'AC-ENFORCEMENT [MASKED FAILURE]\n9 passed in 0.5s\n'
    with pytest.raises(ExecutorError):
        check_evidence(["python", "-m", "pytest"], subprocess.CompletedProcess([], 0, output, ""))


@pytest.mark.parametrize(
    "stdout", ["", "Everything fine", '{"leafcutter_check":{"inspected":0,"passed":true}}']
)
def test_success_exit_without_positive_inspection_is_rejected(stdout):
    # covers: ACD-1300g-2
    with pytest.raises(ExecutorError, match="inspected-item"):
        check_evidence(["custom-check"], subprocess.CompletedProcess([], 0, stdout, ""))


@pytest.mark.parametrize(
    "final",
    [
        '{"leafcutter_check":{"inspected":0,"passed":false}}',
        '{"leafcutter_check":1}',
        '{"leafcutter_check":null}',
        '{"leafcutter_check":{"inspected":true,"passed":true}}',
        '{"leafcutter_check":',
        "trailing non-envelope text",
    ],
)
def test_final_check_envelope_overrides_prior_success_and_pytest_fallback(final):
    # covers: ACD-1300g-2
    output = (
        '7 passed in 0.5s\n{"leafcutter_check":{"inspected":1,"passed":true}}\n' + final + "\n\n"
    )
    with pytest.raises(ExecutorError, match="inspected-item"):
        check_evidence(["python", "-m", "pytest"], subprocess.CompletedProcess([], 0, output, ""))


def test_final_check_envelope_is_authoritative_and_preserves_its_count():
    # covers: ACD-1300g-2
    output = '{"leafcutter_check":{"inspected":99,"passed":true}}\n{"leafcutter_check":{"inspected":2,"passed":true}}\n'
    assert (
        check_evidence(["custom"], subprocess.CompletedProcess([], 0, output, ""))["inspected"] == 2
    )


@pytest.mark.parametrize(
    "argv,stdout",
    [
        (["python", "-m", "pytest"], "====== 7 passed in 0.5s ======"),
        (["custom"], '{"leafcutter_check":{"inspected":7,"passed":true}}'),
    ],
)
def test_positive_inspection_preserves_safe_output(argv, stdout):
    # covers: ACD-1300g-2
    evidence = check_evidence(argv, subprocess.CompletedProcess(argv, 0, stdout, "diagnostic"))
    assert (
        evidence["inspected"] == 7
        and evidence["stdout"] == stdout
        and evidence["stderr"] == "diagnostic"
    )


@pytest.mark.parametrize(
    "outcome",
    [
        {"status": "completed", "questions": []},
        {"status": "needs_input", "questions": ["Which target?"]},
    ],
)
def test_local_harness_requires_and_parses_structured_outcome(tmp_path, outcome):
    # covers: ACD-1300g-1, ACD-1300c-1
    events = [
        {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(outcome)}},
        {"type": "turn.completed"},
    ]

    def invoke(argv, **kwargs):
        assert "--output-schema" in argv
        return subprocess.CompletedProcess(
            argv, 0, "\n".join(json.dumps(event) for event in events), ""
        )

    result = LocalCodexExecutor({"model": "qwen3.5:9b"}, invoke=invoke).implement(
        tmp_path, "context", timeout=10
    )
    assert result["status"] == outcome["status"] and result["questions"] == outcome["questions"]


def test_plain_question_text_is_not_a_completed_implementation(tmp_path):
    # covers: ACD-1300g-1-i
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "What should I do?"}},
        {"type": "turn.completed"},
    ]

    def invoke(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv, 0, "\n".join(json.dumps(event) for event in events), ""
        )

    with pytest.raises(ExecutorError, match="structured"):
        LocalCodexExecutor({"model": "qwen3.5:9b"}, invoke=invoke).implement(
            tmp_path, "context", timeout=10
        )


def test_local_command_pins_oss_sandbox_and_disables_nested_agents(tmp_path):
    # covers: ACD-1300g-1, ACD-1300b-2, ACD-1300b-1
    executor = LocalCodexExecutor({"model": "qwen3.5:9b", "endpoint": "http://127.0.0.1:11434"})
    argv = executor.command(tmp_path)
    assert argv[argv.index("--local-provider") + 1] == "ollama"
    assert "--strict-config" in argv
    assert 'default_permissions="leafcutter-worker"' in argv
    assert any('":root"="deny"' in value for value in argv)
    assert "--oss" in argv
    assert "features.multi_agent=false" in argv
    assert 'approval_policy="never"' in argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv


@pytest.mark.parametrize(
    "endpoint",
    ["https://ollama.com", "http://example.org:11434", "http://localhost:11434@evil.invalid"],
)
def test_nonlocal_implementation_endpoint_is_rejected(endpoint):
    # covers: ACD-1300g-1-i, ACD-1300b-1-i
    with pytest.raises(ExecutorError):
        LocalCodexExecutor({"model": "qwen3.5:9b", "endpoint": endpoint})


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"reviewed_sha": "wrong", "disposition": "approved", "findings": []},
        {
            "reviewed_sha": "abc",
            "disposition": "approved",
            "findings": [{"ac_ids": ["AC-1"], "description": "broken"}],
        },
    ],
)
def test_unusable_review_never_becomes_approval(value):
    # covers: ACD-1300g-3-i
    with pytest.raises(ExecutorError):
        validate_review(value, "abc", ["AC-1"])


def test_review_preserves_findings_and_requested_head():
    # covers: ACD-1300g-3
    result = {
        "reviewed_sha": "abc",
        "disposition": "changes_required",
        "findings": [{"ac_ids": ["AC-1"], "description": "assert count", "severity": "high"}],
    }
    assert validate_review(result, "abc", ["AC-1"]) == result


def test_sdk_boundary_sends_package_over_stdin_and_rejects_failed_process(tmp_path):
    # covers: ACD-1300g-3-i, ACD-1300g-3
    calls = []

    def invoke(argv, **kwargs):
        calls.append((argv, kwargs))
        raise ExecutorError("SDK unavailable")

    reviewer = SDKReviewer({"executor": "codex-sdk", "model": "configured-model"}, invoke=invoke)
    with pytest.raises(ExecutorError):
        reviewer.review(tmp_path, {"head_sha": "abc", "ac_ids": ["AC-1"]}, timeout=30)
    assert calls[0][0][-1].endswith("bridge.mjs")
    payload = json.loads(calls[0][1]["input_text"])
    assert payload["model"] == "configured-model"
    assert payload["package"]["head_sha"] == "abc"
    assert "configured-model" not in calls[0][0]


# covers: ACD-1300d-1, ACD-1300g-3
def test_reviewer_receives_only_its_auth_and_redacts_echoed_credential(tmp_path, monkeypatch):
    from scripts.background_worker.executors import SDKReviewer

    monkeypatch.setenv("GH_TOKEN", "unrelated-repository-token")
    monkeypatch.setenv("WORKER_REVIEW_AUTH", "selected-review-credential")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty-auth"))

    def invoke(argv, **kwargs):
        assert "GH_TOKEN" not in kwargs["env"]
        assert "WORKER_REVIEW_AUTH" not in kwargs["env"]
        assert kwargs["env"]["CODEX_API_KEY"] == "selected-review-credential"
        output = {
            "reviewed_sha": "head",
            "disposition": "changes_required",
            "findings": [
                {
                    "ac_ids": ["ACD-1300g-3"],
                    "severity": "high",
                    "description": "Do not persist selected-review-credential",
                }
            ],
        }
        return subprocess.CompletedProcess(argv, 0, json.dumps(output), "")

    result = SDKReviewer(
        {
            "executor": "codex-sdk",
            "model": "controlled",
            "credential_ref": "env:WORKER_REVIEW_AUTH",
        },
        invoke=invoke,
    ).review(tmp_path, {"head_sha": "head", "ac_ids": ["ACD-1300g-3"]})
    assert "selected-review-credential" not in json.dumps(result)
    assert "[REDACTED]" in result["findings"][0]["description"]
