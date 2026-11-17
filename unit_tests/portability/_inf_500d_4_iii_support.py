"""
MODULE: unit_tests/portability/_inf_500d_4_iii_support.py
GOAL: Shared support for the INF-500d-4-iii proofs that run the DEPLOYED workspace maker (ticket 17):
    a private copy of the deployed maker whose install holds a chosen ``config/knowledge_sink.json``,
    a fixture project whose stub build records its argv (and can reject the log-root flags once, like
    an older build), and a copy of the deployed consumer scripts into a maker-made workspace.
BUSINESS CONTEXT: The retired bootstrap read the project's recorded log root and handed it to the
    workspace's build. The maker now owns that step, reading the declaration of the install that
    deployed it (``<install>/config/knowledge_sink.json``, never a path derived from a repository).
    The proofs need to vary that declaration per case, so each case gets its own install copy; the
    shared deployed layout (built once by ``_workspace_maker_fixtures``) is only ever copied from.
ARCHITECTURE: Stdlib-only apart from the package's own declaration writer (``build_phases_knowledge``,
    the real producer of the declaration, used for the "good" input). The fixture project's build is a
    small derivation of ``_workspace_maker_build_helpers.stub_build_py_source`` -- never the package's
    own ``scripts/build.py``. NOT a test file (leading underscore).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
    ensure_deployed_layout,
    deployed_maker_path,
    make_project,
    run_maker,
)
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env
from unit_tests.build_orchestration import _workspace_maker_build_helpers as _bh

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "scripts"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from build_log_root import CONFIG_KEY  # noqa: E402
from build_phases_knowledge import build_knowledge_sink_declaration  # noqa: E402

LOG_FLAGS = ("--log-root", "--no-log-root")
_PRELUDE = '''    import json as _json
    _log = os.environ.get("BUILD_STUB_LOG")
    _prior = 0
    if _log:
        _lp = Path(_log)
        _prior = len(_lp.read_text(encoding="utf-8").splitlines()) if _lp.is_file() else 0
        with open(_lp, "a", encoding="utf-8") as _fh:
            _fh.write(_json.dumps(sys.argv[1:]) + "\\n")
    if __REJECT__ and _prior == 0 and any(a in ("--log-root", "--no-log-root") for a in sys.argv[1:]):
        sys.stderr.write("build.py: error: unrecognized arguments: " + " ".join(sys.argv[1:]) + "\\n")
        return 2
'''
_DECLARATION = '''    _cfg = target / ".leafcutter" / "config"
    _cfg.mkdir(parents=True, exist_ok=True)
    if args.no_log_root:
        _decl = {}
    else:
        _root = Path(args.log_root) if args.log_root else target / "debugging" / "logs"
        _decl = {"operational_log_root": str(_root), "feedback_sink": str(_root / "feedback.jsonl"),
                 "knowledge_emission_sink": str(_root / "knowledge_emissions.jsonl"),
                 "operational_telemetry_stream": str(_root / "agent_telemetry.jsonl")}
    (_cfg / "knowledge_sink.json").write_text(_json.dumps(_decl, indent=2) + "\\n", encoding="utf-8")
    print("stub build complete")
'''


def stub_build_source(*, rejects_log_flags_once: bool) -> str:
    """The fixture project's build: the shared stub plus argv recording and the declaration it would write.

    Every call appends its argv (JSON) to the file named by ``BUILD_STUB_LOG``. With
    *rejects_log_flags_once* the FIRST call that carries ``--log-root`` / ``--no-log-root`` exits 2
    with ``unrecognized arguments`` (a build older than the flags); any later call succeeds. A
    successful call records ``{}`` for ``--no-log-root``, the four-key declaration under the given
    root for ``--log-root``, and the build's own default root otherwise.
    """
    src = _bh.stub_build_py_source("reject")
    steps = (
        ("    parser = argparse.ArgumentParser()\n",
         _PRELUDE.replace("__REJECT__", repr(rejects_log_flags_once)) + "    parser = argparse.ArgumentParser()\n"),
        ("    args = parser.parse_args()\n",
         '    parser.add_argument("--log-root", default=None)\n'
         '    parser.add_argument("--no-log-root", action="store_true")\n    args = parser.parse_args()\n'),
        ('    print("stub build complete")\n', _DECLARATION),
    )
    for old, new in steps:
        assert old in src, f"the shared stub build no longer contains {old!r}"
        src = src.replace(old, new, 1)
    return src


def write_real_declaration(install: Path, root: Path) -> None:
    """Record *root* in ``<install>/config/knowledge_sink.json`` with the package's own writer."""
    build_knowledge_sink_declaration(install, {CONFIG_KEY: str(root)}, False, True)


def write_declaration(install: Path, text: str) -> Path:
    """Write *text* verbatim as the install's declaration (for legacy/relative/keyless shapes)."""
    path = install / "config" / "knowledge_sink.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def project_install(base: Path) -> tuple[Path, Path]:
    """A private copy of the deployed maker inside its own install; returns ``(install, maker)``.

    ``install`` is the directory whose ``scripts/`` holds the maker (so ``<install>/config`` is where
    the maker reads the project's declaration). The sibling modules are materialised from the shared
    deployed layout by the locator itself.
    """
    install = Path(base).resolve() / "install"
    (install / "scripts").mkdir(parents=True)
    copy = install / "scripts" / deployed_maker_path().name
    shutil.copy2(deployed_maker_path(), copy)
    return install, deployed_maker_path(override=copy)


def ensure_workspace(base: Path, slug: str, maker: Path, *, rejects_log_flags_once: bool = False) -> dict[str, Any]:
    """Run ``ensure`` of *maker* from a fresh fixture project; return the run plus what the stub build saw.

    Keys: the ``run_maker`` result (``answer``, ``exit_code``, ``stdout``, ``stderr``) plus ``calls``
    (the build's argv list per call), ``project`` and ``workspace`` (Path or None).
    """
    fx = make_project(Path(base) / "proj", stub_build=stub_build_source(rejects_log_flags_once=rejects_log_flags_once))
    calls_file = Path(base) / "build_calls.jsonl"
    env = {**_isolated_git_env(), "BUILD_STUB_LOG": str(calls_file)}
    res = run_maker(["ensure", "--kind", "feature", "--slug", slug], cwd=fx["project"], maker_path=maker, env=env, timeout=240)
    where = res["answer"].get("workspace_path")
    calls = [json.loads(x) for x in calls_file.read_text(encoding="utf-8").splitlines() if x.strip()] if calls_file.is_file() else []
    return {**res, "calls": calls, "project": fx["project"], "workspace": Path(where) if where else None}


def declaration_of(workspace: Path) -> dict[str, Any]:
    """The workspace's recorded ``config/knowledge_sink.json`` (fails the test when absent)."""
    path = Path(workspace) / ".leafcutter" / "config" / "knowledge_sink.json"
    assert path.is_file(), f"the workspace build recorded no declaration at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def copy_deployed_consumers(workspace: Path) -> Path:
    """Copy the REAL deployed consumers of the declaration into the workspace's ``.leafcutter``; return it.

    Verbatim files from the shared deployed layout: the location query (``scripts/knowledge``), the
    feedback writer (``scripts/feedback``) and the guard-root resolver, so a workspace the maker made
    can be asked the questions a real install answers. Nothing is generated.
    """
    deployed = ensure_deployed_layout() / ".leafcutter"
    out = Path(workspace) / ".leafcutter"
    for rel in (("scripts", "knowledge"), ("scripts", "feedback")):
        shutil.copytree(deployed.joinpath(*rel), out.joinpath(*rel), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    guard = out / "scripts" / "commit_guardian"
    guard.mkdir(parents=True, exist_ok=True)
    shutil.copy2(deployed / "scripts" / "commit_guardian" / "_resolve_root.py", guard / "_resolve_root.py")
    return out
