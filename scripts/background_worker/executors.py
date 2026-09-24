"""Real sandboxed local implementation and read-only SDK review adapters.

Component: ac_driven_dev. AC: ACD-1300g-1, ACD-1300g-3.
"""

from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urlparse



from .execution_boundary import (
    ExecutorError, permission_overrides, local_environment, safe_output, check_evidence, run_process,
)

__all__ = [
    "ExecutorError", "permission_overrides", "local_environment", "safe_output", "check_evidence",
    "run_process", "LocalCodexExecutor", "SDKReviewer", "validate_review", "preflight",
]


def _local_endpoint(endpoint):
    parsed = urlparse(endpoint)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username
        or parsed.password
        or not parsed.hostname
    ):
        raise ExecutorError("Implementation endpoint must be a local Ollama URL")
    host = parsed.hostname
    if host != "localhost":
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
        if not local:
            raise ExecutorError("Implementation inference must stay on a loopback Ollama endpoint")
    return endpoint.rstrip("/")


class LocalCodexExecutor:
    """Codex's local OSS coding harness; no provider fallback or inherited plugins."""

    def __init__(self, settings, *, invoke=run_process):
        self.settings = dict(settings)
        self.model = str(settings.get("model", "qwen3.5:9b"))
        if "cloud" in self.model.lower():
            raise ExecutorError("Cloud Ollama model tags are not local implementation")
        if settings.get("provider", "ollama") != "ollama":
            raise ExecutorError("Local implementation provider must be Ollama")
        self.endpoint = _local_endpoint(settings.get("endpoint", "http://127.0.0.1:11434"))
        self.executable = settings.get("executable", "codex")
        self.invoke = invoke

    def command(self, workspace, outcome_schema=None):
        return [
            self.executable,
            "exec",
            "--oss",
            "--local-provider",
            "ollama",
            "--model",
            self.model,
            "--strict-config",
            "--ignore-user-config",
            "--ignore-rules",
            "--cd",
            str(Path(workspace).resolve()),
            "--json",
            "--ephemeral",
            *[item for value in permission_overrides() for item in ("-c", value)],
            *(["--output-schema", str(outcome_schema)] if outcome_schema else []),
            "-",
        ]

    def preflight(self):
        if not shutil.which(self.executable):
            raise ExecutorError("Codex CLI is not installed; local tool harness unavailable")
        result = self.invoke([self.executable, "exec", "--help"], cwd=Path.cwd(), timeout=20)
        if "--oss" not in result.stdout or "--strict-config" not in result.stdout:
            raise ExecutorError(
                "Installed Codex CLI does not provide the required OSS sandbox interface"
            )
        with tempfile.TemporaryDirectory(prefix="leafcutter-isolation-") as temporary:
            outer = Path(temporary)
            workspace = outer / "workspace"
            workspace.mkdir()
            (outer / "outside").write_text("boundary-sentinel", encoding="utf-8")
            probe = """from pathlib import Path
p=Path.cwd()
(p/'inside').write_text('allowed')
assert (p/'inside').read_text()=='allowed'
for op in (lambda: (p.parent/'outside').read_text(), lambda: (p.parent/'escaped').write_text('forbidden')):
    try: op()
    except PermissionError: pass
    else: raise RuntimeError('Native sandbox permitted outside access')
"""
            try:
                self.check(workspace, [sys.executable, "-c", probe], timeout=30)
            except ExecutorError as exc:
                raise ExecutorError(
                    "Native Codex sandbox cannot prove scoped read/write isolation on this host. "
                    "Run the worker in an isolated Linux/WSL environment with supported filesystem policies "
                    "and its check runtimes available. Native Windows elevated sandbox may require root read access; "
                    "the worker will not weaken the approved boundary."
                ) from exc
        try:
            with urlopen(self.endpoint + "/api/tags", timeout=10) as response:
                installed = json.load(response).get("models", [])
            if self.model not in {item.get("name") for item in installed}:
                raise ExecutorError(f"Required local model {self.model} is not installed in Ollama")
            request = Request(
                self.endpoint + "/api/show",
                data=json.dumps({"model": self.model}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=10) as response:
                metadata = json.load(response)
            if "tools" not in metadata.get("capabilities", []):
                raise ExecutorError(
                    "Ollama model does not advertise tool capability; install a tool-capable local model/runtime"
                )
        except (URLError, OSError, ValueError) as exc:
            raise ExecutorError(
                "Cannot verify installed local Ollama model and tool capability"
            ) from exc

    def check(self, workspace, argv, *, timeout, heartbeat=None):
        command = [
            self.executable,
            "sandbox",
            "-P",
            "leafcutter-worker",
            "-C",
            str(workspace),
            *[item for value in permission_overrides() for item in ("-c", value)],
            "--",
            *argv,
        ]
        with tempfile.TemporaryDirectory(prefix="leafcutter-check-") as home:
            env = local_environment()
            env["CODEX_HOME"] = home
            return self.invoke(
                command, cwd=workspace, timeout=timeout, heartbeat=heartbeat, env=env
            )

    def implement(self, workspace, context, *, timeout, heartbeat=None):
        workspace = Path(workspace).resolve(strict=True)
        with tempfile.TemporaryDirectory(prefix="leafcutter-codex-") as home:
            # A clean home prevents plugins, MCP servers, unsafe profiles and cloud auth leaking into local calls.
            env = local_environment()
            env.update(
                {"CODEX_HOME": home, "OLLAMA_BASE_URL": self.endpoint, "OLLAMA_HOST": self.endpoint}
            )
            config = Path(home) / "config.toml"
            try:
                config.write_text(
                    'approval_policy = "never"\n[features]\nmulti_agent = false\n', encoding="utf-8"
                )
            except OSError as exc:
                raise ExecutorError(
                    "Cannot establish isolated local harness configuration"
                ) from exc
            prompt = (
                "Implement the assigned AC and inherited obligations in this worktree. "
                "Run required checks and maintain documentation. Do not delegate, commit, push, merge, "
                "modify .git or access files outside the worktree. Dependency operations must remain project-local. "
                "Return the structured outcome. If an answer is necessary, use needs_input with exact questions; do not guess.\n"
                + context
            )
            schema = Path(home) / "outcome.schema.json"
            schema.write_text(
                json.dumps(
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["status", "questions"],
                        "properties": {
                            "status": {"type": "string", "enum": ["completed", "needs_input"]},
                            "questions": {"type": "array", "items": {"type": "string"}},
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = self.invoke(
                self.command(workspace, schema),
                cwd=workspace,
                input_text=prompt,
                timeout=timeout,
                env=env,
                heartbeat=heartbeat,
            )
        events = []
        for line in result.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not any(event.get("type") == "turn.completed" for event in events):
            raise ExecutorError("Local harness returned no completed turn; cannot infer success")
        if any(event.get("type") in {"turn.failed", "error"} for event in events):
            raise ExecutorError("Local harness reported an execution failure")
        messages = [
            event["item"].get("text", "")
            for event in events
            if event.get("type") == "item.completed"
            and event.get("item", {}).get("type") == "agent_message"
        ]
        try:
            outcome = json.loads(messages[-1])
        except (IndexError, ValueError) as exc:
            raise ExecutorError(
                "Local harness did not provide a structured completion/needs_input outcome"
            ) from exc
        if (
            not isinstance(outcome, dict)
            or set(outcome) != {"status", "questions"}
            or not isinstance(outcome["questions"], list)
            or any(not isinstance(q, str) or not q.strip() for q in outcome["questions"])
        ):
            raise ExecutorError("Invalid structured local outcome")
        if outcome["status"] == "needs_input" and outcome["questions"]:
            return outcome
        if outcome["status"] != "completed" or outcome["questions"]:
            raise ExecutorError("Local completion contradicts outstanding questions")
        if not any(
            event.get("type") == "item.completed"
            and (
                event.get("item", {}).get("type") == "command_execution"
                and event["item"].get("exit_code") == 0
                or event.get("item", {}).get("type") == "file_change"
                and event["item"].get("status") == "completed"
            )
            for event in events
        ):
            raise ExecutorError("Local harness produced no actual tool execution evidence")
        return {"status": "completed", "questions": [], "event_count": len(events)}


def validate_review(result, expected_sha, ac_ids):
    if not isinstance(result, dict) or result.get("reviewed_sha") != expected_sha:
        raise ExecutorError("Review is missing or belongs to a different head")
    if set(result) != {"reviewed_sha", "disposition", "findings"}:
        raise ExecutorError("Review does not match the strict result schema")
    if result.get("disposition") not in {"approved", "changes_required"} or not isinstance(
        result.get("findings"), list
    ):
        raise ExecutorError("Review has no valid disposition/findings")
    findings = result["findings"]
    if (result["disposition"] == "approved" and findings) or (
        result["disposition"] == "changes_required" and not findings
    ):
        raise ExecutorError("Review disposition contradicts its findings")
    for finding in findings:
        if (
            not isinstance(finding, dict)
            or not finding.get("description")
            or not isinstance(finding.get("ac_ids"), list)
            or not finding["ac_ids"]
        ):
            raise ExecutorError("Review findings must identify affected ACs")
        if (
            set(finding) != {"ac_ids", "severity", "description"}
            or not isinstance(finding["description"], str)
            or finding["severity"] not in {"low", "medium", "high", "critical"}
            or any(not isinstance(ac, str) for ac in finding["ac_ids"])
        ):
            raise ExecutorError("Review finding does not match the strict result schema")
        if not set(finding["ac_ids"]).issubset(set(ac_ids)):
            raise ExecutorError("Review findings reference ACs outside the feature")
    return result


class SDKReviewer:
    """Node bridge uses actual SDK APIs; subprocess JSON is strictly checked here."""

    def __init__(self, settings, *, invoke=run_process):
        self.settings = dict(settings)
        if settings.get("executor") not in {"codex-sdk", "claude-agent-sdk"} or not settings.get(
            "model"
        ):
            raise ExecutorError("Configure a supported reviewer SDK and explicit model")
        self.bridge = Path(__file__).parent / "reviewer_sdk" / "bridge.mjs"
        self.invoke = invoke

    def preflight(self):
        if not shutil.which("node") or not self.bridge.exists():
            raise ExecutorError("Reviewer Node runtime or installed SDK bridge missing")
        self.invoke(
            ["node", str(self.bridge), "--check", self.settings["executor"]],
            cwd=self.bridge.parent,
            timeout=20,
        )
        credential = self.settings.get("credential_ref")
        if credential and not os.environ.get(credential.removeprefix("env:")):
            raise ExecutorError(
                "Configured reviewer credential environment variable is unavailable"
            )
        if not credential:
            if self.settings["executor"] == "codex-sdk":
                auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
                present = (
                    os.environ.get("CODEX_API_KEY")
                    or os.environ.get("OPENAI_API_KEY")
                    or auth.is_file()
                )
            else:
                auth = Path.home() / ".claude" / ".credentials.json"
                present = (
                    os.environ.get("ANTHROPIC_API_KEY")
                    or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
                    or auth.is_file()
                )
            if not present:
                raise ExecutorError(
                    "Reviewer credentials are unavailable; configure credential_ref or authenticate the selected SDK CLI"
                )

    def review(self, workspace, package, *, timeout=1800, heartbeat=None):
        payload = {
            "executor": self.settings["executor"],
            "model": self.settings["model"],
            "workspace": str(Path(workspace).resolve()),
            "package": package,
        }
        env = local_environment()
        auth_names = (
            ("CODEX_API_KEY", "OPENAI_API_KEY")
            if self.settings["executor"] == "codex-sdk"
            else ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
        )
        env.update({name: os.environ[name] for name in auth_names if os.environ.get(name)})
        credential = self.settings.get("credential_ref")
        if credential:
            value = os.environ.get(credential.removeprefix("env:"))
            if not value:
                raise ExecutorError("Configured reviewer credentials are unavailable")
            env[
                "CODEX_API_KEY" if self.settings["executor"] == "codex-sdk" else "ANTHROPIC_API_KEY"
            ] = value
        with tempfile.TemporaryDirectory(prefix="leafcutter-review-") as home:
            original = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
            if self.settings["executor"] == "codex-sdk":
                if original.is_file():
                    shutil.copyfile(original, Path(home) / "auth.json")
                env["CODEX_HOME"] = home
            payload["configOverrides"] = permission_overrides(readonly=True)
            review_workspace = Path(home) / "review-workspace"
            review_workspace.mkdir()
            payload["reviewWorkspace"] = str(review_workspace)
            result = self.invoke(
                ["node", str(self.bridge)],
                cwd=workspace,
                input_text=json.dumps(payload),
                timeout=timeout,
                env=env,
                heartbeat=heartbeat,
            )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ExecutorError("SDK bridge did not return structured review output") from exc
        data = validate_review(
            data, package["head_sha"], package.get("review_ac_ids", package["ac_ids"])
        )
        for finding in data["findings"]:
            description = safe_output(finding["description"])
            for name in auth_names:
                secret = env.get(name)
                if secret:
                    description = description.replace(secret, "[REDACTED]")
            finding["description"] = description
        return data


def preflight(settings):
    LocalCodexExecutor(settings["implementation"]).preflight()
    SDKReviewer(settings["reviewer"]).preflight()
