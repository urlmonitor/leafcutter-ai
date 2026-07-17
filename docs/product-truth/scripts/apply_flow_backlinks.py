"""Reconcile a flow's ``step.implements[]`` back-links, then regenerate derived data.

WHAT THIS CLOSES (UXP-402 gap): the ``business-analyst`` derives L2/L3 ACs from an
approved flow's steps and *reports* a ``flow_backlinks`` map (step id -> [AC ids]),
but it does NOT write ``step.implements`` itself — the link direction of truth is
flow -> AC (``step.implements``). This script is the reconciliation step that
writes those authored edges into the ``.flow.json`` and then re-runs
``generate_product_truth.py`` so every derived field (each node's ``impl_status``,
the flow ``impl_summary``, ``index.json`` ``by_ac``/``by_flow``, and each AC's
``product_truth`` back-ref) is recomputed to match.

It is invoked by ``/plan-feature`` AFTER the business-analyst stage as a dedicated
reconciliation commit (it re-mutates already-committed flow + index + AC files, so
it cannot be folded into a stage commit), and it is exposed as a clean argparse CLI
so it is unit-testable directly against a real on-disk flow fixture.

IDEMPOTENCE: applying the same ``flow_backlinks`` map twice is a no-op the second
time — new AC ids are unioned into ``implements`` (order preserved), so re-running
never duplicates an edge and the regenerated derived data is byte-stable.

ERROR HANDLING: every file read/write and the generator subprocess call is wrapped
in try/except with a SPECIFIC exception type that logs and re-raises (or wraps).
No bare except; no blind ``except Exception``.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("apply_flow_backlinks")

STORE = Path(__file__).resolve().parent.parent
GENERATOR = Path(__file__).resolve().parent / "generate_product_truth.py"


class BacklinkError(Exception):
    """Raised when a flow or backlinks payload cannot be resolved or applied."""


# --------------------------------------------------------------------------- #
# I/O boundary (typed try/except, log + re-raise per repo error-handling policy)
# --------------------------------------------------------------------------- #
def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        logger.exception("cannot read %s", path)
        raise


def _write_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except OSError:
        logger.exception("cannot write %s", path)
        raise


def _load_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except OSError:
        logger.exception("cannot read %s", path)
        raise
    except json.JSONDecodeError:
        logger.exception("invalid JSON in %s", path)
        raise


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #
def resolve_flow_path(flow: str, store: Path = STORE) -> Path:
    """Resolve a flow id or path to the concrete ``.flow.json`` file on disk.

    Accepts either an existing filesystem path or a flow ``id`` (matched against
    every flow's ``"id"`` field under ``<store>/flows``).
    """
    candidate = Path(flow)
    if candidate.is_file():
        return candidate.resolve()

    flows_dir = store / "flows"
    for path in sorted(flows_dir.rglob("*.flow.json")):
        data = _load_json(path)
        if data.get("id") == flow:
            return path.resolve()

    msg = f"no flow file found for '{flow}' under {flows_dir}"
    raise BacklinkError(msg)


def load_backlinks(*, file: str | None, inline: str | None) -> dict:
    """Load the ``flow_backlinks`` map (step id -> [AC ids]) from a file or inline JSON."""
    if inline is not None:
        try:
            data = json.loads(inline)
        except json.JSONDecodeError as exc:
            msg = f"--backlinks-json is not valid JSON: {exc}"
            raise BacklinkError(msg) from exc
    elif file is not None:
        data = _load_json(Path(file))
    else:
        msg = "exactly one of --backlinks-file / --backlinks-json is required"
        raise BacklinkError(msg)

    if not isinstance(data, dict):
        msg = "flow_backlinks payload must be a JSON object {step_id: [ac_ids]}"
        raise BacklinkError(msg)
    return data


# --------------------------------------------------------------------------- #
# Pure application logic
# --------------------------------------------------------------------------- #
def apply_backlinks(flow: dict, backlinks: dict) -> tuple[bool, list[str]]:
    """Union each backlink's AC ids into the matching node's ``implements[]``.

    Steps AND branches are matched by ``id``. The union preserves existing order
    and appends only genuinely-new ids, so re-applying the same map is a no-op
    (idempotent). Returns ``(changed, unknown_step_ids)``.
    """
    nodes = {node["id"]: node for node in flow.get("steps", [])}
    for branch in flow.get("branches", []):
        nodes.setdefault(branch["id"], branch)

    changed = False
    unknown: list[str] = []
    for step_id, ac_ids in backlinks.items():
        node = nodes.get(step_id)
        if node is None:
            unknown.append(step_id)
            continue
        existing = list(node.get("implements", []))
        merged = list(existing)
        for ac_id in ac_ids:
            if ac_id not in merged:
                merged.append(ac_id)
        if merged != existing:
            node["implements"] = merged
            changed = True
    return changed, unknown


# --------------------------------------------------------------------------- #
# Generator subprocess
# --------------------------------------------------------------------------- #
def run_generator(generator: Path = GENERATOR) -> None:
    """Re-run ``generate_product_truth.py`` so all derived fields are recomputed."""
    try:
        result = subprocess.run(
            [sys.executable, str(generator)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        logger.exception("cannot invoke generator %s", generator)
        msg = f"generator subprocess failed to start: {exc}"
        raise BacklinkError(msg) from exc

    if result.returncode != 0:
        logger.error("generator failed (exit %s): %s", result.returncode, result.stderr)
        msg = f"generate_product_truth.py exited {result.returncode}"
        raise BacklinkError(msg)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def reconcile(
    flow: str,
    backlinks: dict,
    *,
    store: Path = STORE,
    generator: Path = GENERATOR,
    skip_generate: bool = False,
) -> bool:
    """Write ``flow_backlinks`` into the flow then regenerate derived data.

    Returns True when the flow file's ``implements`` edges changed. The generator
    always runs (unless ``skip_generate``) so derived data is reconciled even when
    the edges were already present (idempotent path).
    """
    flow_path = resolve_flow_path(flow, store=store)
    flow_data = _load_json(flow_path)

    changed, unknown = apply_backlinks(flow_data, backlinks)
    for step_id in unknown:
        logger.warning("flow '%s' has no step/branch '%s' — backlink skipped", flow, step_id)

    if changed:
        new_text = json.dumps(flow_data, indent=2, ensure_ascii=False) + "\n"
        _write_text(flow_path, new_text)
        logger.info("wrote step.implements back-links into %s", flow_path)
    else:
        logger.info("no new back-links for %s (already reconciled)", flow_path)

    if not skip_generate:
        run_generator(generator)
        logger.info("regenerated product-truth derived data")

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a flow's step.implements back-links, then regenerate derived product-truth data."
    )
    parser.add_argument("--flow", required=True, help="Flow id (e.g. fern-and-fig/checkout-and-pay) or path to a .flow.json")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backlinks-file", help="Path to a JSON file mapping step_id -> [ac_ids].")
    group.add_argument("--backlinks-json", help="Inline JSON mapping step_id -> [ac_ids].")
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Write back-links only; do NOT re-run generate_product_truth.py (for testing).",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(message)s")

    try:
        backlinks = load_backlinks(file=args.backlinks_file, inline=args.backlinks_json)
        reconcile(args.flow, backlinks, skip_generate=args.skip_generate)
    except BacklinkError as exc:
        logger.error("FAIL: %s", exc)
        return 1
    logger.info("OK: flow back-links reconciled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
