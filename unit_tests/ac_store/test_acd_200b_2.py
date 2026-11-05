"""
MODULE: test_acd_200b_2
GOAL: Red-first specification of ACD-200b-2: the documentation-trigger names are declared
    in exactly one list (the documentation_triggers enum of config/ac_store_schema.json)
    that the store's schema check (scripts/ac_store/validate_ac_schema.py) and the
    commit-time record check (templates/scripts/commit_guardian/check_ac_schema.py, incl.
    its no-jsonschema fallback validate_manually) both read; the rule check's
    trigger-to-specialist map (_rc_doc_triggers.TRIGGER_SPECIALISTS) has exactly one entry
    per name, and a parity check names any trigger missing from one side (ticket 01).
BUSINESS CONTEXT: Today the names live twice (the schema enum and
    validate_ac_schema._DOC_TRIGGER_VALUES) and the hook's fallback checks none of them, so
    one check can silently accept a name another rejects. "api-guide" is a fixture name.
ARCHITECTURE: Every validator runs on records written by the real serializer. The schema
    check and the commit hook run as real subprocesses over a tmp repo laid out like a
    consumer repo (<tmp>/config/ac_store_schema.json, <tmp>/docs/acceptance-criteria/);
    the schema check is expected to read the one list from the repo the record lives in
    (the same repo root it already infers for declared files), the hook from HOOK_ROOT.
    The hook is the SOURCE copy under templates/ (scripts/commit_guardian/ is a git-ignored
    build output). Contract read here: `_rc_doc_triggers.parity_errors(names, specialists)
    -> list[str]`, one message per one-sided name, naming the name and the side
    ("list" or "map") it is missing from.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    FAMILY_DOC_TRIGGERS,
    REPO_ROOT,
    SCRIPTS_DIR,
    check_store,
    findings_for,
    hierarchy,
    make_store,
)

_SCHEMA = REPO_ROOT / "config" / "ac_store_schema.json"
_VALIDATOR = SCRIPTS_DIR / "validate_ac_schema.py"
_HOOK_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_HOOK = _HOOK_DIR / "check_ac_schema.py"
_NEW = "api-guide"
_FIVE = ("how-to", "sequence-diagram", "state-diagram", "component-diagram", "reference-doc")


def _enum(schema: dict) -> list[str]:
    """The documentation_triggers name list of a parsed schema."""
    return schema["properties"]["documentation_triggers"]["oneOf"][0]["items"]["enum"]


def _shipped_schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _schema_with(names: list[str]) -> dict:
    """The shipped schema with the documentation_triggers list replaced by `names`."""
    schema = copy.deepcopy(_shipped_schema())
    _enum(schema)[:] = names
    return schema


def _l1(triggers: list[str], record_id: str = "ZZI-100") -> dict:
    """An L1 record both validators accept apart from its documentation_triggers."""
    return {
        "id": record_id, "title": f"Trigger probe {record_id}", "component": "ac-driven-dev",
        "components": ["ac_driven_dev"], "level": "L1", "status": "active",
        "created_by": "tickets/test.md", "priority": "medium", "readiness": "draft",
        "criteria": "Given a fixture record,\nWhen the check runs,\nThen it is a valid requirement.\n",
        "documentation_triggers": list(triggers),
    }


def _repo(root: Path, record: dict, schema: dict | None = None) -> Path:
    """A tmp consumer repo holding `schema` (default: verbatim shipped copy) and `record`."""
    (root / "config").mkdir(parents=True, exist_ok=True)
    if schema is None:
        shutil.copyfile(_SCHEMA, root / "config" / "ac_store_schema.json")
    else:
        (root / "config" / "ac_store_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    store = root / "docs" / "acceptance-criteria"
    store.mkdir(parents=True, exist_ok=True)
    target = store / f"{record['id']}.yaml"
    target.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return target


def _env(**extra: str) -> dict[str, str]:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", **extra}


def _schema_check(root: Path, record: dict, schema: dict | None = None) -> subprocess.CompletedProcess:
    """`python scripts/ac_store/validate_ac_schema.py <record>` with cwd = the tmp repo."""
    target = _repo(root, record, schema)
    return subprocess.run(
        [sys.executable, str(_VALIDATOR), str(target)], cwd=str(root), env=_env(),
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )


def _hook_check(root: Path, record: dict, schema: dict | None = None) -> subprocess.CompletedProcess:
    """The commit hook over the tmp repo, the record named as staged."""
    target = _repo(root, record, schema)
    return subprocess.run(
        [sys.executable, str(_HOOK)], cwd=str(root),
        env=_env(HOOK_ROOT=str(root), HOOK_TEST_STAGED_FILES=str(target), HOOK_NO_GIT="1"),
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )


def _out(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout + proc.stderr


def _import(directory: Path, name: str):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    __import__(name)
    return sys.modules[name]


def _is_guardian_module(module: object) -> bool:
    """True for a module loaded from any commit_guardian folder (template or deployed copy)."""
    file = getattr(module, "__file__", None)
    return isinstance(file, str) and Path(file).parent.name == "commit_guardian"


@contextlib.contextmanager
def _fresh_hook_module():
    """check_ac_schema loaded from templates/ under a unique name, its siblings fresh.

    Hermetic under xdist: a commit_guardian module another test cached in this worker
    (e.g. the deployed copy's _ac_schema_validators) is set aside, the template folder
    is put first on sys.path, and the worker's previous modules are restored afterwards.
    """
    saved = {name: mod for name, mod in sys.modules.items() if _is_guardian_module(mod)}
    for name in saved:
        del sys.modules[name]
    sys.path.insert(0, str(_HOOK_DIR))
    try:
        spec = importlib.util.spec_from_file_location("_acd_200b_2_check_ac_schema", _HOOK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(_HOOK_DIR))
        for name in [n for n, m in list(sys.modules.items()) if _is_guardian_module(m)]:
            del sys.modules[name]
        sys.modules.update(saved)


def test_record_check_rejects_unknown_trigger_and_accepts_reference_doc(tmp_path):
    # covers: ACD-200b-2
    # angle: reachability
    """validate_ac_schema.py as a subprocess in a tmp repo: [reference-doc, api-guide]
    exits non-zero naming api-guide; [reference-doc] alone exits 0."""
    rejected = _schema_check(tmp_path / "bad", _l1(["reference-doc", _NEW]))
    accepted = _schema_check(tmp_path / "good", _l1(["reference-doc"]))

    assert rejected.returncode != 0 and _NEW in _out(rejected), _out(rejected)
    assert accepted.returncode == 0, _out(accepted)


def test_commit_hook_rejects_unknown_trigger_and_accepts_reference_doc(tmp_path):
    # covers: ACD-200b-2
    # angle: reachability
    """check_ac_schema.py as a subprocess, HOOK_ROOT = the tmp repo and the record in
    HOOK_TEST_STAGED_FILES: non-zero naming api-guide; the reference-doc-only record passes."""
    rejected = _hook_check(tmp_path / "bad", _l1(["reference-doc", _NEW]))
    accepted = _hook_check(tmp_path / "good", _l1(["reference-doc"]))

    assert rejected.returncode != 0 and _NEW in _out(rejected), _out(rejected)
    assert accepted.returncode == 0, _out(accepted)


def test_commit_hook_fallback_without_jsonschema_rejects_unknown_trigger(tmp_path, monkeypatch):
    # covers: ACD-200b-2
    # angle: discrimination
    """check_ac_schema._validate_file with validate_with_jsonschema raising ImportError
    (so validate_manually runs): [reference-doc, api-guide] gets an error naming api-guide,
    [reference-doc] alone gets none, and a schema whose list adds api-guide makes the
    fallback accept it (the names come from the loaded schema, not a copy)."""
    def no_jsonschema(*_args, **_kwargs):
        raise ImportError  # jsonschema absent (simulated)

    bad = _repo(tmp_path / "bad", _l1(["reference-doc", _NEW]))
    good = _repo(tmp_path / "good", _l1(["reference-doc"]))

    with _fresh_hook_module() as hook:
        monkeypatch.setattr(hook, "validate_with_jsonschema", no_jsonschema)
        bad_errors = hook._validate_file(bad, _shipped_schema())
        good_errors = hook._validate_file(good, _shipped_schema())
        widened_errors = hook._validate_file(bad, _schema_with([*_FIVE, _NEW]))

    assert any(_NEW in e for e in bad_errors), bad_errors
    assert good_errors == [], good_errors
    assert widened_errors == [], widened_errors


def test_rule_check_reports_unknown_trigger_and_accepts_reference_doc(tmp_path):
    # covers: ACD-200b-2
    # angle: criterion
    """The requirement rule check reports api-guide on the L1 as a failed finding and
    raises no unknown-trigger finding for reference-doc (covered by a
    documentation-expert record)."""
    doc_child = {
        "assigned_agent": "documentation-expert",
        "declared_files": [{"path": "docs/_fixture_doc_200b_2.md", "state": "to_be_created"}],
    }
    store = make_store(tmp_path, hierarchy(
        "ACD-9990", 2, l1={"documentation_triggers": ["reference-doc", _NEW]}, child={2: doc_child},
    ))

    _, report = check_store(store)

    family = FAMILY_DOC_TRIGGERS
    found = findings_for(report, record_id="ACD-9990a", rule_family=family)
    unknown = [f for f in found if _NEW in f["message"]]
    assert [f["disposition"] for f in unknown] == ["failed"], found
    assert not any("reference-doc" in f["message"] for f in found), found


def test_trigger_names_live_in_one_list(tmp_path):
    # covers: ACD-200b-2
    # angle: discrimination
    """With a tmp repo whose schema list drops how-to, validate_ac_schema.py rejects
    how-to (it reads the list); validate_ac_schema holds no trigger-name collection of
    its own; TRIGGER_SPECIALISTS has exactly one key per name of the shipped list."""
    without_how_to = [name for name in _FIVE if name != "how-to"]
    proc = _schema_check(tmp_path, _l1(["how-to"]), _schema_with(without_how_to))
    assert proc.returncode != 0 and "how-to" in _out(proc), _out(proc)

    tree = ast.parse(_VALIDATOR.read_text(encoding="utf-8"))
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not (literals & set(_FIVE)), f"validate_ac_schema.py still names triggers: {sorted(literals & set(_FIVE))}"

    triggers = _import(SCRIPTS_DIR, "_rc_doc_triggers")
    assert sorted(triggers.TRIGGER_SPECIALISTS) == sorted(_enum(_shipped_schema()))


def test_sixth_name_is_accepted_after_one_list_edit(tmp_path, monkeypatch):
    # covers: ACD-200b-2
    # angle: discrimination
    """A tmp repo whose schema list adds api-guide, plus api-guide in TRIGGER_SPECIALISTS:
    validate_ac_schema.py, check_ac_schema.py and the rule check all accept api-guide."""
    widened = _schema_with([*_FIVE, _NEW])
    record = _l1(["reference-doc", _NEW])

    schema_check = _schema_check(tmp_path / "cli", record, widened)
    assert schema_check.returncode == 0, _out(schema_check)
    hook_check = _hook_check(tmp_path / "hook", record, widened)
    assert hook_check.returncode == 0, _out(hook_check)

    triggers = _import(SCRIPTS_DIR, "_rc_doc_triggers")
    monkeypatch.setitem(triggers.TRIGGER_SPECIALISTS, _NEW, "documentation-expert")
    doc_child = {
        "assigned_agent": "documentation-expert",
        "declared_files": [{"path": "docs/_fixture_doc_200b_2.md", "state": "to_be_created"}],
    }
    store = make_store(tmp_path / "rc", hierarchy(
        "ACD-9990", 2, l1={"documentation_triggers": ["reference-doc", _NEW]}, child={2: doc_child},
    ))
    store.schema.write_text(json.dumps(widened, indent=2), encoding="utf-8")
    _, report = check_store(store, "--schema", str(store.schema))
    assert not any(_NEW in f["message"] for f in report["findings"]), report["findings"]


def test_list_and_map_parity_names_trigger_and_side():
    # covers: ACD-200b-2
    # angle: discrimination
    """parity_errors passes on the shipped list and map; a list with an extra api-guide
    fails naming api-guide and the map side; a map with an extra key fails naming that key
    and the list side; both at once (same counts) report both."""
    triggers = _import(SCRIPTS_DIR, "_rc_doc_triggers")
    parity = getattr(triggers, "parity_errors", None)
    assert callable(parity), "_rc_doc_triggers must expose parity_errors(names, specialists) -> list[str]"
    names = list(_enum(_shipped_schema()))
    specialists = dict(triggers.TRIGGER_SPECIALISTS)

    assert parity(names, specialists) == []

    list_only = parity([*names, _NEW], specialists)
    assert len(list_only) == 1 and _NEW in list_only[0] and "map" in list_only[0], list_only

    map_only = parity(names, {**specialists, "how-to-guide": "documentation-expert"})
    assert len(map_only) == 1 and "how-to-guide" in map_only[0] and "list" in map_only[0], map_only

    both = parity([*names, _NEW], {**specialists, "how-to-guide": "documentation-expert"})
    assert len(both) == 2, both
    assert any(_NEW in m and "map" in m for m in both) and any("how-to-guide" in m and "list" in m for m in both)


def test_unloadable_schema_does_not_reject_every_trigger(tmp_path, monkeypatch):
    # covers: ACD-200b-2
    # angle: discrimination
    """With no schema passed and the shipped schema unloadable there is no list to check against:
    a record with a valid trigger is not reported as having invalid values ('Valid values: []')."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import validate_ac_schema as vas

    monkeypatch.setattr(vas, "load_ac_store_schema", lambda *_a, **_k: (None, "schema file not found - SKIPPED"))
    target = _repo(tmp_path, _l1(["reference-doc"]))
    errors = vas._validate_file(target, {"ac_driven_dev"})
    assert not [e for e in errors if "invalid values" in e or "Valid values: []" in e], errors
