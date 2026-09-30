"""
MODULE: kernel.secrets
GOAL: Load the Jev and Langfuse credentials from the process environment or a .env file without
    ever printing, logging or persisting their values.
BUSINESS CONTEXT: The kernel needs JEV_API_KEY and the Langfuse keys, which live in an untracked
    .env above the repository (worktrees do not receive it). Missing Jev credentials make a run
    fail with provider_unavailable; missing Langfuse credentials only degrade observability.
ARCHITECTURE: Lookup order per value: process environment, then the explicit env file
    (argument or LEAFCUTTER_ENV_FILE), then the first .env found walking up from the repository
    root. os.environ is never mutated; secret values are SecretStr and describe() returns
    presence booleans only.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from kernel.config import repo_root

logger = logging.getLogger(__name__)

ENV_FILE_VAR = "LEAFCUTTER_ENV_FILE"
# (settings field, environment variable names in priority order)
_FIELD_NAMES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("jev_api_key", ("JEV_API_KEY", "TYPESAFE_API_KEY")),
    ("langfuse_public_key", ("LANGFUSE_PUBLIC_KEY",)),
    ("langfuse_secret_key", ("LANGFUSE_SECRET_KEY",)),
    ("langfuse_base_url", ("LANGFUSE_BASE_URL", "LANGFUSE_HOST")),
)
_SECRET_FIELDS = frozenset({"jev_api_key", "langfuse_public_key", "langfuse_secret_key"})


class SecretSettings(BaseModel):
    """Loaded credentials; secret fields never reveal their value in repr or logs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    jev_api_key: SecretStr | None = Field(default=None, repr=False)
    langfuse_public_key: SecretStr | None = Field(default=None, repr=False)
    langfuse_secret_key: SecretStr | None = Field(default=None, repr=False)
    langfuse_base_url: str | None = Field(default=None, repr=False)
    origins: dict[str, str] = Field(default_factory=dict)

    def describe(self) -> dict[str, bool]:
        """Return presence booleans per field (never values)."""
        return {name: getattr(self, name) is not None for name, _ in _FIELD_NAMES}

    def has_jev(self) -> bool:
        """True if a Jev API key is available."""
        return self.jev_api_key is not None

    def has_langfuse(self) -> bool:
        """True if public key, secret key and base URL are all available."""
        return all((self.langfuse_public_key, self.langfuse_secret_key,
                    self.langfuse_base_url))

    def secret_values(self) -> dict[str, str]:
        """Return the loaded secret values by field name, for the redactor only."""
        found: dict[str, str] = {}
        for name in _SECRET_FIELDS:
            value = getattr(self, name)
            if value is not None:
                found[name] = value.get_secret_value()
        return found


def parse_env_text(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines: skips comments, accepts an `export ` prefix and strips quotes.

    Args:
        text: Contents of an env file.

    Returns:
        dict[str, str]: Variable name to value.
    """
    parsed: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        if not sep or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        parsed[key] = value
    return parsed


def find_env_file(start: Path) -> Path | None:
    """Return the first `.env` file found walking up from start, or None."""
    current = start.resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def _read_env_file(path: Path) -> dict[str, str]:
    """Read and parse an env file; unreadable files are logged (path only) and ignored."""
    try:
        return parse_env_text(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        logger.warning("could not read env file %s: %s", path, exc.strerror or "os error")
        return {}


def load_secrets(env_file: Path | None = None, *, env: Mapping[str, str] | None = None,
                 start_dir: Path | None = None) -> SecretSettings:
    """Load credentials from env, an explicit env file, then the first walked-up .env.

    Args:
        env_file: Explicit env file (falls back to LEAFCUTTER_ENV_FILE).
        env: Environment mapping (defaults to os.environ); never mutated.
        start_dir: Directory where the .env walk starts (defaults to the repository root).

    Returns:
        SecretSettings: Values that were found plus where each came from.
    """
    environment = os.environ if env is None else env
    explicit = env_file or (Path(environment[ENV_FILE_VAR])
                            if environment.get(ENV_FILE_VAR) else None)
    sources: list[tuple[str, Mapping[str, str]]] = [("env", environment)]
    if explicit is not None:
        sources.append((str(explicit), _read_env_file(Path(explicit))))
    walked = find_env_file(start_dir or repo_root())
    if walked is not None and walked != explicit:
        sources.append((str(walked), _read_env_file(walked)))
    values: dict[str, object] = {}
    origins: dict[str, str] = {}
    for field_name, names in _FIELD_NAMES:
        for origin, mapping in sources:
            hit = next((mapping[n] for n in names if mapping.get(n)), None)
            if hit is not None:
                values[field_name] = hit
                origins[field_name] = origin
                break
    return SecretSettings(origins=origins, **values)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Source order is the outer loop so an environment value
#   always beats a file value even when only a fallback alias (LANGFUSE_HOST) is set there.
#   (#KernelBootstrapV0/P1)
# ====================================================================
