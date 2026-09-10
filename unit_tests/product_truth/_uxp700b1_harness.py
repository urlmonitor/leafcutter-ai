"""
MODULE: _uxp700b1_harness
GOAL: Fixture builders shared by UXP-700b-1's test classes.
BUSINESS CONTEXT: test_uxp_700b_1.py ran to 446 content lines, over the
    400-line check-file-size limit, and the fixtures were the part all three
    of its test classes shared rather than the part any one of them was about.
    Extracting them keeps every assertion where it was and puts the store
    construction in one place. Named with a leading underscore so pytest never
    collects it as a test module.
ARCHITECTURE: Pure builders over a tempdir. `_make_sound_store` writes a
    complete, schema-valid store; `_make_empty_store` writes the zero-artifact
    counterpart; `_run_validate_in_process` calls the real validator's main()
    with STORE/AC_STORE redirected, and `_parse_outcome_payload` reads the
    machine-readable JSON contract line back off its stdout.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
from pathlib import Path
from unittest import mock

_PT_SRC = Path(__file__).resolve().parents[2] / "docs" / "product-truth"
_SCRIPTS_DIR = _PT_SRC / "scripts"
_REAL_SCHEMAS_DIR = _PT_SRC / "schemas"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402
import validate_product_truth as vpt  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixture builders — real serializer (json.dump), never a hand-typed literal,
# and the "sound" store's derived index is computed with the SAME generator
# functions the real generator uses (gpt.build_by_component / build_by_entity /
# build_by_flow / build_by_ac), so the fixture is provably self-consistent under
# every D1-D5 derived-vs-source check rather than hand-typed to happen to match.
# --------------------------------------------------------------------------- #
def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _make_empty_store(store_root: Path, ac_root: Path) -> None:
    """Materialize a product-truth store with zero flows, zero mock-data, zero mockups.

    This is UXP-700a-2's "zero-artifact record whose index is present and empty" —
    the record this AC's own `expects_from` contract names as the fixture that makes
    the empty case reachable at all.
    """
    for sub in ("flows", "mock-data", "mockups", "classifier"):
        (store_root / sub).mkdir(parents=True, exist_ok=True)
    shutil.copytree(_REAL_SCHEMAS_DIR, store_root / "schemas")
    (store_root / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    _write_json(
        store_root / "index.json",
        {
            "artifacts": [],
            "entity_registry": [],
            "by_component": {},
            "by_entity": {},
            "by_flow": {},
            "by_ac": {},
        },
    )
    ac_root.mkdir(parents=True, exist_ok=True)


def _make_sound_store(store_root: Path, ac_root: Path) -> None:
    """Materialize a store with one flow, one mock-data record set, and one mockup —
    at least one artifact of each type that satisfies every check (the Given
    clause's contrasting case). CONFIRMED by direct execution (see module docstring)
    to exit 0 with 0 errors AND 0 warnings against the UNMODIFIED production checker.
    """
    for sub in ("flows/leafcutter", "mock-data/leafcutter", "mockups/leafcutter", "classifier"):
        (store_root / sub).mkdir(parents=True, exist_ok=True)
    shutil.copytree(_REAL_SCHEMAS_DIR, store_root / "schemas")
    (store_root / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    ac_root.mkdir(parents=True, exist_ok=True)

    flow = {
        "id": "leafcutter/test-flow",
        "component": "leafcutter",
        "name": "Test Flow",
        "summary": "A minimal, fully-sound flow fixture for UXP-700b-1.",
        "kind": "user",
        "source": "mock",
        "status": "active",
        "readiness": "approved",
        "version": 1,
        "entities": ["Widget"],
        "mock_data_ref": "leafcutter/test-mock",
        "steps": [
            {
                "id": "step-a",
                "label": "Step A",
                "human": "The user sees the widget screen.",
                "order": 1,
                "screen": "test-screen",
                "reads": [],
                "writes": [],
                "implements": [],
                "impl_status": "not_started",
                "impl_asof": "2026-01-01",
            }
        ],
        "branches": [],
        "impl_summary": {"done": 0, "in_progress": 0, "not_started": 1, "total": 1, "asof": "2026-01-01"},
    }
    _write_json(store_root / "flows" / "leafcutter" / "test-flow.flow.json", flow)

    mock_data = {
        "id": "leafcutter/test-mock",
        "component": "leafcutter",
        "status": "active",
        "readiness": "approved",
        "version": 1,
        "invariants": [],
        "entities": {
            "Widget": {
                "fields": {"id": "string"},
                "records": [{"id": "widget-1"}],
            }
        },
    }
    _write_json(store_root / "mock-data" / "leafcutter" / "test-mock.mock.json", mock_data)

    mockup = {
        "id": "leafcutter/test-screen",
        "component": "leafcutter",
        "screen": "test-screen",
        "title": "Test Screen",
        "summary": "A minimal, fully-sound mockup fixture for UXP-700b-1.",
        "entities": ["Widget"],
        "source": "mock",
        "renders": None,
        "status": "active",
        "readiness": "approved",
        "version": 1,
        "provenance": [],
    }
    _write_json(store_root / "mockups" / "leafcutter" / "test-screen.mockup.json", mockup)

    # Rebuild the derived index with the SAME generator functions the real
    # generator uses (mirrors _run_generate's STORE/AC_STORE redirection pattern
    # in unit_tests/test_generate_product_truth_idempotency.py).
    original_store, original_ac_store = gpt.STORE, gpt.AC_STORE
    gpt.STORE, gpt.AC_STORE = store_root, ac_root
    try:
        flows, flow_paths = gpt.load_flows()
        mocks = gpt.load_mocks()
        artifacts = [
            {
                "id": flow["id"], "type": "flow", "component": flow["component"],
                "status": flow["status"], "readiness": flow["readiness"], "version": flow["version"],
            },
            {
                "id": mock_data["id"], "type": "mock_data", "component": mock_data["component"],
                "status": mock_data["status"], "readiness": mock_data["readiness"],
                "version": mock_data["version"],
            },
            {
                "id": mockup["id"], "type": "mockup", "component": mockup["component"],
                "status": mockup["status"], "readiness": mockup["readiness"], "version": mockup["version"],
            },
        ]
        index = {
            "artifacts": artifacts,
            "entity_registry": ["Widget"],
            "by_component": gpt.build_by_component(artifacts),
            "by_entity": gpt.build_by_entity(flows, mocks),
            "by_flow": gpt.build_by_flow(flows, flow_paths, {}, run_date="2026-01-01"),
            "by_ac": gpt.build_by_ac(flows, run_date="2026-01-01"),
        }
    finally:
        gpt.STORE, gpt.AC_STORE = original_store, original_ac_store
    _write_json(store_root / "index.json", index)


def _run_validate_in_process(store_root: Path, ac_root: Path) -> tuple[int, str]:
    """Run validate_product_truth.main() against a fixture store, in-process.

    Redirects the module-level STORE/AC_STORE on BOTH validate_product_truth and
    generate_product_truth (the imported derivation functions close over
    generate_product_truth's OWN globals — see _run_generate in
    unit_tests/test_generate_product_truth_idempotency.py for the same pattern).
    Returns (exit_code, captured_stdout).
    """
    ovs, ova = vpt.STORE, vpt.AC_STORE
    ogs, oga = gpt.STORE, gpt.AC_STORE
    vpt.STORE, vpt.AC_STORE = store_root, ac_root
    gpt.STORE, gpt.AC_STORE = store_root, ac_root
    stdout_buf = io.StringIO()
    try:
        with mock.patch.object(sys, "argv", ["validate_product_truth.py"]):
            with contextlib.redirect_stdout(stdout_buf):
                exit_code = vpt.main()
    finally:
        vpt.STORE, vpt.AC_STORE = ovs, ova
        gpt.STORE, gpt.AC_STORE = ogs, oga
    return exit_code, stdout_buf.getvalue()


def _parse_outcome_payload(stdout_text: str) -> dict:
    """Parse the machine-readable outcome payload from the checker's stdout.

    The LAST non-blank stdout line must be one JSON object carrying at least an
    "outcome" key, AND it must be the ONLY JSON-parseable line in the output —
    guarding against a regression that accidentally prints the payload twice, or
    prints it followed by stray debug output that happens to look like the real
    line. A store with no implementation of this contract at all (e.g. before
    UXP-700b-1's outcome vocabulary existed) prints nothing to stdout, which
    raises here — that was the intended red state before the shared-worktree
    implementation described in this module's docstring landed.
    """
    lines = [line for line in stdout_text.splitlines() if line.strip()]
    if not lines:
        raise AssertionError(
            "expected a machine-readable JSON outcome payload as the last line of "
            f"stdout; got no stdout output at all (stdout={stdout_text!r})"
        )
    json_line_count = 0
    for line in lines:
        try:
            json.loads(line)
        except json.JSONDecodeError:
            continue
        json_line_count += 1
    if json_line_count != 1:
        raise AssertionError(
            f"expected EXACTLY ONE JSON-parseable line on stdout (found "
            f"{json_line_count}); stdout={stdout_text!r}"
        )
    payload = json.loads(lines[-1])
    if not isinstance(payload, dict) or "outcome" not in payload:
        raise AssertionError(
            f"the last stdout line parsed as JSON but is not an outcome payload "
            f"(missing 'outcome' key): {payload!r}"
        )
    return payload
