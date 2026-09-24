"""Configuration validation; no credentials or implicit cloud implementation."""

from __future__ import annotations
from urllib.parse import urlparse
import re
import math


def validate(settings: dict, *, executable: bool = False) -> None:
    poll = settings.get("poll_seconds", 15)
    if type(poll) not in (int, float) or not math.isfinite(poll) or not 1 <= poll <= 60:
        raise ValueError("poll_seconds must be between 1 and 60")
    count = settings.get("max_agent_calls", 1)
    if type(count) is not int or count < 1:
        raise ValueError("max_agent_calls must be a positive integer")
    if type(settings.get("enabled", False)) is not bool:
        raise ValueError("enabled must be boolean")
    for role in ("implementation", "reviewer"):
        value = settings.get(role)
        if value is None and not executable:
            continue
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("model"), str)
            or not value["model"].strip()
        ):
            raise ValueError(role + " requires explicit executor and model settings")
        fields = {"executor", "provider", "model", "credential_ref"}
        if role == "implementation":
            fields.add("endpoint")
        if set(value) - fields:
            raise ValueError(
                role + " contains unsupported fields; use credential_ref for authentication"
            )
        ref = value.get("credential_ref")
        if ref is not None and (
            not isinstance(ref, str) or not re.fullmatch(r"env:[A-Za-z_][A-Za-z0-9_]*", ref)
        ):
            raise ValueError("credential_ref must name an environment variable as env:NAME")
        if not isinstance(value.get("executor"), str):
            raise ValueError(role + " executor must be a string")
        allowed = {"codex-cli"} if role == "implementation" else {"codex-sdk", "claude-agent-sdk"}
        if value.get("executor") not in allowed:
            raise ValueError(role + " executor is unsupported")
        if role == "implementation":
            if not isinstance(value.get("endpoint", ""), str):
                raise ValueError("Implementation endpoint must be a URL")
            endpoint = urlparse(value.get("endpoint", "http://127.0.0.1:11434"))
            if (
                value.get("provider") != "ollama"
                or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
                or endpoint.scheme != "http"
                or endpoint.username
                or endpoint.password
                or "cloud" in value["model"].lower()
            ):
                raise ValueError("Implementation requires a local Ollama endpoint and local model")
        elif value.get("provider") not in (
            None,
            "openai" if value["executor"] == "codex-sdk" else "anthropic",
        ):
            raise ValueError("Reviewer provider does not match its configured SDK")
    checks = settings.get("checks", [])
    if executable and not checks:
        raise ValueError("Configure at least one required project check before enabling work")
    if not isinstance(checks, list) or any(
        not isinstance(c, list) or not c or any(not isinstance(s, str) or not s for s in c)
        for c in checks
    ):
        raise ValueError("checks must be a list of nonempty argument arrays")
    target = settings.get("target_ref", "origin/main")
    if not isinstance(target, str) or not target or target.startswith("-"):
        raise ValueError("target_ref must be a Git reference")
