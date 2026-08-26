"""
MODULE: _acs_100i_support
GOAL: Verdict and whole-corpus helpers for the ACS-100i-6 / -7 / -8 test tree —
    the tree that narrows the AC-store "package surface" structured-spec
    obligation from a spelling-keyed proxy (assigned_agent + component enum) to
    an explicit `package_surface: true` declaration on the record. This module
    is the single import surface for the test modules; path, fixture and CLI
    helpers live in _acs_100i_fixtures and are re-exported here.
BUSINESS CONTEXT: The obligation today fires on `assigned_agent: python-coder`
    AND `component` in {build_pipeline, build-orchestration}. Measured on this
    worktree at 9b16d013, that proxy over-matches (243 of the store's 280
    refusals are this one rule, including the three BO-2000d records that
    *specify* the rule) and under-matches (440 records spell the namespace
    `build-pipeline`, which the trigger enum omits, so the gate has never fired
    on them). ACS-100i-6 replaces the proxy with a declaration; ACS-100i-7
    asserts the effect on the REAL corpus; ACS-100i-8 stops an undeclared
    surface from landing anyway by reconciling registry additions against the
    declaration.
ARCHITECTURE: Every helper is behavioral. Verdicts come from
    ``validate_with_jsonschema`` — the exact helper
    templates/scripts/commit_guardian/check_ac_schema.py calls — run against the
    real config/ac_store_schema.json. Nothing here greps a source file for a
    string: per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by
    Grep", a grep-only test passes on dead code.

    Rule attribution
    ----------------
    "Refused for lacking a structured implementation spec" is computed, not
    pattern-matched on message text. A record's refusal is attributed to the
    package-surface rule when it disappears once the schema's TOP-LEVEL
    ``if``/``then`` block is removed. Errors raised by the ``it_requirements``
    ``oneOf`` object branch survive that removal and are therefore counted as
    UNRELATED — which is exactly what makes the ACS-100i-7 second scenario a
    real anti-loosening guard: an implementer who reaches "zero rule refusals"
    by weakening the object branch shrinks the unrelated set and fails.

    Self-hosting boundary (ADR-001): ``scripts/commit_guardian/`` exists only in
    a deployed consumer layout. In this source repo the commit hook and its
    helper live under ``templates/scripts/commit_guardian/``.
"""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# This directory holds the sibling helper modules. Inserted here rather than in
# a conftest.py so the import surface stays local to this test tree — a
# root-level sys.path mutation has a blast radius across every suite.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acs_100i_fixtures import (  # noqa: E402, F401  (re-exported for tests)
    AC_SCHEMA_HOOK,
    AC_STORE_DIR,
    BASELINE_FIXTURE,
    COMMIT_GUARDIAN_DIR,
    NAMED_FALSE_REFUSALS,
    PKG_SURFACE_VALIDATOR_CLI,
    REPO_ROOT,
    REQUIRED_IMPL_FIELDS,
    SCHEMA_PATH,
    SCHEMA_VALIDATOR_CLI,
    CliRun,
    base_ac_record,
    complete_impl_spec,
    fields_reported_missing,
    load_baseline,
    refusal_text,
    run_cli,
    states_structured_spec_obligation,
    write_ac_yaml,
)

sys.path.insert(0, str(COMMIT_GUARDIAN_DIR))
from _ac_schema_validators import validate_with_jsonschema  # noqa: E402

_SCHEMA_CACHE: dict[str, Any] = {}
_STORE_CACHE: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def load_schema() -> dict[str, Any]:
    """Return the real config/ac_store_schema.json, parsed and cached.

    Returns:
        The parsed schema dict. Callers must not mutate it.
    """
    if "full" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE["full"] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE["full"]


def schema_without_package_surface_rule() -> dict[str, Any]:
    """Return the schema with its TOP-LEVEL ``if``/``then`` block removed.

    This is the counterfactual used for rule attribution (see module
    docstring). The ``it_requirements`` ``oneOf`` object branch — which carries
    its own five-field ``required`` list independently of the trigger — is left
    completely intact, so anything it refuses is still refused here.

    Returns:
        A deep copy of the schema minus the top-level if/then pair.
    """
    if "stripped" not in _SCHEMA_CACHE:
        stripped = copy.deepcopy(load_schema())
        stripped.pop("if", None)
        stripped.pop("then", None)
        _SCHEMA_CACHE["stripped"] = stripped
    return _SCHEMA_CACHE["stripped"]


def top_level_rule_is_present() -> bool:
    """Return True when the schema still carries a top-level if/then pair.

    Guards the attribution helpers against silently becoming vacuous: if a
    future edit deletes the rule outright rather than narrowing it, every
    attribution would be empty and every ACS-100i-7 assertion would pass for
    the wrong reason.
    """
    schema = load_schema()
    return "if" in schema and "then" in schema


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Verdict:
    """A validator verdict on one AC record, split by rule attribution.

    Attributes:
        refused: True when the record fails the real schema.
        messages: Every jsonschema message the real schema produced.
        rule_messages: The subset attributable to the top-level package-surface
            if/then rule — messages that vanish when that block is removed.
        other_messages: The remainder (object-branch, enum, required-field,
            additionalProperties — anything not caused by the trigger).
    """

    refused: bool
    messages: tuple[str, ...]
    rule_messages: tuple[str, ...]
    other_messages: tuple[str, ...]

    @property
    def refused_on_package_surface_rule(self) -> bool:
        """True when at least one refusal is attributable to the rule."""
        return bool(self.rule_messages)


def verdict(data: dict[str, Any]) -> Verdict:
    """Validate one in-memory AC record against the real schema.

    Uses ``validate_with_jsonschema`` — the exact helper
    ``templates/scripts/commit_guardian/check_ac_schema.py`` calls — so this
    verdict is the commit-time gate's verdict, not a re-implementation of it.

    Args:
        data: Parsed AC record.

    Returns:
        A :class:`Verdict` with the refusal split by rule attribution.
    """
    full = validate_with_jsonschema(data, load_schema())
    stripped = validate_with_jsonschema(data, schema_without_package_surface_rule())

    remaining = Counter(stripped)
    rule_messages: list[str] = []
    other_messages: list[str] = []
    for message in full:
        if remaining[message] > 0:
            remaining[message] -= 1
            other_messages.append(message)
        else:
            rule_messages.append(message)

    return Verdict(
        refused=bool(full),
        messages=tuple(full),
        rule_messages=tuple(rule_messages),
        other_messages=tuple(other_messages),
    )


# ---------------------------------------------------------------------------
# The real corpus
# ---------------------------------------------------------------------------


def load_store_records() -> dict[Path, Any]:
    """Parse every AC YAML in the REAL store, once per session.

    ``index.yaml`` is excluded — it is the namespace registry, not an AC
    record, and the ACS-100i-7 baseline was measured with it excluded.

    Returns:
        Mapping of absolute file path to parsed YAML content.
    """
    if "store" not in _STORE_CACHE:
        loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
        records: dict[Path, Any] = {}
        for path in sorted(AC_STORE_DIR.rglob("*.yaml")):
            if path.name == "index.yaml":
                continue
            records[path] = yaml.load(path.read_text(encoding="utf-8"), Loader=loader)
        _STORE_CACHE["store"] = records
    return _STORE_CACHE["store"]


def whole_store_pass(extra: dict[Path, Any] | None = None) -> dict[Path, Verdict]:
    """Validate every record in the store (plus ``extra``) in one pass.

    Args:
        extra: Additional path -> record entries to include in the pass, as
            ACS-100i-7-i's "a copy of the store into which one record has been
            added" requires. The real store on disk is never mutated.

    Returns:
        Mapping of path to :class:`Verdict` for every REFUSED record only.
        Accepted records are omitted so callers can compare refusal sets
        directly.

    Note:
        The store's own verdicts are memoized across calls. JSON Schema
        validation is a pure function of (record, schema) and the schema is read
        once, so memoizing loses no fidelity — every record is still validated
        against the real schema by the real helper; it is simply not
        re-validated for each test in the same session.
    """
    if "refusals" not in _STORE_CACHE:
        base: dict[Path, Verdict] = {}
        for path, data in load_store_records().items():
            if not isinstance(data, dict) or "id" not in data:
                continue
            result = verdict(data)
            if result.refused:
                base[path] = result
        _STORE_CACHE["refusals"] = base

    refusals: dict[Path, Verdict] = dict(_STORE_CACHE["refusals"])
    for path, data in (extra or {}).items():
        if not isinstance(data, dict) or "id" not in data:
            continue
        result = verdict(data)
        if result.refused:
            refusals[path] = result
        else:
            refusals.pop(path, None)
    return refusals


def store_relative(path: Path) -> str:
    """Return ``path`` relative to the repo root as a POSIX string."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def find_store_record(ac_id: str) -> Path:
    """Return the on-disk path of a real AC record by id.

    Args:
        ac_id: The AC id, matching its file stem (e.g. ``BO-2000d-1``).

    Returns:
        Absolute path to the record.

    Raises:
        AssertionError: When no such record exists — a test asserting on a
            named real record must fail loudly rather than skip.
    """
    matches = [p for p in load_store_records() if p.stem == ac_id]
    assert matches, f"AC record {ac_id!r} not found under {AC_STORE_DIR}"
    return matches[0]
