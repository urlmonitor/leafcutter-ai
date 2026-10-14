"""
MODULE: _uxp_514_harness
GOAL: Shared fixture builders and CLI-run helpers for the UXP-514 / UXP-514-1..6
    drift-check tests (kept out of the test files for the 400-line ratchet).
BUSINESS CONTEXT: UXP-514's four checks (D1 impl_status, D2 product_truth
    back-references, D3 derived index lookups, D4 screen resolution) plus the
    D6 copied-scalar-field check agree by construction on the live store, so a
    test over an unmodified store proves nothing. Every negative here starts
    from a REAL, dependency-closed private copy of the store (copy_bounded_store)
    and edits it only through the real serializers (json / yaml.safe_dump).
ARCHITECTURE: No assertions live here. The reporting contract the tests pin
    (declared once, here, so the test files cannot drift apart):

      * Each check records itself in the run's `checks` bookkeeping under a
        fixed name, so the final stdout JSON line's `examined_by_check` carries
        `{name: <count of records it examined>}` when it ran:
            impl-status          D1  count = steps+branches whose status it recomputed
            product-truth-links  D2  count = criteria it inverted
            derived-indexes      D3  count = derived-lookup entries it compared
            screen-refs          D4  count = steps/branches naming a screen it resolved
            index-fields         D6  count = copied artifact fields it compared
      (the first, second, third and fourth names already exist in
      product_truth_outcome.CHECK_READS, where each states a POPULATION size
      -- flows / acceptance-criteria -- rather than the figure above.)
      * A check whose input set is empty is NOT listed in `examined_by_check`
        and the run prints a line (any log level) containing the check name and
        the phrase "not exercised" and the noun of the input it needed
        (impl_status / product_truth / derived / screen).
      * Findings are `FAIL: ...` (blocking) or `WARN: ...` lines on the real CLI.
"""
from __future__ import annotations

import atexit
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from unit_tests.product_truth._uxp_300_store import copy_bounded_store, write_json

TIMEOUT = 240
CHECKS = ("impl-status", "product-truth-links", "derived-indexes", "screen-refs")
INPUT_NOUN = {"impl-status": "impl_status", "product-truth-links": "product_truth",
              "derived-indexes": "derived", "screen-refs": "screen"}

_KEEP: list[tempfile.TemporaryDirectory] = []
_CACHE: dict[str, subprocess.CompletedProcess] = {}


def _cleanup() -> None:
    for tmp in _KEEP:
        tmp.cleanup()


atexit.register(_cleanup)


def new_store() -> Path:
    """A fresh, real, dependency-closed private copy of the store."""
    tmp = tempfile.TemporaryDirectory()
    _KEEP.append(tmp)
    return copy_bounded_store(Path(tmp.name) / "docs", extra_ac_ids=("UXP-514",))


def _run(store: Path, script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(store / "scripts" / script)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)


def run_validator(store: Path) -> subprocess.CompletedProcess:
    return _run(store, "validate_product_truth.py")


def run_generator(store: Path) -> subprocess.CompletedProcess:
    return _run(store, "generate_product_truth.py")


def cached_run(key: str, build=None) -> subprocess.CompletedProcess:
    """Run the CLI once per key per process; `build(store)` mutates the fresh store first."""
    if key not in _CACHE:
        store = new_store()
        if build is not None:
            build(store)
        _CACHE[key] = run_validator(store)
    return _CACHE[key]


def baseline() -> subprocess.CompletedProcess:
    return cached_run("baseline")


def output(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout + "\n" + proc.stderr


def lines(proc: subprocess.CompletedProcess, prefix: str) -> list[str]:
    return [ln for ln in output(proc).splitlines() if ln.startswith(prefix)]


def failures(proc) -> list[str]:
    return lines(proc, "FAIL: ")


def warnings(proc) -> list[str]:
    return lines(proc, "WARN: ")


def outcome(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout.strip().splitlines()[-1])


def examined(proc: subprocess.CompletedProcess) -> dict:
    return outcome(proc).get("examined_by_check", {})


# ---------------------------------------------------------------- store edits
def flow_files(store: Path) -> list[Path]:
    return sorted((store / "flows").rglob("*.flow.json"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def flow_path(store: Path, flow_id: str) -> Path:
    for path in flow_files(store):
        if load_json(path)["id"] == flow_id:
            return path
    raise KeyError(flow_id)


def nodes(flow: dict) -> list[dict]:
    return flow.get("steps", []) + flow.get("branches", [])


def edit_all_flows(store: Path, fn) -> None:
    for path in flow_files(store):
        flow = load_json(path)
        fn(flow)
        write_json(path, flow)


def edit_index(store: Path, fn) -> None:
    path = store / "index.json"
    index = load_json(path)
    fn(index)
    write_json(path, index)


def ac_files(store: Path) -> list[Path]:
    return sorted((store.parent / "acceptance-criteria").rglob("*.yaml"))


def edit_ac(path: Path, fn) -> None:
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    fn(record)
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")


def acs_with_product_truth(store: Path) -> list[tuple[Path, dict]]:
    found = []
    for path in ac_files(store):
        if path.name == "index.yaml":
            continue
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(record, dict) and record.get("product_truth") and record.get("id") == path.stem:
            found.append((path, record))
    return found


def set_readiness(store: Path, flow_id: str, readiness: str) -> None:
    """Change a journey's readiness in the journey AND its index mirror (no unrelated drift)."""
    path = flow_path(store, flow_id)
    flow = load_json(path)
    flow["readiness"] = readiness
    write_json(path, flow)

    def mirror(index):
        for art in index["artifacts"]:
            if art["id"] == flow_id:
                art["readiness"] = readiness
        if "readiness" in index.get("by_flow", {}).get(flow_id, {}):
            index["by_flow"][flow_id]["readiness"] = readiness
    edit_index(store, mirror)


def first_plain_step(store: Path) -> tuple[Path, dict, dict]:
    """A real step with a stated impl_status and no expands_to (status derives from its own criteria)."""
    for path in flow_files(store):
        flow = load_json(path)
        for step in flow.get("steps", []):
            if "expands_to" not in step and step.get("impl_status") and step.get("implements"):
                return path, flow, step
    raise LookupError("no plain step")


def registered_screens(store: Path) -> list[str]:
    return sorted({load_json(p).get("screen") for p in (store / "mockups").rglob("*.mockup.json")} - {None})


def sync_copied_scalar_fields(store: Path) -> None:
    """Make every scalar field the index copies equal its source (the live store has drifted)."""
    def sync(index):
        for art in index["artifacts"]:
            src = load_json(store / art["path"])
            for key in ("summary", "kind", "source", "component", "status", "readiness", "version", "screen"):
                if key in art and key in src:
                    art[key] = src[key]
            if "title" in art:
                art["title"] = src.get("title", src.get("name", art["title"]))
    edit_index(store, sync)


# ---------------------------------------------------------------- emptied inputs
def empty_impl_status(store: Path) -> None:
    def strip(flow):
        for node in nodes(flow):
            node.pop("impl_status", None)
    edit_all_flows(store, strip)


def empty_product_truth(store: Path) -> None:
    for path in ac_files(store):
        if path.name != "index.yaml":
            edit_ac(path, lambda rec: rec.pop("product_truth", None))


def empty_derived_indexes(store: Path) -> None:
    def clear(index):
        for key in ("by_component", "by_entity", "by_flow", "by_ac"):
            index[key] = {}
    edit_index(store, clear)


def empty_screens(store: Path) -> None:
    def strip(flow):
        for node in nodes(flow):
            node.pop("screen", None)
    edit_all_flows(store, strip)


EMPTIERS = {"impl-status": empty_impl_status, "product-truth-links": empty_product_truth,
            "derived-indexes": empty_derived_indexes, "screen-refs": empty_screens}


def emptied_run(check: str) -> subprocess.CompletedProcess:
    return cached_run(f"empty:{check}", EMPTIERS[check])


def not_exercised_lines(proc: subprocess.CompletedProcess, check: str) -> list[str]:
    return [ln for ln in output(proc).splitlines() if check in ln and "not exercised" in ln.lower()]
