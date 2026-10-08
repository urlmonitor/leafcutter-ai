"""MODULE: artifact_validation.py
GOAL: Require completed canonical validation before artifact evaluation can pass.
BUSINESS CONTEXT: Crashes and unavailable target contracts are not baseline noise.
ARCHITECTURE: Parse subprocess reports and call the existing scoped contract CLI.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

CONTRACTS_REL = "docs/product-truth/scripts/product_truth_contracts.py"


def _report(proc: subprocess.CompletedProcess, label: str) -> dict:
    """Require a normal validator exit and a structured report before scoring."""
    try:
        value = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"{label} unavailable: {(proc.stderr or '')[-800:]}") from exc
    if proc.returncode not in (0, 1) or not isinstance(value, dict):
        raise ValueError(f"{label} unavailable (exit {proc.returncode})")
    return value


def store_errors(proc: subprocess.CompletedProcess) -> set[str]:
    """Extract store errors only from a completed authoritative validator run."""
    prefix = "FAIL: "
    errors = {line[len(prefix):] for line in (proc.stderr or "").splitlines() if line.startswith(prefix)}
    report = _report(proc, "Product-truth validator")
    if report.get("outcome") not in {"checked-and-sound", "failed", "degraded", "nothing-examined"}:
        raise ValueError("Product-truth validator did not report a recognized outcome")
    if proc.returncode != 0 and not errors:
        raise ValueError("Product-truth validator did not complete its checks: " + (proc.stderr or "")[-800:])
    return errors


def target_errors(store: Path, target_obj: dict | None, run_script: Callable) -> list[str]:
    """Check exactly one selected flow in a fresh process, independently of baseline."""
    if target_obj is None:
        return ["no target flow produced"]
    target_id = target_obj.get("id")
    if not isinstance(target_id, str) or not target_id:
        return ["target flow has no valid id"]
    sandbox = store.parent.parent
    proc = run_script(sandbox, CONTRACTS_REL,
                      ["--repo-root", str(sandbox), "--check", "--flow-id", target_id], 180)
    report = _report(proc, "Target contract validation")
    errors = report.get("errors")
    if not isinstance(errors, list) or any(not isinstance(error, str) for error in errors):
        raise ValueError("Target contract validation returned no error list")
    if not errors and (proc.returncode != 0 or report.get("checked_flows") != 1):
        raise ValueError("Target contract validation did not check exactly one flow")
    return errors


# DECISION HISTORY
# ================================================================================
# - 2026-10-05 06:37 [python-coder]: Keep validator completion checks explicit without growing the oversized harness. (#TICKETLESS reason=user-authorized-evaluation-repair)
