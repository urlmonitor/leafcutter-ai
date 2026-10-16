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



from .local_model import write_catalog
from .reply_contract import reply_instructions
from .local_outcome import parse_outcome
from .codex_home import isolated_codex_home

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
        self.metadata = {}

    def command(self, workspace, model_options=(), *, readonly=False):
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
            *[item for value in (*permission_overrides(workspace=workspace, readonly=readonly), *model_options) for item in ("-c", value)],
            "-",
        ]

    def preflight(self):
        if not shutil.which(self.executable):
            raise ExecutorError("Codex CLI is not installed; local tool harness unavailable")
        result = self.invoke([self.executable, "exec", "--help"], cwd=Path.cwd(), timeout=20)
        if any(flag not in result.stdout for flag in ("--oss", "--strict-config")):
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
try: (p.parent/'outside').read_text()
except (PermissionError, FileNotFoundError): pass
else: raise RuntimeError('Native sandbox permitted outside read')
for name in ('outside', 'escaped'):
    try: (p.parent/name).write_text('forbidden')
    except (PermissionError, FileNotFoundError, OSError): pass
"""
            try:
                self.check(workspace, [sys.executable, "-c", probe], timeout=30)
                # Linux may allow writes to private namespace temp paths; verify
                # from the coordinator that no real outside write escaped.
                if (outer / "outside").read_text(encoding="utf-8") != "boundary-sentinel" or (outer / "escaped").exists():
                    raise ExecutorError("Native sandbox allowed a write outside the owned worktree")
                if (workspace / "inside").read_text(encoding="utf-8") != "allowed":
                    raise ExecutorError("Native sandbox did not persist the owned worktree write")
            except (ExecutorError, OSError) as exc:
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
        try:
            with tempfile.TemporaryDirectory(prefix="leafcutter-model-preflight-") as home:
                write_catalog(
                    home, self.model, metadata,
                    context_window=self.settings.get("context_window", 65536),
                    reasoning_effort=self.settings.get("reasoning_effort"),
                )
        except (OSError, ValueError) as exc:
            raise ExecutorError("Invalid local model runtime configuration: " + str(exc)) from exc
        self.metadata = metadata

    def check(self, workspace, argv, *, timeout, heartbeat=None, readonly=False):
        command = [
            self.executable,
            "sandbox",
            "-P",
            "leafcutter-worker",
            "-C",
            str(workspace),
            *[item for value in permission_overrides(workspace=workspace, readonly=readonly) for item in ("-c", value)],
            "--",
            *argv,
        ]
        with isolated_codex_home(prefix="check-") as home:
            env = local_environment()
            env["CODEX_HOME"] = home
            return self.invoke(
                command, cwd=workspace, timeout=timeout, heartbeat=heartbeat, env=env
            )

    def implement(self, workspace, context, *, timeout, heartbeat=None):
        return self._execute(workspace, context, timeout=timeout, heartbeat=heartbeat)

    def discover(self, workspace, context, *, timeout, heartbeat=None):
        return self._execute(workspace, context, timeout=timeout, heartbeat=heartbeat, discovery=True)

    def _execute(self, workspace, context, *, timeout, heartbeat=None, discovery=False):
        workspace = Path(workspace).resolve(strict=True)
        with isolated_codex_home(prefix="implementation-") as home:
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
                "Follow this work sequence:\n"
                "1. Read assigned_ac and saved resolved_user_decisions. Honor genuinely unresolved explicit confirmation gates.\n"
                "2. Use available file or shell tools to locate and read relevant code, tests and documentation in this worktree. "
                "Do not ask the user to paste contents of files you can read locally; inspect those files with tools.\n"
                "3. Implement the approved assigned behavior, preserve prior work, and run required_checks. "
                "Investigate tool/check failures using available tools.\n"
                "The coordinator also rejects unintended trailing whitespace in changed lines. "
                "Inspect submitted edits for that quality gate without running Git; remove accidental trailing whitespace "
                "while preserving meaningful whitespace in code, strings and fixtures.\n"
                "4. Finish with exactly one valid JSON outcome object, without Markdown fences, explanation or trailing characters.\n\n"
                "Implement ONLY assigned_ac and its inherited obligations in this worktree. "
                "Other leaf ACs in the full feature plan are context, not authorization to implement them now. "
                "Preserve work and passing tests from previously completed ACs; do not implement future leaf behavior early. "
                "Do not run Git commands; the coordinator handles worktree metadata, diff, commits and publication. "
                "Inspect and edit files directly. "
                "Execute clear approved AC and reviewer requests without asking permission; "
                "use judgment for routine code and test choices. Ask needs_input only for a genuinely missing "
                "or contradictory requirement, or an explicit requirement to obtain user confirmation. "
                "Read resolved_user_decisions first on resume: these human answers have already been provided. "
                "Fulfill those confirmed choices instead of asking the same confirmation again. Apply each saved human answer only to its "
                "recorded question and scope; do not repeat an already answered confirmation unless a new conflict remains. "
                "Run required checks and maintain documentation. Do not delegate, commit, push, merge, "
                "modify .git or access files outside the worktree. Dependency operations must remain project-local. "
                "Use the available tools to read and modify the actual files; a completion claim alone is not work. "
                + reply_instructions()
                + context
            )
            if discovery:
                from .discovery_executor import discovery_prompt
                prompt = discovery_prompt(context)
            catalog, effort, window = write_catalog(
                home, self.model, self.metadata,
                context_window=self.settings.get("context_window", 65536),
                reasoning_effort=self.settings.get("reasoning_effort"),
            )
            options = [
                "model_catalog_json=" + json.dumps(str(catalog)),
                "model_reasoning_effort=" + json.dumps(effort),
                f"model_context_window={window}",
                f"model_auto_compact_token_limit={window * 3 // 4}",
                'web_search="disabled"',
            ]
            result = self.invoke(
                self.command(workspace, options, readonly=discovery),
                cwd=workspace,
                input_text=prompt,
                timeout=timeout,
                env=env,
                heartbeat=heartbeat,
            )
        return parse_outcome(result.stdout, discovery=discovery)


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
        with isolated_codex_home(prefix="review-") as home:
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

# DECISION HISTORY
# ========================================
# - 2026-09-30 00:00 [python-coder]: Keep tool turns unconstrained after paired local inference evidence; validate final reports separately. (#TICKETLESS reason=approved-ac-local-schema-transport)
