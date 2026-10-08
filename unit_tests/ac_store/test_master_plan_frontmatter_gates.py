"""
MODULE: unit_tests/ac_store/test_master_plan_frontmatter_gates.py
GOAL: Prove that the Master_Plan the epic generator writes passes the repository's
      own frontmatter gates with no hand editing (ACD-1200a-8-i).
BUSINESS CONTEXT: The generated Master_Plan used to omit fields both gates require,
      so every generated epic had to be hand-fixed before it could be committed.
      These tests generate a real epic in a temporary AC store and then RUN the
      real gates over the real file. They hold no list of required field names:
      the gates' own required sets decide (a test-side list would be a second copy
      of the requirement that drifts exactly as the generator did).

The two gates
    check-doc-frontmatter    scripts/commit_guardian/check_doc_frontmatter.py, run as
                             a subprocess with the real commit_guardian.json. The file
                             must sit under a ``tickets/`` relative path, or the gate
                             skips it and "passes" vacuously, so the temp root is a
                             git repo and the plan lives under tickets/00_inbox/epics.
    ticket_frontmatter_guard templates/hooks/ticket_frontmatter_guard.py::validate,
                             loaded from its real file.

Ticket fixtures come from a fake of the ticket-generation subprocess whose
frontmatter is written with yaml.safe_dump; the Master_Plan under test is always
the real generator's output.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_GUARDIAN_DIR = _SCRIPTS_DIR / "commit_guardian"
_GUARD_PATH = _REPO_ROOT / "templates" / "hooks" / "ticket_frontmatter_guard.py"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import goal_to_epic  # noqa: E402

AC_ID = "MPG-1"
_OMIT = object()  # per_ac value: leave this key out, as the real generator does

_DRIVER = (
    "import sys; sys.path.insert(0, sys.argv[1]); import config; "
    "config.TICKET_FM_REQUIRED_FIELDS.append(sys.argv[2]); "
    "sys.argv = ['check_doc_frontmatter.py', '--file', sys.argv[3]]; "
    "import check_doc_frontmatter as m; sys.exit(m.main())"
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_ac(store: Path, ac_id: str, title: str, *, level: str = "L2",
              covered_by: list[str] | None = None) -> None:
    """Write one AC YAML via yaml.safe_dump into the temporary store."""
    sub = store / "test-component"
    sub.mkdir(parents=True, exist_ok=True)
    data = {
        "id": ac_id, "title": title, "component": "build-orchestration",
        "level": level, "status": "active", "work_status": "todo",
        "readiness": "approved", "priority": "medium",
        "estimated_complexity": "S", "depends_on": [],
        "covered_by": covered_by or [], "amended_by": [],
        "implemented_by": [], "superseded_by": None,
    }
    (sub / f"{ac_id}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _ticket_writer(store: Path, per_ac: dict[str, dict]):
    """Fake of the ticket-generation subprocess; frontmatter via yaml.safe_dump."""
    def _writer(ac_id: str, _store: Path, tickets_root: Path) -> str:
        fm = {
            "title": f"Ticket for {ac_id}", "status": "todo",
            "components": ["test-component"], "created": "2026-10-06",
            "depends_on": [], "source_ac": ac_id,
            "agents": {"python-coder": "needed"},
            "change_target": ["code"], "risk_surface": "internal",
            "requires_diagram": False, "requires_adr": False,
        }
        fm.update(per_ac.get(ac_id, {}))
        fm = {k: v for k, v in fm.items() if v is not _OMIT}
        path = tickets_root / f"TICKET-{ac_id}.md"
        path.write_text(f"---\n{yaml.safe_dump(fm)}---\n\n# {ac_id}\n", encoding="utf-8")
        rel = str(path.resolve().relative_to(tickets_root.resolve().parent.parent))
        for yp in sorted(store.rglob("*.yaml")):
            data = yaml.safe_load(yp.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("id") == ac_id:
                data["implemented_by"] = [rel]
                yp.write_text(yaml.safe_dump(data), encoding="utf-8")
        return str(path.resolve())
    return _writer


def _make_root(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return (root, store, inbox); root is a git repo so the gate resolves it."""
    root = tmp_path.resolve()
    store, inbox = root / "ac_store", root / "tickets" / "00_inbox"
    store.mkdir()
    inbox.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root, store, inbox


def _generate(tmp_path: Path, *, via: str = "ids", title: str = "Ship the parts",
              per_ac: dict[str, dict] | None = None,
              leaves: list[str] | None = None,
              epic_name: str | None = None) -> tuple[Path, Path]:
    """Generate a real epic; return (temp root, the generated Master_Plan.md)."""
    root, store, inbox = _make_root(tmp_path)
    leaves = leaves or [f"{AC_ID}-a"]
    for leaf in leaves:
        _write_ac(store, leaf, f"Leaf {leaf}")
    writer = _ticket_writer(store, per_ac or {})
    # epic_name pins the folder name only: _derive_epic_name keeps ':' from a title,
    # which Windows cannot create as a directory (separate defect, out of scope here).
    name_patch = (patch("epic_pipeline._derive_epic_name", return_value=epic_name)
                  if epic_name else patch.dict("os.environ", {}))
    with patch("epic_tickets._call_generate_ticket_from_ac", side_effect=writer), name_patch:
        if via == "run":
            _write_ac(store, AC_ID, title, level="L0", covered_by=leaves)
            epic = goal_to_epic.run(AC_ID, store, inbox, worktree_root=root,
                                    yes=True, approved_only=True)
        else:
            _write_ac(store, leaves[0], title)
            epic = goal_to_epic.build_epic_from_ids(leaves, store_root=store, inbox_dir=inbox)
    return root, Path(epic) / "Master_Plan.md"


def _frontmatter(plan: Path) -> dict:
    """Parse the plan's frontmatter block."""
    fm = yaml.safe_load(plan.read_text(encoding="utf-8").split("---", 2)[1])
    assert isinstance(fm, dict), "Master_Plan has no parseable frontmatter"
    return fm


def _doc_gate(root: Path, plan: Path, extra_required: str | None = None):
    """Run the real check-doc-frontmatter over the plan; return (rc, output)."""
    rel = plan.relative_to(root).as_posix()
    gate = _GUARDIAN_DIR / "check_doc_frontmatter.py"
    cmd = [sys.executable, str(gate), "--file", rel]
    if extra_required is not None:
        cmd = [sys.executable, "-c", _DRIVER, str(_GUARDIAN_DIR), extra_required, rel]
    done = subprocess.run(cmd, cwd=root, capture_output=True, encoding="utf-8",
                          errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return done.returncode, done.stdout + done.stderr


def _load_guard():
    spec = importlib.util.spec_from_file_location("tfg_under_test", _GUARD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("via", ["ids", "run"])
def test_generated_master_plan_passes_check_doc_frontmatter(tmp_path, via):
    # covers: ACD-1200a-8-i
    # angle: real_artifact
    """AC-1: the generated plan is accepted by the real check-doc-frontmatter."""
    root, plan = _generate(tmp_path, via=via)
    rc, out = _doc_gate(root, plan)
    assert rc == 0 and "PASSED: 1 doc" in out, f"gate rejected the generated plan:\n{out}"


@pytest.mark.parametrize("via", ["ids", "run"])
def test_generated_master_plan_passes_ticket_frontmatter_guard(tmp_path, via):
    # covers: ACD-1200a-8-i
    # angle: real_artifact
    """AC-2/AC-3: the real ticket guard returns no errors; title/type/depends_on set."""
    _root, plan = _generate(tmp_path, via=via, title="Ship the parts")
    guard = _load_guard()
    fm = guard.parse_frontmatter(plan.read_text(encoding="utf-8"))
    assert fm is not None, "guard could not parse the plan frontmatter"
    errors = guard.validate(fm, plan)
    assert errors == [], f"ticket_frontmatter_guard rejected the plan: {errors}"
    assert fm.get("title") == "EPIC: Ship the parts"
    assert fm.get("type") == "epic" and fm.get("depends_on") == []
    for kept in ("epic_name", "created", "status", "components", "source_ac"):
        assert kept in fm, f"existing field {kept!r} was dropped"


def test_gate_required_set_growth_fails_until_generator_emits_field(tmp_path):
    # covers: ACD-1200a-8-i
    # angle: discrimination
    """AC-6: with one more field in the gate's required set, the plan is rejected naming it.

    Precondition: the same plan passes the unmodified gate, so the rejection is
    attributable to the added field and not to an already-broken plan.
    """
    root, plan = _generate(tmp_path)
    rc0, out0 = _doc_gate(root, plan)
    assert rc0 == 0, f"plan must pass the unmodified gate first:\n{out0}"
    extra = "field_added_to_the_gate_later"
    rc, out = _doc_gate(root, plan, extra_required=extra)
    assert rc != 0, "gate accepted a plan lacking the newly required field"
    assert f"Missing required field: '{extra}'" in out, out


@pytest.mark.parametrize("values,expected", [
    ([True, False, None], True),
    ([False, None], False),
    ([None], None),
])
def test_requires_and_surface_roll_up_across_tickets(tmp_path, values, expected):
    # covers: ACD-1200a-8-i
    # angle: boundary
    """AC-4: tri-state roll-up for requires_*; change_target/risk_surface are unions."""
    leaves = [f"{AC_ID}-{i}" for i in range(len(values))]
    targets = [["code"], ["docs"], ["code", "config"]]
    surfaces = ["internal", "contract_boundary", "internal"]
    per_ac = {
        leaf: {"requires_diagram": v, "requires_adr": v,
               "change_target": targets[i], "risk_surface": surfaces[i]}
        for i, (leaf, v) in enumerate(zip(leaves, values))
    }
    root, plan = _generate(tmp_path, per_ac=per_ac, leaves=leaves)
    fm = _frontmatter(plan)
    if expected is not True:  # all-False / all-None plans must be accepted by both gates
        guard = _load_guard()
        assert guard.validate(guard.parse_frontmatter(plan.read_text(encoding="utf-8")),
                              plan) == []
        rc, out = _doc_gate(root, plan)
        assert rc == 0 and "PASSED: 1 doc" in out, out
    for key in ("requires_diagram", "requires_adr"):
        assert key in fm, f"{key} missing from the plan frontmatter"
        assert fm[key] is expected, f"{key}={fm[key]!r}, expected {expected!r}"

    def as_set(v):
        return set(v) if isinstance(v, list) else {v}

    n = len(values)
    want_t = {t for ts in targets[:n] for t in ts}
    assert "change_target" in fm and as_set(fm["change_target"]) == want_t
    assert "risk_surface" in fm and as_set(fm["risk_surface"]) == set(surfaces[:n])


def test_title_with_colon_round_trips(tmp_path):
    # covers: ACD-1200a-8-i
    # angle: failure
    """AC-5: a goal title with ':' and quotes survives a yaml.safe_load round trip."""
    title = 'Ship parts: the "fast" path'
    _root, plan = _generate(tmp_path, title=title, epic_name="ShipParts")
    assert _frontmatter(plan).get("title") == f"EPIC: {title}"


def test_missing_gate_fields_warn_and_guard_reports_exactly_them(tmp_path, capsys):
    # covers: ACD-1200a-8-i
    # angle: failure
    """M-1: tickets lacking change_target/risk_surface -> WARNING, empty lists, guard errors."""
    leaf = f"{AC_ID}-a"
    _root, plan = _generate(tmp_path, leaves=[leaf],
                            per_ac={leaf: {"change_target": _OMIT, "risk_surface": _OMIT}})
    warnings = [ln for ln in capsys.readouterr().err.splitlines() if ln.startswith("WARNING")]
    for field in ("change_target", "risk_surface"):
        assert any(field in ln and leaf in ln for ln in warnings), (field, warnings)
    fm = _frontmatter(plan)
    assert fm["change_target"] == [] and fm["risk_surface"] == []
    guard = _load_guard()
    errors = guard.validate(guard.parse_frontmatter(plan.read_text(encoding="utf-8")), plan)
    assert errors, "guard accepted a plan with empty change_target/risk_surface"
    flagged = {f for f in ("change_target", "risk_surface") if any(f in e for e in errors)}
    assert flagged == {"change_target", "risk_surface"}, errors
    assert all("change_target" in e or "risk_surface" in e for e in errors), errors
