"""Coordinator-authored AC completion metadata included in the reviewed commit."""

import logging
from pathlib import Path

import yaml

from .execution_boundary import ExecutorError
from .planning import _parent

LOGGER = logging.getLogger(__name__)


def complete_ac(workspace, plan, ac_id, changed_paths, *, completed_ac_ids=()):
    """Record completion only after checks; reject changes to approved requirements."""
    root = Path(workspace).resolve()
    ac_root = root / "docs" / "acceptance-criteria"
    obligations = plan["source_context"]["obligations"]
    if ac_id not in plan["ac_ids"] or ac_id not in obligations:
        raise ExecutorError("Completion AC is outside the approved plan")
    records = {}
    completed = set(completed_ac_ids) | {ac_id} | set(plan["source_context"].get("completed_context_ids", []))
    baseline = plan["source_context"].get("completion_baseline", {})
    proven = set(completed)
    for _ in obligations:
        for identifier, item in obligations.items():
            children = {child for child, value in obligations.items() if _parent(child, value) == identifier}
            declared = set(item.get("covered_by") or [])
            if item.get("level") == "L0" and not declared:
                continue
            children.update(child for child in declared if "/" not in child)
            if children and children.issubset(proven):
                proven.add(identifier)
    try:
        for identifier, expected in obligations.items():
            paths = list(ac_root.rglob(identifier + ".yaml"))
            if len(paths) != 1:
                raise ExecutorError("Approved AC must have exactly one worktree record: " + identifier)
            path = paths[0]
            if not path.resolve().is_relative_to(root):
                raise ExecutorError("AC record escapes the owned worktree")
            raw = path.read_text(encoding="utf-8")
            record = yaml.safe_load(raw)
            if not isinstance(record, dict) or any(record.get(key) != value for key, value in expected.items()):
                raise ExecutorError("Model/worktree changed approved AC requirements: " + identifier)
            if (record.get("work_status") == "done" and identifier not in proven
                    and baseline.get(identifier, {}).get("work_status") != "done"):
                raise ExecutorError("Unproven model-authored completion claim: " + identifier)
            records[identifier] = (path, record, raw)
        path, record, raw = records[ac_id]
        existing = record.get("implemented_by") or []
        if not isinstance(existing, list) or any(not isinstance(item, str) for item in existing):
            raise ExecutorError("AC implemented_by must be a list of repository paths")
        evidence = set()
        for name in [*existing, *changed_paths]:
            relative = name.split("#", 1)[0]
            candidate = (root / relative).resolve()
            if (candidate.is_relative_to(root) and candidate.is_file()
                    and not candidate.is_relative_to(ac_root.resolve())
                    and not ({".git", ".leafcutter"} & set(Path(relative).parts))):
                evidence.add(candidate.relative_to(root).as_posix())
        if not evidence:
            raise ExecutorError("Successful AC needs an existing implementation/documentation evidence path")
        record["work_status"] = "done"
        record["implemented_by"] = sorted(evidence)
        # Roll up only known approved obligations. A root with undeclared sibling
        # features must never become done merely because this feature finished.
        changed = True
        while changed:
            changed = False
            for identifier, (_, parent, _) in records.items():
                if identifier in completed or parent.get("level") not in {"L0", "L1", "L2"}:
                    continue
                children = {child for child, (_, item, _) in records.items() if _parent(child, item) == identifier}
                declared = set(parent.get("covered_by") or [])
                if parent.get("level") == "L0" and not declared:
                    continue
                children.update(child for child in declared if child not in children and "/" not in child)
                if children and children.issubset(completed):
                    parent["work_status"] = "done"
                    parent["implemented_by"] = sorted(evidence)
                    completed.add(identifier)
                    changed = True
        wrote = False
        for identifier, (path, item, raw) in records.items():
            if identifier not in completed or item.get("work_status") != "done":
                continue
            updated = yaml.safe_dump(item, sort_keys=False, allow_unicode=True, width=100)
            if updated != raw:
                path.write_text(updated, encoding="utf-8")
                wrote = True
        return wrote
    except (OSError, yaml.YAMLError) as exc:
        LOGGER.warning("Cannot persist checked AC completion: %s", type(exc).__name__)
        raise ExecutorError("Cannot persist checked AC completion metadata") from exc
