"""
MODULE: test_km_kgs_100a_3_xi_deploy
GOAL: TDD stubs for KM-KGS-100a-3-xi -- deploy, drift, and the whole-repo
      .md frontmatter differential for the extracted reader module. See
      test_km_kgs_100a_3_xi.py's SPLIT NOTE for why this is a sibling
      module rather than one file: together the two implement all 15
      test_spec entries; the split is purely by concern to stay under the
      .py content-line limit (GE-127a-1), never a change to any test's
      name, body, or tags.
BUSINESS CONTEXT: see docs/acceptance-criteria/knowledge-management/
    KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100a-3-xi.yaml. Deploy tests
    follow unit_tests/build_guards/test_bp_100k_2.py's temp-workspace
    pattern, calling the real deploy phase function directly instead of a
    full build.py subprocess. The reader module does not exist yet, so
    every deploy test that needs it is discovered from the ten functions'
    __module__ attribute (never a hard-coded file name) and fails with a
    clear message naming the pre-extraction state. No test in this module
    ever calls pytest.skip.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_BUILD_GUARDS_DIR = _REPO_ROOT / "unit_tests" / "build_guards"
_TICKETS_DIR = _REPO_ROOT / "tickets"
_DOCS_DIR = _REPO_ROOT / "docs"
_PATHS_JSON = _REPO_ROOT / "config" / "paths.json"

sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_BUILD_GUARDS_DIR))

import knowledge_query as kq  # noqa: E402
from knowledge_query import _parse_frontmatter  # noqa: E402
import test_bp_100k_2 as _bp100k2  # noqa: E402

_READER_FUNCTION_NAMES = (
    "_find_frontmatter_end", "_strip_matched_quotes", "_split_flow_sequence_items",
    "_parse_scalar_value", "_line_indent", "_strip_inline_comment",
    "_is_mapping_item_text", "_parse_block_children", "_parse_frontmatter", "_parse_yaml_file",
)


def _subprocess_env():
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return env


def _discover_reader_module(kq_module):
    """Resolve the reader module from the ten functions' own __module__.

    Compact duplicate of test_km_kgs_100a_3_xi.py's helper of the same name
    (small, needed by both files -- not promoted to a shared non-test
    helper module under unit_tests/, which is not an existing convention
    here). See that file for the full discovery rationale. Never a
    hard-coded file name; raises a clear AssertionError (not an obscure
    crash) in every failure state, including the pre-extraction state.
    """
    module_names = {}
    for name in _READER_FUNCTION_NAMES:
        func = getattr(kq_module, name, None)
        assert func is not None, f"knowledge_query has no attribute {name!r}"
        module_names[name] = getattr(func, "__module__", None)
    distinct = set(module_names.values())
    if distinct == {"knowledge_query"}:
        raise AssertionError(
            "reader functions are still defined in knowledge_query.py -- "
            f"the KM-KGS-100a-3-xi extraction has not happened yet. {module_names}"
        )
    assert len(distinct) == 1, f"reader functions split across modules: {module_names}"
    reader_module_name = next(iter(distinct))
    reader_module = sys.modules.get(reader_module_name)
    assert reader_module is not None, f"reader module {reader_module_name!r} not in sys.modules"
    reader_file = getattr(reader_module, "__file__", None)
    assert reader_file and reader_file.endswith(".py"), f"reader module file {reader_file!r} invalid"
    assert Path(reader_file).resolve().parent == _SCRIPTS_DIR, (
        f"reader module file {reader_file!r} is not next to knowledge_query.py"
    )
    return reader_module


# ---------------------------------------------------------------------------
# Whole-repo .md frontmatter differential (test_spec entries 1-3)
# ---------------------------------------------------------------------------

_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _load_edge_fields_union():
    """Union of every edge_fields entry declared across paths.json surfaces,
    read from the config -- never a hard-coded list."""
    data = json.loads(_PATHS_JSON.read_text(encoding="utf-8"))
    return {f for s in data.get("surfaces", {}).values() for f in s.get("edge_fields", [])}


_EDGE_FIELDS = _load_edge_fields_union()


def _normalise(value):
    return [] if value is None else value


def _extract_frontmatter_block(text):
    """Return the raw text between the two '---' delimiters, or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


def _load_md_reference_mapping(text):
    """PyYAML (C loader when available) reference mapping for a .md file's
    frontmatter, or None when it does not read as a mapping."""
    frontmatter_text = _extract_frontmatter_block(text)
    if frontmatter_text is None:
        return None
    try:
        data = yaml.load(frontmatter_text, Loader=_LOADER)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _comparable_fields(reference_fields):
    """Edge fields eligible for comparison: declared in paths.json, present
    on the reference mapping, and a list whose items are all strings."""
    def _is_string_list(value):
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    return {f for f in _EDGE_FIELDS if f in reference_fields and _is_string_list(reference_fields[f])}


def _diff_md_record_fields(reader_fields, reference_fields):
    """Shared differential comparison step, reused by the whole-repo scan
    and by the forced-disagreement test below."""
    pairs = ((f, _normalise(reader_fields.get(f)), reference_fields[f]) for f in _comparable_fields(reference_fields))
    return [(f, rv, refv) for f, rv, refv in pairs if rv != refv]


def _scan_whole_repo_md():
    """One pass over every *.md file under tickets/ and docs/ with a
    '---' delimited frontmatter block that PyYAML reads as a mapping."""
    mismatches = []
    compared_counts = {}
    scanned = 0
    md_files = sorted(_TICKETS_DIR.glob("**/*.md")) + sorted(_DOCS_DIR.glob("**/*.md"))
    for md_file in md_files:
        try:
            text = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        reference = _load_md_reference_mapping(text)
        if reference is None:
            continue
        scanned += 1
        rel_path = str(md_file.relative_to(_REPO_ROOT))
        reader_fields = _parse_frontmatter(text)
        for field in _comparable_fields(reference):
            compared_counts[field] = compared_counts.get(field, 0) + 1
        for field, reader_value, reference_value in _diff_md_record_fields(reader_fields, reference):
            mismatches.append((rel_path, field, reader_value, reference_value))
    return mismatches, compared_counts, scanned


@pytest.fixture(scope="module")
def whole_repo_md_scan():
    assert _TICKETS_DIR.is_dir(), f"tickets/ not found at {_TICKETS_DIR}"
    assert _DOCS_DIR.is_dir(), f"docs/ not found at {_DOCS_DIR}"
    start = time.perf_counter()
    mismatches, compared_counts, scanned = _scan_whole_repo_md()
    elapsed = time.perf_counter() - start
    print(
        f"\n[KM-KGS-100a-3-xi] whole-repo .md differential runtime: "
        f"{elapsed:.2f}s over {scanned} files"
    )
    return mismatches, compared_counts, scanned, elapsed


def test_whole_repo_md_frontmatter_edge_values_match_reference_reader(whole_repo_md_scan):
    # covers: KM-KGS-100a-3-xi
    # angle: real_artifact
    """Every .md frontmatter file's string-list edge fields, read via the
    production _parse_frontmatter entry point, equal PyYAML's value for the
    same bytes. All mismatches are collected and reported together."""
    mismatches, _compared_counts, _scanned, _elapsed = whole_repo_md_scan
    assert not mismatches, "Reader/reference disagreement on real .md files:\n" + "\n".join(
        f"{path} field={field}: reader={reader_value!r} reference={reference_value!r}"
        for path, field, reader_value, reference_value in mismatches
    )


def test_whole_repo_md_differential_is_not_vacuous(whole_repo_md_scan):
    # covers: KM-KGS-100a-3-xi
    # angle: real_artifact
    """The scan checked at least 1000 files, and each of components,
    depends_on, files_touched and related_docs was compared at least once."""
    _mismatches, compared_counts, scanned, _elapsed = whole_repo_md_scan
    assert scanned >= 1000, f"only {scanned} files scanned -- expected at least 1000"
    required_fields = ("components", "depends_on", "files_touched", "related_docs")
    zero_compared = [f for f in required_fields if compared_counts.get(f, 0) == 0]
    assert not zero_compared, (
        f"field(s) with zero comparisons across {scanned} files: {zero_compared}"
    )


def test_md_differential_reports_every_forced_disagreement(tmp_path, monkeypatch):
    # covers: KM-KGS-100a-3-xi
    # angle: failure
    """Disagreement is forced synthetically, never by relying on a real
    reader bug: _parse_frontmatter is monkeypatched to disagree with PyYAML
    on two distinct files, and the shared differential step reports both."""
    file_a = tmp_path / "a.md"
    file_a.write_text(
        "---\nid: KM-EX-MD-FORCED-A\nrelated_docs:\n  - docs/example-a.md\n---\n\nBody\n",
        encoding="utf-8",
    )
    file_b = tmp_path / "b.md"
    file_b.write_text(
        "---\nid: KM-EX-MD-FORCED-B\ndepends_on:\n  - EXAMPLE-B\n---\n\nBody\n",
        encoding="utf-8",
    )

    def _fake_parse_frontmatter(_text):
        return {"related_docs": ["FORCED-WRONG"], "depends_on": ["FORCED-WRONG"]}

    monkeypatch.setattr(sys.modules[__name__], "_parse_frontmatter", _fake_parse_frontmatter)

    all_mismatches = []
    for md_file in (file_a, file_b):
        text = md_file.read_text(encoding="utf-8")
        reference = _load_md_reference_mapping(text)
        reader_fields = _parse_frontmatter(text)
        for field, reader_value, reference_value in _diff_md_record_fields(reader_fields, reference):
            all_mismatches.append((md_file.name, field, reader_value, reference_value))

    reported_names = {m[0] for m in all_mismatches}
    assert file_a.name in reported_names, "file_a's forced disagreement was not reported"
    assert file_b.name in reported_names, "file_b's forced disagreement was not reported"
    assert len(all_mismatches) >= 2, "expected at least one mismatch reported per forced file"


# ---------------------------------------------------------------------------
# Deploy / drift coverage (test_spec entries 11-13; entry 10 -- the deploy
# manifest test -- lives in test_km_kgs_100a_3_xi.py alongside the other
# reader-module-discovery-only checks, since it needs no synthetic package)
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_package(tmp_path):
    workspace = tmp_path
    pkg_root = _bp100k2._build_synthetic_full_package(workspace)
    snapshot = _bp100k2._snapshot_and_clear_build_phases_cache()
    try:
        yield workspace, pkg_root
    finally:
        _bp100k2._restore_build_phases_cache(snapshot)


def _deploy_workflow_tools(workspace, pkg_root):
    build_helpers_mod, build_phases_mod, config_loader_mod = _bp100k2._load_pkg_modules(pkg_root)
    config = config_loader_mod.load_config(None, workspace)
    build_phases_mod.build_workflow_tools(workspace, config, dry_run=False, force=True)
    return build_helpers_mod, build_phases_mod, config_loader_mod, config


def test_workflow_tools_phase_deploys_reader_module_byte_identical(synthetic_package):
    # covers: KM-KGS-100a-3-xi
    # angle: deployed
    """build_workflow_tools deploys knowledge_query.py and the reader module
    side by side into a temp target's scripts/, each byte-identical to its
    source."""
    workspace, pkg_root = synthetic_package
    reader_module = _discover_reader_module(kq)
    reader_name = Path(reader_module.__file__).name

    _deploy_workflow_tools(workspace, pkg_root)

    deployed_dir = workspace / "scripts"
    kq_deployed = deployed_dir / "knowledge_query.py"
    reader_deployed = deployed_dir / reader_name
    assert kq_deployed.is_file(), f"knowledge_query.py not deployed to {deployed_dir}"
    assert reader_deployed.is_file(), f"{reader_name} not deployed to {deployed_dir}"
    assert kq_deployed.read_bytes() == (pkg_root / "scripts" / "knowledge_query.py").read_bytes()
    assert reader_deployed.read_bytes() == (pkg_root / "scripts" / reader_name).read_bytes()


_AC_RECORD_TEXT_FIXTURE = (
    "id: KM-EX-DEPLOY-CHECK\nimplemented_by:\n  - scripts/example_module.py\n"
    "covered_by:\n  - unit_tests/test_example.py\ndepends_on:\n  - OTHER-AC-1\n"
    'components:\n  - "knowledge_management"  # primary component\n'
)

_DEPLOYED_READER_CHILD_TEMPLATE = '''
import importlib.util
import json
import sys
from pathlib import Path

KQ_PATH = Path(r"__KQ_PATH__")
RECORD_PATH = Path(r"__RECORD_PATH__")

sys.path[:] = [p for p in sys.path if Path(p).name != "scripts"]

spec = importlib.util.spec_from_file_location("knowledge_query", KQ_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["knowledge_query"] = mod
spec.loader.exec_module(mod)

text = RECORD_PATH.read_text(encoding="utf-8")
fields = mod._parse_yaml_file(text)
sys.stdout.write(json.dumps(fields, sort_keys=True))
'''


def test_deployed_knowledge_query_reads_ac_record_same_as_source(synthetic_package, tmp_path):
    # covers: KM-KGS-100a-3-xi
    # angle: deployed
    """From the temp deployment, a subprocess with no scripts/ on sys.path
    loads the DEPLOYED knowledge_query.py and reads a temp AC record to the
    same field values as the SOURCE knowledge_query._parse_yaml_file."""
    workspace, pkg_root = synthetic_package
    _deploy_workflow_tools(workspace, pkg_root)

    deployed_kq = workspace / "scripts" / "knowledge_query.py"
    assert deployed_kq.is_file(), f"knowledge_query.py not deployed to {deployed_kq}"

    record_path = tmp_path / "km_ex_deploy_check.yaml"
    record_path.write_text(_AC_RECORD_TEXT_FIXTURE, encoding="utf-8")

    script = _DEPLOYED_READER_CHILD_TEMPLATE.replace("__KQ_PATH__", str(deployed_kq)).replace(
        "__RECORD_PATH__", str(record_path)
    )
    script_path = tmp_path / "child_deployed_read.py"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=_subprocess_env(),
        timeout=30,
    )
    assert result.returncode == 0, (
        f"deployed knowledge_query.py failed to read the AC record. "
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    deployed_fields = json.loads(result.stdout.strip())
    source_fields = json.loads(json.dumps(kq._parse_yaml_file(_AC_RECORD_TEXT_FIXTURE), sort_keys=True))
    assert deployed_fields == source_fields


def test_output_drift_gate_reports_no_gap_for_reader_module(synthetic_package):
    # covers: KM-KGS-100a-3-xi
    # angle: deployed
    """With untouched deployed copies, the output-drift gate exits 0 and
    its output contains no GAP line naming the reader module or
    knowledge_query.py. Drift DETECTION for workflow-tool scripts is out of
    scope (SCOPE NOTE) and is not asserted."""
    workspace, pkg_root = synthetic_package
    build_helpers_mod, build_phases_mod, config_loader_mod = _bp100k2._load_pkg_modules(pkg_root)
    config = config_loader_mod.load_config(None, workspace)
    output_root = workspace / config.get("output_root", ".leafcutter")

    # build_agents (+ shims) populates at least one real output_mappings
    # entry, exactly as test_bp_100k_2's own drift-gate fixture does --
    # otherwise the manifest records ZERO output mappings overall (workflow
    # -tool scripts alone are never tracked, per the SCOPE NOTE) and
    # check_output_drift.py refuses the whole run rather than reporting a
    # clean, comparable RESULT with zero gaps.
    build_phases_mod.build_agents(output_root, config, dry_run=False, force=True)
    build_helpers_mod.install_shims(workspace, output_root=output_root, config=config, dry_run=False, force=True)
    build_phases_mod.build_workflow_tools(workspace, config, dry_run=False, force=True)
    build_helpers_mod.write_build_manifest(pkg_root, target_root=workspace, config=config, dry_run=False)

    hook_path = _bp100k2._deploy_hook(workspace, _bp100k2._CHECK_OUTPUT_DRIFT_SRC)
    result = _bp100k2._run_hook(hook_path, workspace)

    assert result.returncode == 0, (
        "check_output_drift.py must not block on an untouched deploy. "
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    reader_name = None
    try:
        reader_module = _discover_reader_module(kq)
        reader_name = Path(reader_module.__file__).name
    except AssertionError:
        reader_name = None

    combined = result.stdout + result.stderr
    for line in combined.splitlines():
        if "UNCOMPARABLE: GAP" not in line:
            continue
        assert "knowledge_query.py" not in line, f"GAP line names knowledge_query.py: {line}"
        if reader_name is not None:
            assert reader_name not in line, f"GAP line names the reader module: {line}"
