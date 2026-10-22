"""
MODULE: unit_tests/build_orchestration/test_tq500f3v_project_interpreter.py
GOAL: TQ-500f-3-v -- the red-baseline gate judges new tests with the adopter
    project's own interpreter, and refuses loudly (never "no red outcome")
    when that interpreter cannot import the project's own package.

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-v.yaml

BUSINESS CONTEXT: reproduces the DIAGraph adopter defect. The build routes run
    the gate as bare ``python fast_lane.py ...``; in an adopter whose
    dependencies live in a project venv, that interpreter has pytest but not
    the project package, so conftest import fails (pytest exit 4), every new
    test reads ERROR and the gate reports ``no_red_outcome_among_new_tests``
    even though the tests are genuinely red under the project venv.

ARCHITECTURE: real git fixtures (``_tq500f3i_fixtures``), a real venv built
    with ``--system-site-packages`` (so it has the same pytest/yaml as the
    interpreter running this suite), and the project package installed into
    that venv ONLY, through a ``.pth`` file in the venv's own site-packages.
    The gate is always launched by ``sys.executable`` -- the stand-in for the
    bare ``python`` on PATH -- exactly as build-feature.js launches it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import unit_tests.build_orchestration._tq500f3i_fixtures as fx

_PACKAGE = "adopterpkg"
_TEST_NAME = "test_adopter_answer_is_42"

_BASE_FILES = {
    ".gitignore": ".venv/\nenvs/\n",
    f"src/{_PACKAGE}/__init__.py": "def answer():\n    return 41\n",
    "tests/conftest.py": f"import {_PACKAGE}  # noqa: F401  (the adopter conftest imports its own package)\n",
}


def _new_test_source(ac_id: str) -> str:
    return (
        f"from {_PACKAGE} import answer\n\n\n"
        f"def {_TEST_NAME}():\n"
        f"    # covers: {ac_id}\n"
        "    assert answer() == 42\n"
    )


def _make_adopter(tmp_root: Path, ac_id: str) -> tuple[Path, Path]:
    """Build the adopter worktree with one new, uncommitted covering test."""
    work_dir, _base_sha = fx.make_worktree(tmp_root, dict(_BASE_FILES))
    ac_root = work_dir / "docs" / "acceptance-criteria"
    fx.write_ac_yaml(ac_root, ac_id, [{"name": _TEST_NAME}])
    (work_dir / "tests" / "test_adopter_feature.py").write_text(_new_test_source(ac_id), encoding="utf-8")
    return work_dir, ac_root


def _make_env(work_dir: Path, rel: str) -> Path:
    """Create a venv at *work_dir/rel* that alone can import the project package."""
    env_dir = work_dir / rel
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", str(env_dir)],
        check=True, capture_output=True, text=True, timeout=120,
    )
    python = env_dir / "bin" / "python"
    purelib = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True, capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    Path(purelib).mkdir(parents=True, exist_ok=True)
    (Path(purelib) / f"{_PACKAGE}.pth").write_text(str(work_dir / "src") + "\n", encoding="utf-8")
    return python


def _gate(subcommand: str, ac_id: str, work_dir: Path, ac_root: Path) -> dict:
    """Run the real gate CLI with the bare interpreter and parse its one JSON verdict."""
    id_flag = "--source-ac" if subcommand == "heavy_lane_gate" else "--ac-ids"
    proc = subprocess.run(
        [sys.executable, str(fx.GATE_SCRIPT), subcommand, id_flag, ac_id,
         "--test-root", str(work_dir), "--ac-root", str(ac_root)],
        capture_output=True, text=True, timeout=300,
    )
    assert proc.stdout.strip().startswith("{"), (
        f"{subcommand} printed no JSON verdict; exit={proc.returncode} "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    return json.loads(proc.stdout)


def test_gate_judges_new_tests_with_the_worktree_venv():
    # covers: TQ-500f-3-v
    # angle: criterion
    """The DIAGraph shape: the project package exists only in the worktree's
    .venv. Both lanes' gate, launched by the bare interpreter, must judge the
    new test with the .venv interpreter, see it red, and pass.
    """
    ac_id = "TQ-FIX-3V-VENV"
    with tempfile.TemporaryDirectory() as tmp:
        work_dir, ac_root = _make_adopter(Path(tmp), ac_id)
        venv_python = _make_env(work_dir, ".venv")

        for subcommand in ("heavy_lane_gate", "verify_red_baseline"):
            verdict = _gate(subcommand, ac_id, work_dir, ac_root)
            assert verdict.get("gate_passed") is True, f"{subcommand}: verdict={verdict!r}"
            assert fx.find_by_name(verdict.get("red"), _TEST_NAME) is not None, (
                f"{subcommand}: the new test must be judged red under the project venv; verdict={verdict!r}"
            )
            assert verdict.get("interpreter") == str(venv_python), (
                f"{subcommand}: the verdict must name the interpreter that judged the tests; verdict={verdict!r}"
            )


def test_gate_uses_the_configured_python_command_first():
    # covers: TQ-500f-3-v
    # angle: boundary
    """A configured testing_context.python_command wins over everything else:
    the environment lives outside .venv, and the gate still finds it.
    """
    ac_id = "TQ-FIX-3V-CONFIGURED"
    with tempfile.TemporaryDirectory() as tmp:
        work_dir, ac_root = _make_adopter(Path(tmp), ac_id)
        configured_python = _make_env(work_dir, "envs/project")
        config_dir = work_dir / ".claude"
        config_dir.mkdir()
        (config_dir / "skills_config.json").write_text(
            json.dumps({"testing_context": {"python_command": "envs/project/bin/python"}}),
            encoding="utf-8",
        )

        verdict = _gate("heavy_lane_gate", ac_id, work_dir, ac_root)

        assert verdict.get("gate_passed") is True, f"verdict={verdict!r}"
        assert fx.find_by_name(verdict.get("red"), _TEST_NAME) is not None, f"verdict={verdict!r}"
        assert verdict.get("interpreter") == str(configured_python), f"verdict={verdict!r}"


def test_gate_refuses_loudly_when_the_project_package_cannot_be_imported():
    # covers: TQ-500f-3-v
    # angle: failure
    """No project environment at all: the gate can only fall back to the
    interpreter running it, which cannot import the project package. Every
    new test errors at conftest import; that must be a distinct, named
    refusal -- never "no_red_outcome_among_new_tests".
    """
    ac_id = "TQ-FIX-3V-UNIMPORTABLE"
    with tempfile.TemporaryDirectory() as tmp:
        work_dir, ac_root = _make_adopter(Path(tmp), ac_id)

        for subcommand in ("heavy_lane_gate", "verify_red_baseline"):
            verdict = _gate(subcommand, ac_id, work_dir, ac_root)
            assert verdict.get("gate_passed") is False, f"{subcommand}: verdict={verdict!r}"
            assert verdict.get("reason") != "no_red_outcome_among_new_tests", (
                f"{subcommand}: an un-importable project package must not read as 'no red'; verdict={verdict!r}"
            )
            assert verdict.get("reason") == "project_package_not_importable", f"{subcommand}: verdict={verdict!r}"
            refusal = str(verdict.get("refusal") or "")
            assert sys.executable in refusal and f"'{_PACKAGE}'" in refusal, (
                f"{subcommand}: the refusal must name the interpreter and the package; verdict={verdict!r}"
            )
            assert verdict.get("interpreter") == sys.executable, f"{subcommand}: verdict={verdict!r}"


def test_resolver_order_configured_venv_uv_then_current():
    # covers: TQ-500f-3-v
    # angle: boundary
    """Without a configured command or a .venv, a uv-managed project is run
    through ``uv run``; with none of the three, the running interpreter.
    """
    sys.path.insert(0, str(fx.REPO_ROOT / "scripts" / "ac_store"))
    import project_python

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        fx.init_repo(root)
        (root / "tests").mkdir()

        fallback = project_python.resolve_project_python(root / "tests")
        assert fallback.argv == (sys.executable,), fallback
        assert fallback.source == "current", fallback

        (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
        with mock.patch.object(project_python.shutil, "which", return_value="/opt/bin/uv"):
            via_uv = project_python.resolve_project_python(root / "tests")
        assert via_uv.argv == ("/opt/bin/uv", "run", "--project", str(root.resolve()), "python"), via_uv
        assert via_uv.source == "uv", via_uv
