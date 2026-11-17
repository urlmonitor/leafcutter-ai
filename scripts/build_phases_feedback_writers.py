"""
MODULE: build_phases_feedback_writers
GOAL: Fail the build when an agent that signs off can write to no feedback category,
    and report (without failing) every allowed_writers entry that names no registered
    agent.
BUSINESS CONTEXT: KI-FC-003 / AC INF-100c-5. ``submit_feedback.py`` silently refuses an
    agent that is in no category's allowed_writers, and nothing checked that the agent
    definitions and the writer lists agree. Five agents were each added by hand after the
    same silent rejection. This check turns that class of omission into a build failure.
ARCHITECTURE: ``check_feedback_writers`` is a pure read-only function over three files
    (agent definitions, the feedback categories file, the agent registry) returning
    ``missing_writers`` / ``unknown_writers`` / ``failures`` / ``warnings``.
    ``run_feedback_writer_check`` is the build-facing wrapper ``build.py::_validate_all``
    calls (re-exported through ``build_phases``), so ``--validate-only`` reaches it.
    The writer rule is NOT restated here: ``writer_allowed`` and ``HOOK_WRITER`` are
    loaded from ``templates/scripts/feedback/feedback_validation.py`` by path -- the
    same file submission uses, which the build deploys whole under
    ``scripts/feedback/`` (``_manifest_feedback_scripts``). Like every build-engine
    module this file runs against the package source, never from a deployed copy.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from build_colors import error as _error
from build_colors import warn as _warn

_VALIDATION_FILE = "feedback_validation.py"


def _load_validation() -> ModuleType:
    """Load the shared writer rule (``feedback_validation``) by path.

    Looks beside the package source's templates first, then in a sibling
    ``feedback/`` directory (a layout where the deploy copy is present).

    Returns:
        The loaded ``feedback_validation`` module.

    Raises:
        ImportError: When no candidate file exists or it cannot be loaded.
    """
    here = Path(__file__).resolve().parent
    candidates = [here.parent / "templates" / "scripts" / "feedback" / _VALIDATION_FILE,
                  here / "feedback" / _VALIDATION_FILE]
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("_feedback_validation_shared", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise ImportError(f"cannot find the shared writer rule {_VALIDATION_FILE}; tried: "
                      + ", ".join(str(p) for p in candidates))


def _read_frontmatter(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Parse ``path``'s YAML frontmatter strictly.

    Returns:
        ``(frontmatter, None)`` on success, ``(None, failure_message)`` otherwise.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"cannot read agent definition {path.name}: {exc}"
    end = text.find("\n---", 3) if text.startswith("---") else -1
    if end == -1:
        return None, f"agent definition {path.name} has no YAML frontmatter"
    try:
        front = yaml.safe_load(text[3:end])
    except yaml.YAMLError as exc:
        return None, f"agent definition {path.name} has malformed frontmatter: {exc}"
    if not isinstance(front, dict):
        return None, f"agent definition {path.name} frontmatter is not a mapping"
    return front, None


def _collect_signers(agents_dir: Path) -> tuple[list[str], list[str]]:
    """Return ``(sorted ids whose frontmatter sets signoff: true, failures)``.

    README.md and ``_``-prefixed partials carry no frontmatter and are skipped. An
    absent ``signoff`` means not required; a non-boolean value is a failure naming the file.
    """
    if not agents_dir.is_dir():
        return [], [f"agent definitions directory {agents_dir} is not readable"]
    signers: list[str] = []
    failures: list[str] = []
    for path in sorted(agents_dir.glob("*.md")):
        if path.name == "README.md" or path.name.startswith("_"):
            continue
        front, failure = _read_frontmatter(path)
        if front is None:
            failures.append(failure or f"agent definition {path.name} is unreadable")
        elif "signoff" in front and not isinstance(front["signoff"], bool):
            failures.append(f"agent definition {path.name} has a non-boolean signoff value: {front['signoff']!r}")
        elif front.get("signoff") is True:
            signers.append(path.stem)
    return signers, failures


def _load_categories(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return ``({category id: entry}, failures)`` from the feedback categories file."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return {}, [f"cannot read categories file {path.name}: {exc}"]
    entries = data.get("categories") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return {}, [f"categories file {path.name} has no 'categories' list"]
    cats: dict[str, dict[str, Any]] = {}
    for entry in entries:
        writers = entry.get("allowed_writers") if isinstance(entry, dict) else None
        if not (isinstance(writers, list) and all(isinstance(w, str) for w in writers)
                and isinstance(entry.get("id"), str)):
            return {}, [f"categories file {path.name} has a malformed category entry: {entry!r}"]
        cats[entry["id"]] = entry
    return cats, []


def _load_registry_ids(path: Path) -> tuple[set[str], list[str]]:
    """Return ``(registered agent ids, failures)`` from ``agent_registry.json``."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return set(), [f"cannot read agent registry {path.name}: {exc}"]
    agents = data.get("agents") if isinstance(data, dict) else None
    if not isinstance(agents, list) or not all(isinstance(a, dict) and "id" in a for a in agents):
        return set(), [f"agent registry {path.name} has no well-formed 'agents' list"]
    return {str(a["id"]) for a in agents}, []


def _unknown_writers(cats: dict[str, dict[str, Any]], registered: set[str], hook: str) -> list[dict[str, Any]]:
    """Writers that are neither the hook sentinel nor registered, each once with sorted categories."""
    seen: dict[str, set[str]] = {}
    for cid, entry in cats.items():
        for writer in entry["allowed_writers"]:
            if writer != hook and writer not in registered:
                seen.setdefault(writer, set()).add(cid)
    return [{"writer": w, "categories": sorted(c)} for w, c in sorted(seen.items())]


def check_feedback_writers(agents_dir: Path, categories_path: Path, registry_path: Path) -> dict[str, Any]:
    """Compare who signs off with who may write feedback. Read-only and deterministic.

    Args:
        agents_dir: Directory of agent definitions (``templates/agents``).
        categories_path: The feedback categories file.
        registry_path: ``config/agent_registry.json``.

    Returns:
        Dict with ``missing_writers`` (sorted ids that sign off and are admitted by no
        category), ``unknown_writers`` (``{"writer", "categories"}`` per unregistered
        writer), ``failures`` (blocking messages; one covers all missing writers) and
        ``warnings`` (one line per unknown writer).
    """
    result: dict[str, Any] = {"missing_writers": [], "unknown_writers": [], "failures": [], "warnings": []}
    signers, failures = _collect_signers(agents_dir)
    cats, cat_failures = _load_categories(categories_path)
    registered, reg_failures = _load_registry_ids(registry_path)
    result["failures"] = failures + cat_failures + reg_failures
    try:
        shared = _load_validation()
    except ImportError as exc:
        result["failures"].append(str(exc))
        return result
    if cat_failures:
        return result
    result["missing_writers"] = sorted(s for s in signers if not any(shared.writer_allowed(s, c, cats) for c in cats))
    if result["missing_writers"]:
        result["failures"].append(
            f"{', '.join(result['missing_writers'])}: each signs off (signoff: true) but can write to "
            f"no feedback category -- add it to allowed_writers in {categories_path.name}"
        )
    if not reg_failures:
        result["unknown_writers"] = _unknown_writers(cats, registered, shared.HOOK_WRITER)
    result["warnings"] = [
        f"feedback writer '{u['writer']}' names no registered agent (in categories: {', '.join(u['categories'])})"
        for u in result["unknown_writers"]
    ]
    return result


def run_feedback_writer_check(package_root: Path) -> int:
    """Run the check on the package's shipped files and print the report.

    Args:
        package_root: Root of the leafcutter package.

    Returns:
        1 when any failure was found, else 0 (warnings never fail the build).
    """
    result = check_feedback_writers(
        package_root / "templates" / "agents",
        package_root / "templates" / "config" / "feedback_categories.yaml",
        package_root / "config" / "agent_registry.json",
    )
    for line in result["warnings"]:
        _warn(line)
    for line in result["failures"]:
        _error(line)
    return 1 if result["failures"] else 0
