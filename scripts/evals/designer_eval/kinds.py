"""
MODULE: scripts/evals/designer_eval/kinds.py
GOAL: The assertion kinds of the test-designer set: the edited requirement record is
    schema-valid, states a bug-fix / gate judgement, names the required wrong versions, the
    design was written, and (the trap) new behaviour states neither a bug fix nor a gate.
BUSINESS CONTEXT: TQ-200d-3. The designer produces no test file: its evidence is the requirement
    record it edited in place. Its judgement of "bug fix, gate or neither" is read from the fields
    of the test entries (TQ-500f-2-ii, 2026-09-27: ``must_catch`` or ``angle: discrimination``;
    their absence states neither), never from the reply text. Wrong-version names are matched with
    the wrong-version runner's own rule (_wvr_scope.wrong_version_key), so "revert the fix" and
    "the fix undone" are one name.
ARCHITECTURE: Every spec carries ``record`` (an AC id) and ``store`` (the sandbox-relative store
    directory). ``load`` reads ``<sandbox>/<store>/<record>.yaml``; a missing, unparseable, empty or
    non-mapping record fails the kind with a detail naming the record, never a harness error.
    Names come only from ``must_catch``; blank and non-string items are ignored. ``exact`` names
    match by key; each ``tokens`` entry matches as contiguous words (-, _ and whitespace alike) in
    its own distinct non-exact name; all required names must sit in ONE test entry.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import produced_tests_runs  # noqa: F401  (first: puts scripts/build_orchestration on sys.path for _wvr_scope)
import yaml
from _wvr_scope import wrong_version_key
from produced_tests_runs import RowContext

VALIDATOR = Path(__file__).resolve().parents[2] / "ac_store" / "validate_ac_schema.py"
VALIDATOR_TIMEOUT_SECONDS = 120
WORD_RE = re.compile(r"[^\W_]+")


def record_path(ctx: RowContext, spec: dict) -> Path:
    """Where the designer's edited record sits in the scoring sandbox."""
    return ctx.sandbox / spec["store"] / f"{spec['record']}.yaml"


def load(ctx: RowContext, spec: dict) -> tuple[dict | None, str]:
    """The parsed record, or ``(None, why)`` naming the record when it is missing, unparseable or not a mapping."""
    path, ac_id = record_path(ctx, spec), spec["record"]
    if not path.is_file():
        return None, f"{ac_id}: the sandbox holds no record file {spec['store']}/{ac_id}.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        return None, f"{ac_id}: the record does not parse ({exc})"
    if not isinstance(data, dict):
        return None, f"{ac_id}: the record is not a mapping"
    return data, ""


def entries(data: dict) -> list[dict]:
    """The mapping items of the record's test_spec (anything else is ignored)."""
    design = data.get("test_spec")
    return [e for e in design if isinstance(e, dict)] if isinstance(design, list) else []


def names_of(entry: dict) -> list[str]:
    """The non-blank string items of an entry's must_catch; nothing else names a wrong version."""
    raw = entry.get("must_catch")
    return [n for n in raw if isinstance(n, str) and n.strip()] if isinstance(raw, list) else []


def words(text: str) -> str:
    """Lower-cased words of *text* joined by one space: -, _, whitespace and other punctuation all separate words."""
    return " ".join(WORD_RE.findall(text.casefold()))


def has_token(name: str, token: str, variants: dict[str, list[str]]) -> bool:
    """True when the token, or one of its fixed word-sequence variants, appears in *name* as contiguous words."""
    padded = f" {words(name)} "
    return any(f" {words(phrase)} " in padded for phrase in (token, *variants.get(token, [])))


def unmatched_tokens(tokens: list[str], pool: list[str], variants: dict[str, list[str]]) -> list[str]:
    """The tokens left without a name of their own: a maximum matching of tokens to distinct names (spec order)."""
    owner: dict[int, int] = {}

    def place(t: int, seen: set[int]) -> bool:
        for n, name in enumerate(pool):
            if n in seen or not has_token(name, tokens[t], variants):
                continue
            seen.add(n)
            if n not in owner or place(owner[n], seen):
                owner[n] = t
                return True
        return False

    placed = {t for t in range(len(tokens)) if place(t, set())}
    return [tok for t, tok in enumerate(tokens) if t not in placed]


def missing_in(entry: dict, spec: dict) -> list[str]:
    """The required literals (as written in the spec) this one entry does not name."""
    exact = spec.get("exact", [])
    names = names_of(entry)
    have = {wrong_version_key(n) for n in names}
    missing = [e for e in exact if wrong_version_key(e) not in have]
    wanted = {wrong_version_key(e) for e in exact}
    pool = [n for n in names if wrong_version_key(n) not in wanted]
    return missing + unmatched_tokens(spec.get("tokens", []), pool, spec.get("variants", {}))


def schema_valid(ctx: RowContext, spec: dict) -> dict:
    """The edited record passes scripts/ac_store/validate_ac_schema.py (run with cwd at the sandbox)."""
    data, why = load(ctx, spec)
    if data is None:
        return {"passed": False, "detail": f"{why}; validate_ac_schema.py was not run"}
    cmd = [sys.executable, str(VALIDATOR), str(record_path(ctx, spec))]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=VALIDATOR_TIMEOUT_SECONDS, check=False, cwd=ctx.sandbox)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"passed": False, "detail": f"{spec['record']}: validate_ac_schema.py could not run ({exc!r})"}
    if done.returncode == 0:
        return {"passed": True, "detail": f"{spec['record']} passes validate_ac_schema.py"}
    first = " | ".join((done.stderr or done.stdout).strip().splitlines()[:3])
    return {"passed": False, "detail": f"{spec['record']} fails validate_ac_schema.py: {first[:300]}"}


def states_judgement(ctx: RowContext, spec: dict) -> dict:
    """Some entry carries a non-blank must_catch or is a discrimination test: a stated bug fix or gate."""
    data, why = load(ctx, spec)
    if data is None:
        return {"passed": False, "detail": why}
    stated = [e for e in entries(data) if names_of(e) or e.get("angle") == "discrimination"]
    if stated:
        return {"passed": True, "detail": f"{len(stated)} test entry(ies) state a bug fix or gate: must_catch or angle discrimination"}
    return {"passed": False, "detail": f"{spec['record']}: the design states neither a bug fix nor a gate: no test entry carries must_catch or angle discrimination"}


def names_wrong_versions(ctx: RowContext, spec: dict) -> dict:
    """One test entry names every required wrong version (the exact names and a distinct name per token)."""
    data, why = load(ctx, spec)
    if data is None:
        return {"passed": False, "detail": why}
    required = [*spec.get("exact", []), *spec.get("tokens", [])]
    best = min((missing_in(e, spec) for e in entries(data)), key=len, default=required)
    if not best:
        return {"passed": True, "detail": "one test entry names every required wrong version"}
    listed = "; ".join(repr(m) for m in best)
    return {"passed": False, "detail": f"{spec['record']}: no test entry names every required wrong version; still missing: {listed}"}


def states_neither(ctx: RowContext, spec: dict) -> dict:
    """The trap: new behaviour is neither a bug fix nor a gate, so no entry carries a non-blank must_catch or angle discrimination."""
    data, why = load(ctx, spec)
    if data is None:
        return {"passed": False, "detail": why}
    names = [n.strip() for e in entries(data) for n in names_of(e)]
    discriminating = [e for e in entries(data) if e.get("angle") == "discrimination"]
    if not names and not discriminating:
        return {"passed": True, "detail": f"{spec['record']}: no test entry carries must_catch or angle discrimination"}
    found = [f"must_catch {names}"] * bool(names) + ["angle discrimination"] * bool(discriminating)
    return {"passed": False, "detail": f"{spec['record']}: states neither a bug fix nor a gate, yet a test entry carries " + " and ".join(found)}


def design_written(ctx: RowContext, spec: dict) -> dict:
    """The designer wrote its design: a non-empty test_spec, authorship step test-designer, non-empty opened files."""
    data, why = load(ctx, spec)
    if data is None:
        return {"passed": False, "detail": why}
    authorship = data.get("test_design_authorship")
    opened = data.get("test_design_opened_files")
    checks = {
        "test_spec": bool(entries(data)),
        "test_design_authorship": isinstance(authorship, dict) and authorship.get("step") == "test-designer",
        "test_design_opened_files": isinstance(opened, list) and bool(opened),
    }
    missing = [field for field, ok in checks.items() if not ok]
    if missing:
        return {"passed": False, "detail": f"{spec['record']}: no design was written: {', '.join(missing)} missing or empty"}
    return {"passed": True, "detail": f"{spec['record']}: test_spec, test_design_authorship and test_design_opened_files are written"}


KINDS: dict[str, Callable[[RowContext, dict], dict]] = {
    "designer_record_schema_valid": schema_valid,
    "designer_states_judgement": states_judgement,
    "designer_names_wrong_versions": names_wrong_versions,
    "designer_states_neither": states_neither,
    "designer_design_written": design_written,
}
