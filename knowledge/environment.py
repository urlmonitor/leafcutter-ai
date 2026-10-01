"""MODULE: environment
GOAL: Resolve optional knowledge credentials without changing the process environment.
BUSINESS CONTEXT: Worktrees consume external credentials without copying secret files.
ARCHITECTURE: Mirrors kernel.secrets source precedence using stdlib only; no kernel imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import KnowledgeConfig

import logging
import os
from pathlib import Path
from urllib.parse import urlsplit
from .errors import invalid


def _read(path: Path, *, explicit: bool = False) -> dict[str, str]:
    """Read.

    Args:
        path: External environment file to parse without exposing its contents.


    Returns:
        dict[str, str]: Parsed assignments, or an empty mapping for unreadable discovered files.

    Keyword-only explicit: Whether unreadability must fail instead of warning.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        if explicit:
            invalid("cannot read named LEAFCUTTER_ENV_FILE")
        logging.getLogger(__name__).warning("could not read discovered knowledge env file")
        return {}
    parsed = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if sep and key:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            parsed[key] = value
    return parsed


def environment_sources(
    start: str | Path | None = None, *, env: dict[str, str] | None = None
) -> list[dict[str, str]]:
    """Return process, named file and nearest ancestor file in precedence order.

    Args:
        start: Directory from which nearest-parent environment discovery starts.


    Returns:
        list[dict[str, str]]: Process mapping followed by explicit and discovered file mappings.

    Keyword-only env: Optional process-environment mapping used instead of os.environ.
    """
    environment = os.environ if env is None else env
    sources = [environment]
    explicit = (
        Path(environment["LEAFCUTTER_ENV_FILE"]).resolve()
        if environment.get("LEAFCUTTER_ENV_FILE")
        else None
    )
    if explicit is not None:
        sources.append(_read(explicit, explicit=True))
    current = Path(start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            if candidate != explicit:
                sources.append(_read(candidate))
            break
    return sources


def select_value(sources: list[dict[str, str]], *names: str) -> str | None:
    """Select source before alias priority; never print or persist the selected value.

    Args:
        sources: Credential sources in descending precedence order.
        names: Variable names in descending alias precedence order.

    Returns:
        str | None: First nonempty variable value, or None when every source lacks it.
    """
    return next((source[name] for source in sources for name in names if source.get(name)), None)


def resolve_neo4j(
    config: KnowledgeConfig | dict, *, env: dict[str, str] | None = None
) -> list[str]:
    """Resolve serving aliases; custom variable names remain explicit and fail closed.

    Args:
        config: Explicit optional backend configuration.


    Returns:
        list[str]: URI, username and password in backend constructor order.

    Keyword-only env: Optional process-environment mapping used instead of os.environ.
    """
    sources = environment_sources(config.repository_root, env=env)
    values = []
    names = (config.neo4j_uri_env, config.neo4j_username_env, config.neo4j_password_env)
    for name, suffix in zip(names, ("URI", "USERNAME", "PASSWORD")):
        aliases = (name, "NEO4J_" + suffix) if name == "LEAFCUTTER_NEO4J_" + suffix else (name,)
        values.append(select_value(sources, *aliases))
    if values[0] and not values[1] and names[1] == "LEAFCUTTER_NEO4J_USERNAME":
        try:
            host = urlsplit(values[0]).hostname or ""
        except ValueError:
            invalid("invalid Neo4j URI")
        if host.endswith(".databases.neo4j.io"):
            values[1] = "neo4j"
    missing = [name for name, value in zip(names, values) if not value]
    if missing:
        invalid("enabled Neo4j backend missing settings: " + ", ".join(missing))
    return values


def resolve_database(config: KnowledgeConfig | dict, *, env: dict[str, str] | None = None) -> str:
    """Use an explicit configured database, then environment aliases, then neo4j.

    Args:
        config: Explicit optional backend configuration.


    Returns:
        str: Explicit, environment-selected or fallback database name.

    Keyword-only env: Optional process-environment mapping used instead of os.environ.
    """
    if config.database is not None:
        if not config.database.strip():
            invalid("configured Neo4j database must not be empty")
        return config.database
    sources = environment_sources(config.repository_root, env=env)
    return select_value(sources, "LEAFCUTTER_NEO4J_DATABASE", "NEO4J_DATABASE") or "neo4j"
