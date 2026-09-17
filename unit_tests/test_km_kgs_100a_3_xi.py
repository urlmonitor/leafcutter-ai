"""
MODULE: test_km_kgs_100a_3_xi
GOAL: TDD stubs for KM-KGS-100a-3-xi -- the knowledge-map frontmatter reader
      (the ten functions that locate the frontmatter end, strip matched
      quotes, split flow sequences, parse scalars, measure indentation,
      strip inline comments, recognise mapping items, parse block children,
      parse .md frontmatter and parse .yaml files) moves out of
      scripts/knowledge_query.py into its own module, with reading,
      reachability, deployment and size unchanged or improved.
SPLIT NOTE (GE-127a-1): this module covers reader-module discovery,
    reachability, size, and the deploy-manifest test (needs no synthetic
    package). The whole-repo .md differential, deploy-byte-identical,
    deployed-record and drift-gap tests -- which DO need a synthetic
    package -- live in the sibling module test_km_kgs_100a_3_xi_deploy.py.
    Both files together implement all 15 test_spec entries for
    KM-KGS-100a-3-xi; the split is purely by concern to stay under the .py
    content-line limit, never a change to any test's name, body, or tags.
BUSINESS CONTEXT: see docs/acceptance-criteria/knowledge-management/
    KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100a-3-xi.yaml. Behaviour
    -preserving structural change only -- no reader rule from
    KM-KGS-100a-3-i..-x changes. The reader module does not exist yet, so
    every test that needs it is discovered from the ten functions'
    __module__ attribute (never a hard-coded file name); while extraction
    has not happened, that discovery step itself fails with a clear message
    naming the state ("reader functions are still defined in
    knowledge_query.py"), which is the intended RED reason for every test
    that depends on it. No test in this module ever calls pytest.skip.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

import knowledge_query as kq  # noqa: E402
from _file_size_ratchet import count_content_lines  # noqa: E402
from check_file_size import get_limit_for_extension  # noqa: E402
import build as build_module  # noqa: E402
from build_phases_knowledge import _manifest_workflow_tool_scripts  # noqa: E402

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

    Never a hard-coded file name. Raises a clear AssertionError (not an
    obscure crash) when the functions are still defined inside
    knowledge_query itself -- the pre-extraction state -- or when they are
    split across more than one module, or when the discovered module cannot
    be found as a real .py file next to knowledge_query.py.
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


def _git_show_origin_main(rel_path):
    """Read a blob from origin/main. Fails the test, never skips, when the
    revision or blob cannot be resolved."""
    result = subprocess.run(
        ["git", "show", f"origin/main:{rel_path}"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, (
        f"could not resolve origin/main:{rel_path} -- git error: {result.stderr.strip()}"
    )
    return result.stdout


# ---------------------------------------------------------------------------
# Defining-module discovery + reachability (test_spec entries 4-6)
# ---------------------------------------------------------------------------


def test_reader_functions_are_defined_outside_knowledge_query():
    # covers: KM-KGS-100a-3-xi
    # angle: criterion
    """All ten reader functions share ONE module, whose __module__ is not
    'knowledge_query' and whose __file__ is a .py file next to
    knowledge_query.py. RED before the extraction (all ten report
    __module__ 'knowledge_query')."""
    reader_module = _discover_reader_module(kq)
    for name in _READER_FUNCTION_NAMES:
        assert getattr(kq, name).__module__ == reader_module.__name__


def test_reader_names_are_the_reader_module_objects_on_normal_import():
    # covers: KM-KGS-100a-3-xi
    # angle: reachability
    """With scripts/ on sys.path and knowledge_query imported normally, each
    of the ten names is the SAME object (identity) as the reader module's
    own attribute of that name."""
    reader_module = _discover_reader_module(kq)
    for name in _READER_FUNCTION_NAMES:
        assert getattr(kq, name, None) is getattr(reader_module, name, None), (
            f"knowledge_query.{name} is not identical to {reader_module.__name__}.{name}"
        )


_REACHABILITY_CHILD_TEMPLATE = '''
import importlib.util
import json
import sys
from pathlib import Path

KQ_PATH = Path(r"__KQ_PATH__")
NAMES = __NAMES_JSON__

sys.path[:] = [p for p in sys.path if Path(p).name != "scripts"]

spec = importlib.util.spec_from_file_location("knowledge_query", KQ_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["knowledge_query"] = mod
spec.loader.exec_module(mod)

errors = []
resolved = {}
for name in NAMES:
    func = getattr(mod, name, None)
    if func is None:
        errors.append(name + ": missing attribute on knowledge_query")
        continue
    if not callable(func):
        errors.append(name + ": attribute is not callable")
        continue
    mod_name = getattr(func, "__module__", None)
    if mod_name == "knowledge_query":
        errors.append(name + ": still defined in knowledge_query (extraction not done)")
        continue
    owner = sys.modules.get(mod_name)
    if owner is None:
        errors.append(name + ": owning module " + repr(mod_name) + " not in sys.modules")
        continue
    if getattr(owner, name, None) is not func:
        errors.append(name + ": not identical to " + str(mod_name) + "." + name)
        continue
    resolved[name] = mod_name

if errors:
    sys.stderr.write("FAIL: " + "; ".join(errors))
    sys.exit(1)
sys.stdout.write(json.dumps(resolved))
sys.exit(0)
'''


def test_reader_names_reachable_when_loaded_from_file_path_without_scripts_on_path(tmp_path):
    # covers: KM-KGS-100a-3-xi
    # angle: reachability
    """A subprocess with every scripts/ entry scrubbed from sys.path loads
    scripts/knowledge_query.py via spec_from_file_location exactly as
    scripts/visualise_knowledge_graph.py does, and every one of the ten
    names must be reachable, callable, and identical to the attribute named
    by its own __module__ in sys.modules."""
    kq_path = _SCRIPTS_DIR / "knowledge_query.py"
    script = (
        _REACHABILITY_CHILD_TEMPLATE.replace("__KQ_PATH__", str(kq_path)).replace(
            "__NAMES_JSON__", json.dumps(list(_READER_FUNCTION_NAMES))
        )
    )
    script_path = tmp_path / "child_reachability.py"
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
        "spec_from_file_location reachability check failed with no scripts/ "
        f"directory on sys.path. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Size (test_spec entries 7-9)
# ---------------------------------------------------------------------------


def test_reader_module_code_length_within_py_limit():
    # covers: KM-KGS-100a-3-xi
    # angle: criterion
    """The discovered reader module's code length, measured with
    count_content_lines, is at or below get_limit_for_extension's limit."""
    reader_module = _discover_reader_module(kq)
    reader_path = Path(reader_module.__file__)
    source = reader_path.read_text(encoding="utf-8")
    length = count_content_lines(source)
    limit = get_limit_for_extension(str(reader_path))
    assert length <= limit, f"{reader_path} is {length} content lines, over its {limit}-line limit"


def test_knowledge_query_code_length_not_greater_than_main():
    # covers: KM-KGS-100a-3-xi
    # angle: criterion
    """count_content_lines of the working-tree knowledge_query.py must not
    exceed count_content_lines of the origin/main blob (1013 on
    2026-09-17). RED before the extraction (1104 > 1013)."""
    main_text = _git_show_origin_main("scripts/knowledge_query.py")
    main_length = count_content_lines(main_text)
    working_text = (_SCRIPTS_DIR / "knowledge_query.py").read_text(encoding="utf-8")
    working_length = count_content_lines(working_text)
    assert working_length <= main_length, (
        f"scripts/knowledge_query.py is {working_length} content lines, "
        f"main is {main_length} -- the size ratchet will refuse this change"
    )


_WIRING_FILES = (
    "scripts/build.py",
    "scripts/build_phases_knowledge.py",
    "scripts/build_phases_workflows.py",
    "scripts/build_helpers.py",
)


def test_over_limit_build_wiring_files_do_not_grow_vs_main():
    # covers: KM-KGS-100a-3-xi
    # angle: boundary
    """For each deploy/manifest/drift wiring file already over its limit on
    main, the working-tree length must not exceed main's. All violations are
    listed together; an unresolvable origin/main blob fails, never skips."""
    violations = []
    for rel in _WIRING_FILES:
        main_text = _git_show_origin_main(rel)
        main_length = count_content_lines(main_text)
        limit = get_limit_for_extension(rel)
        if main_length <= limit:
            continue
        working_text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        working_length = count_content_lines(working_text)
        if working_length > main_length:
            violations.append((rel, working_length, main_length))
    assert not violations, "file(s) already over their limit on main grew further: " + ", ".join(
        f"{rel}: {now} > {then}" for rel, now, then in violations
    )


# ---------------------------------------------------------------------------
# Deploy manifest coverage (test_spec entry 10 -- lives here, not in
# test_km_kgs_100a_3_xi_deploy.py, since it needs no synthetic package)
# ---------------------------------------------------------------------------


def test_deploy_manifests_list_reader_module_alongside_knowledge_query():
    # covers: KM-KGS-100a-3-xi
    # angle: seam
    """_manifest_workflow_tool_scripts and _guard_source_paths_workflow_tools
    each return a set containing both scripts/knowledge_query.py and
    scripts/<reader module file name>."""
    reader_module = _discover_reader_module(kq)
    reader_name = Path(reader_module.__file__).name

    manifest_set = _manifest_workflow_tool_scripts(_REPO_ROOT)
    guard_set = build_module._guard_source_paths_workflow_tools(_REPO_ROOT)

    for label, entries in (("manifest", manifest_set), ("guard", guard_set)):
        assert "scripts/knowledge_query.py" in entries, (
            f"{label} set is missing 'scripts/knowledge_query.py': {sorted(entries)}"
        )
        assert f"scripts/{reader_name}" in entries, (
            f"{label} set is missing 'scripts/{reader_name}': {sorted(entries)}"
        )


# ---------------------------------------------------------------------------
# Stdlib-only coverage (test_spec entries 14-15)
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS = (
    "import requests",
    "import numpy",
    "import pandas",
    "import yaml",
    "import toml",
    "import pydantic",
    "import sqlalchemy",
    "import psycopg2",
    "import aiohttp",
)


def _stdlib_only_scan(paths):
    """Shared stdlib-only forbidden-import scan applied over a list of
    source paths -- the same forbidden-import list TestStdlibOnly uses."""
    violations = {}
    for path in paths:
        source = Path(path).read_text(encoding="utf-8")
        found = [imp for imp in _FORBIDDEN_IMPORTS if imp in source]
        if found:
            violations[str(path)] = found
    return violations


def test_stdlib_scan_rejects_forbidden_import_in_reader_module(tmp_path):
    # covers: KM-KGS-100a-3-xi
    # angle: failure
    """Disagreement is forced synthetically: a temp copy of the reader
    module with 'import yaml' appended reports a violation naming that file
    and the import; an unmodified temp copy reports none."""
    reader_module = _discover_reader_module(kq)
    reader_path = Path(reader_module.__file__)
    original_source = reader_path.read_text(encoding="utf-8")

    clean_copy = tmp_path / "reader_clean.py"
    clean_copy.write_text(original_source, encoding="utf-8")
    tainted_copy = tmp_path / "reader_tainted.py"
    tainted_copy.write_text(original_source + "\nimport yaml\n", encoding="utf-8")

    clean_violations = _stdlib_only_scan([clean_copy])
    tainted_violations = _stdlib_only_scan([tainted_copy])

    assert clean_violations == {}, f"unmodified copy reported a violation: {clean_violations}"
    assert str(tainted_copy) in tainted_violations, (
        f"tainted copy did not report a violation: {tainted_violations}"
    )
    assert "import yaml" in tainted_violations[str(tainted_copy)]


def test_stdlib_only_gate_covers_real_reader_module():
    # covers: KM-KGS-100a-3-xi
    # angle: criterion
    """The stdlib-only gate reads the source of BOTH knowledge_query.py and
    the discovered reader module, and both real files pass the scan. RED
    before the extraction because no separate reader module exists to be
    scanned."""
    kq_path = _SCRIPTS_DIR / "knowledge_query.py"
    reader_module = _discover_reader_module(kq)
    reader_path = Path(reader_module.__file__)

    scanned_paths = {kq_path, reader_path}
    assert kq_path in scanned_paths
    assert reader_path in scanned_paths

    violations = _stdlib_only_scan(scanned_paths)
    assert violations == {}, f"stdlib-only gate found violation(s): {violations}"
