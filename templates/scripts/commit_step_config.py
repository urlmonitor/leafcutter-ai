#!/usr/bin/env python3
"""
MODULE: commit_step_config
GOAL: Load and validate config/commit_step.json -- the one place the shared commit
    step's answer vocabulary (answer_version, answer keys and their empty values,
    reason_code families, the two retry ceilings) lives -- exactly once per run.
BUSINESS CONTEXT: BO-4500a-4 moves the contract's vocabulary out of code so extending
    it (a new code, a new key) is an edit to one data file. The step must therefore
    refuse, not guess, when that file cannot be trusted: there is NO built-in
    fallback list and NO default ceiling anywhere in code.
ARCHITECTURE: Stdlib only; the structure is validated by hand (the published form of
    the same check is config/commit_step.schema.json, which the step never reads, so
    the schema is not deployed). Lookup order: the file named by
    LEAFCUTTER_COMMIT_STEP_CONFIG (and only that file when set), else
    config/commit_step.json beside the source tree, else beside the deployed install.
    This module raises ConfigError and imports nothing from the step, so
    commit_step_base can depend on it without a cycle.

DECISION HISTORY:
  - 2026-10-16 [python-coder/BO-4500a-4]: Created. Replaces commit_step_base.ceiling()
    (which defaulted to 3 when no file existed) with load-once, validate-by-hand,
    refuse-on-failure semantics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_ENV = "LEAFCUTTER_COMMIT_STEP_CONFIG"
_FILE = "commit_step.json"
# Which families may carry a code for each status (a structural rule of the contract,
# not vocabulary): a refused answer is a policy or a step code, and so on.
STATUS_FAMILIES = {
    "refused": ("policy", "step"),
    "hook_failed": ("check",),
    "nothing_to_commit": ("nothing",),
    "committed": (),
}
_CEILINGS = ("max_automated_fix_retries", "max_transient_retries")
_STATE: dict[str, dict] = {}


class ConfigError(Exception):
    """The step's config file is missing, unreadable or structurally invalid."""

    def __init__(self, subject: str, problem: str) -> None:
        super().__init__(f"{subject} {problem}")


def _candidates() -> list[Path]:
    """The files to try, in order: the override alone, else source-tree then deployed."""
    override = os.environ.get(CONFIG_ENV)
    if override:
        return [Path(override)]
    here = Path(__file__).resolve().parent
    return [here.parent.parent / "config" / _FILE, here.parent / "config" / _FILE]


def _is_count(value: object) -> bool:
    """True for a non-negative integer that is not a bool."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _check_codes(codes: object) -> None:
    """Validate the reason_codes partition: four lists of unique, non-empty strings."""
    if not isinstance(codes, dict):
        raise ConfigError("reason_codes", "must be an object of families")
    if sorted(codes) != sorted(f for fams in STATUS_FAMILIES.values() for f in fams):
        raise ConfigError("reason_codes", "must hold exactly the families policy, step, check, nothing")
    if any(not isinstance(family, list) for family in codes.values()):
        raise ConfigError("reason_codes", "families must each be a list")
    every = [code for family in codes.values() for code in family]
    if any(not isinstance(code, str) or not code for code in every):
        raise ConfigError("reason_codes", "families must hold non-empty strings only")
    if len(every) != len(set(every)):
        raise ConfigError("reason_codes", "lists a code in more than one family")


def validate(config: object) -> dict:
    """Return *config* when structurally valid, else raise ConfigError saying why."""
    if not isinstance(config, dict):
        raise ConfigError("config", "must hold one JSON object")
    version = config.get("answer_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ConfigError("answer_version", "must be an integer of at least 1")
    keys = config.get("answer_keys")
    if not isinstance(keys, dict) or not keys:
        raise ConfigError("answer_keys", "must be a non-empty object")
    _check_codes(config.get("reason_codes"))
    for name in _CEILINGS:
        if not _is_count(config.get(name)):
            raise ConfigError(name, "must be a non-negative integer")
    if "commit_time_limit_seconds" in config:  # optional; the supervised backstop defaults to 1800
        limit = config["commit_time_limit_seconds"]
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit <= 0:
            raise ConfigError("commit_time_limit_seconds", "must be a number above 0")
    return config


def _read(path: Path) -> dict:
    """Read and validate one candidate file; every failure becomes a ConfigError."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(str(path), f"cannot be read: {exc}") from exc
    try:
        return validate(json.loads(text))
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        raise ConfigError(str(path), f"is not valid JSON: {exc}") from exc
    except ConfigError as exc:
        raise ConfigError(str(path), f"is invalid: {exc}") from exc


def load_config() -> dict:
    """Load and validate the config once; later calls return the same object."""
    if "config" not in _STATE:
        found = next((p for p in _candidates() if p.is_file()), None)
        if found is None:
            raise ConfigError(_FILE, "not found (looked at: " + ", ".join(str(p) for p in _candidates()) + ")")
        _STATE["config"] = _read(found)
    return _STATE["config"]


def loaded() -> dict | None:
    """The config if load_config() succeeded in this run, else None."""
    return _STATE.get("config")


def allowed_codes(config: dict, status: str) -> list[str]:
    """Every reason_code a *status* answer may carry, per the config's families."""
    return [code for family in STATUS_FAMILIES.get(status, ()) for code in config["reason_codes"][family]]
