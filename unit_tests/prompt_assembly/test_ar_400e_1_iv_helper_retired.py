"""AR-400e-1-iv -- the one-time abilities migration helper is retired and nothing depends on
the retired list (TDD red phase).

Decision 7 (BrainCandy, 2026-10-12): ``scripts/migrate_agent_abilities.py`` is DELETED; the
AR-300c tests that shelled out to it are retargeted at the commit-time transform hook.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NAME = "migrate_agent_abilities"
RETARGETED = (
    "test_ar_300c_1_frontmatter_declaration", "test_ar_300c_2_consolidation",
    "test_ar_300c_2_i_single_field_agents", "test_ar_300c_3_derived_copy_comparison",
    "test_ar_300c_3_i_unresolvable_ability", "test_ar_300c_3_ii_registry_transform",
)
_THIS = Path(__file__).resolve()


@pytest.mark.shared_layout_reader
def test_migration_helper_is_absent_from_package_and_deployed_layout(shared_reference_layout):
    # covers: AR-400e-1-iv
    # angle: deployed
    """scripts/migrate_agent_abilities.py does not exist in the checked-out package, and the
    shared reference build (a real build.py deploy of this package) contains no copy of it
    anywhere. Control: the same layout does contain a known deployed script, so the search looked
    in a populated deploy and 'not found' is not an empty-layout artefact. (The helper is a
    build-engine script and is not deployed today, so only the source half is red now; the
    deployed half guards a future deploy-manifest entry.)"""
    layout = Path(shared_reference_layout)
    deployed_known = list((layout / ".leafcutter" / "scripts").glob("knowledge_query.py"))
    assert deployed_known, f"control: no deployed .leafcutter/scripts/knowledge_query.py under {layout}"
    leaked = sorted(str(p) for p in layout.rglob(f"{NAME}.py"))
    source = REPO_ROOT / "scripts" / f"{NAME}.py"
    assert not source.exists() and not leaked, f"source exists={source.exists()}, deployed copies={leaked}"


def _history_free_mentions(path: Path) -> list[int]:
    """1-based lines that name the helper outside a DECISION HISTORY block."""
    hits, in_hist, comment_hist = [], False, False
    for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        stripped = line.strip()
        if "DECISION HISTORY" in line:
            in_hist, comment_hist = True, stripped.startswith("#")
            continue
        if in_hist and comment_hist and stripped and not stripped.startswith("#"):
            in_hist = False
        elif in_hist and not comment_hist and stripped == '"""':
            in_hist = False
            continue
        if not in_hist and NAME in line:
            hits.append(n)
    return hits


def _imports_helper(path: Path) -> bool:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # other files' invalid escapes are not this test's concern
            tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(NAME in a.name for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and NAME in (node.module or ""):
            return True
    return False


def test_nothing_imports_or_invokes_the_migration_helper(tmp_path):
    # covers: AR-400e-1-iv
    # angle: criterion
    """No .py/.js/.json/.md under scripts/, templates/, unit_tests/ or .github/ imports the
    helper or names it (command, path, docstring) outside a DECISION HISTORY block. The helper's
    own file and this retirement test are the only exemptions (AC records are not scanned).
    Control: the scan reads a populated tree and the pattern does fire on a planted line."""
    scanned, offenders = 0, []
    for top in ("scripts", "templates", "unit_tests", ".github"):
        base = REPO_ROOT / top
        for path in sorted(base.rglob("*")) if base.is_dir() else []:
            if path.suffix not in {".py", ".js", ".json", ".md"} or not path.is_file():
                continue
            if "__pycache__" in path.parts or "node_modules" in path.parts or path in (_THIS,):
                continue
            if path == REPO_ROOT / "scripts" / f"{NAME}.py":
                continue
            scanned += 1
            hits = _history_free_mentions(path)
            if hits or (path.suffix == ".py" and _imports_helper(path)):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{hits[:3]}")
    assert scanned > 500, f"control: scan examined only {scanned} files"
    planted = tmp_path / "planted.py"
    planted.write_text(f"x = '{NAME}'\n", encoding="utf-8")
    assert _history_free_mentions(planted) == [1], "control: the pattern must fire"
    planted.write_text(f'"""\nDECISION HISTORY\n- moved from {NAME}.py\n"""\n', encoding="utf-8")
    assert _history_free_mentions(planted) == [], "control: a history entry is exempt"
    assert not offenders, f"{len(offenders)} file(s) still name the retired helper:\n" + "\n".join(offenders)


def _slice_without_helper(dest: Path) -> Path:
    """A real copy of what the AR-300c modules read, with the helper script ABSENT."""
    skip = shutil.ignore_patterns("__pycache__", f"{NAME}.py")
    for name in ("scripts", "templates", "config"):
        shutil.copytree(REPO_ROOT / name, dest / name, ignore=skip)
    shutil.copytree(REPO_ROOT / "unit_tests" / "prompt_assembly", dest / "unit_tests" / "prompt_assembly", ignore=skip)
    shutil.copytree(REPO_ROOT / "unit_tests" / "agents", dest / "unit_tests" / "agents", ignore=skip)
    for init in ("__init__.py",):
        if (REPO_ROOT / "unit_tests" / init).exists():
            shutil.copy2(REPO_ROOT / "unit_tests" / init, dest / "unit_tests" / init)
    assert not (dest / "scripts" / f"{NAME}.py").exists()
    return dest


def _run_pytest(pkg: Path, args: list[str], junit: Path) -> subprocess.CompletedProcess:
    ini = pkg / "isolated.ini"
    ini.write_text("[pytest]\n", encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-c", str(ini), "--rootdir", str(pkg), "-p", "no:cacheprovider",
         "-q", f"--junitxml={junit}", *args],
        cwd=pkg, capture_output=True, text=True, timeout=900, check=False)


def _outcomes(junit: Path) -> dict[str, dict[str, int]]:
    per: dict[str, dict[str, int]] = {}
    for case in ET.parse(junit).getroot().iter("testcase"):
        classname = case.get("classname", "")
        mod = next((m for m in RETARGETED if m in classname), classname)
        status = "failed" if case.find("failure") is not None or case.find("error") is not None else (
            "skipped" if case.find("skipped") is not None else "passed")
        per.setdefault(mod, {"passed": 0, "failed": 0, "skipped": 0})[status] += 1
    return per


def test_retargeted_ar300_tests_pass_without_the_helper(tmp_path):
    # covers: AR-400e-1-iv
    # angle: discrimination
    """The six AR-300c modules run in a subprocess over a copy with the helper ABSENT: each
    collects, has at least one PASSED test, and none is skipped, xfailed or failed. Wrong version
    caught: a retargeted test still shells out to the deleted script (it fails here, which is the
    point -- 'skipped instead of failing' is also refused). Control (same harness, a planted call to
    the deleted helper in one module) must FAIL, proving the harness sees a missing helper."""
    pkg = _slice_without_helper(tmp_path / "pkg")
    files = [f"unit_tests/prompt_assembly/{m}.py" for m in RETARGETED]
    assert all((pkg / f).is_file() for f in files)
    run = _run_pytest(pkg, files, tmp_path / "retargeted.xml")
    per = _outcomes(tmp_path / "retargeted.xml")
    bad = {m: per.get(m, {}) for m in RETARGETED
           if per.get(m, {}).get("passed", 0) < 1 or per[m]["failed"] or per[m]["skipped"]}

    victim = pkg / "unit_tests" / "prompt_assembly" / f"{RETARGETED[0]}.py"
    victim.write_text(victim.read_text(encoding="utf-8") + (
        "\n\ndef test_zz_restored_helper_call():\n"
        "    import subprocess, sys\n"
        "    from pathlib import Path\n"
        "    root = Path(__file__).resolve().parents[2]\n"
        f"    cp = subprocess.run([sys.executable, str(root / 'scripts' / '{NAME}.py'), '--package-root', str(root)],\n"
        "                        capture_output=True, text=True, check=False)\n"
        "    assert cp.returncode == 0, 'helper is gone'\n"), encoding="utf-8")
    control = _run_pytest(pkg, [f"{victim}::test_zz_restored_helper_call"], tmp_path / "control.xml")
    assert control.returncode != 0 and _outcomes(tmp_path / "control.xml").get(RETARGETED[0], {}).get("failed") == 1, \
        f"control: a restored call to the deleted helper must fail, got rc={control.returncode}"
    assert run.returncode == 0 and not bad, (
        f"retargeted modules did not pass without the helper (rc={run.returncode}): {bad}\n{run.stdout[-1500:]}")
    assert re.search(r"\d+ passed", run.stdout), run.stdout[-500:]
