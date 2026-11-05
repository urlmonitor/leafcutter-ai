"""INF-700b-2-i -- the reference gate still refuses from a consumer install.

The gate is the ``check-agent-registry`` hook.  Every test reads the hook directory and the
hook's entry string out of the ``shared_reference_layout`` (a real build) and copies them
into a PRIVATE tmp git consumer project (package copy under ``leafcutter-ai/``, a fresh
``.build_manifest.json``).  Nothing is written into the shared layout and no test spawns
``build.py``.  The layout's own manifest is never used (its ``package_root`` escapes it).
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_ID = "check-agent-registry"
PKG = "leafcutter-ai"
PKG_SKILL = "templates/skills/signoff/SKILL.md"
DANGLING = "no-such-skill"
DANGLING_SENTENCE = f"Load the `{DANGLING}` skill before you continue."
VALID_SENTENCE = "Load the `signoff` skill before you continue."
HARMLESS_SENTENCE = "This paragraph names no skill."
_TIMEOUT = 180
_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
_ENV["PYTHONDONTWRITEBYTECODE"] = "1"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=_TIMEOUT,
                          env=_ENV, check=False)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=str(repo),
                   check=True, capture_output=True, env=_ENV)


def _copy(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def _layout_hook_dir(layout: Path) -> Path:
    hook_dir = layout / ".leafcutter" / "scripts" / "commit_guardian"
    assert hook_dir.is_dir(), f"built layout has no deployed hook directory: {hook_dir}"
    return hook_dir


def _layout_entry(layout: Path) -> str:
    config = layout / ".leafcutter" / "pre-commit-config.yaml"
    assert config.is_file(), f"built layout has no pre-commit config: {config}"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    stanzas = [h for r in data["repos"] for h in r["hooks"] if h.get("id") == HOOK_ID]
    assert len(stanzas) == 1, f"expected one {HOOK_ID} stanza in the built layout: {stanzas}"
    return stanzas[0]["entry"]


def _copy_package(parent: Path) -> None:
    for name in ("scripts", "config", "templates"):
        _copy(REPO_ROOT / name, parent / PKG / name)


def _write_manifest(parent: Path) -> None:
    (parent / ".build_manifest.json").write_text(f'{{"package_root": "{PKG}"}}', encoding="utf-8")


def _commit_baseline(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")


def _consumer(tmp: Path, layout: Path, *, leafcutter_link: Path | None = None) -> Path:
    """Private consumer project: package copy, fresh manifest, deployed hook from the build."""
    repo = tmp / "project"
    repo.mkdir()
    _copy_package(repo)
    _write_manifest(repo)
    if leafcutter_link is None:
        _copy(_layout_hook_dir(layout), repo / ".leafcutter" / "scripts" / "commit_guardian")
    else:
        (repo / ".leafcutter").symlink_to(leafcutter_link, target_is_directory=True)
    _commit_baseline(repo)
    return repo


def _stage_append(repo: Path, rel: str, sentence: str) -> None:
    path = repo / rel
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + sentence + "\n",
                    encoding="utf-8")
    _git(repo, "add", rel)


def _reset(repo: Path) -> None:
    _git(repo, "reset", "-q", "--hard")
    _git(repo, "clean", "-fdq")


def _hook(repo: Path, entry: str) -> tuple[int, str]:
    argv = shlex.split(entry)
    assert argv[0] == "python", entry
    argv[0] = sys.executable
    cp = _run(argv, repo)
    return cp.returncode, cp.stdout + "\n" + cp.stderr


def _names_template_and_skill(out: str) -> bool:
    return any(PKG_SKILL in ln and DANGLING in ln for ln in out.splitlines())


def _has_banner(out: str) -> bool:
    return any(ln.startswith(f"[{HOOK_ID}]") and re.search(r"skill[- ]reference", ln, re.I)
               for ln in out.splitlines())


@pytest.mark.shared_layout_reader
def test_gate_refuses_dangling_reference_from_a_deployed_consumer_layout(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: INF-700b-2-i
    # angle: reachability
    """AC-3: the gate runs from the deployed layout and refuses the commit.

    Hook dir and entry come from the real build; the entry is run as a subprocess with cwd at
    the consumer project.  Catches a deploy-manifest omission a shipped-source copy masks."""
    entry = _layout_entry(shared_reference_layout)
    repo = _consumer(tmp_path, shared_reference_layout)
    _stage_append(repo, f"{PKG}/{PKG_SKILL}", DANGLING_SENTENCE)
    code, out = _hook(repo, entry)
    assert code != 0, f"dangling reference was not refused: {out}"
    assert _names_template_and_skill(out), f"no line names {PKG_SKILL} and {DANGLING}: {out}"
    assert _has_banner(out), f"no skill-reference banner line: {out}"


@pytest.mark.shared_layout_reader
def test_gate_exits_zero_over_a_consistent_deployed_layout(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: INF-700b-2-i
    # angle: deployed
    """AC-5/AC-6: consistent tree exits zero; the refusal is observed in the SAME project, so
    the zero is attributable to the tree and not to a hook that never ran."""
    entry = _layout_entry(shared_reference_layout)
    repo = _consumer(tmp_path, shared_reference_layout)
    for sentence in (HARMLESS_SENTENCE, VALID_SENTENCE):
        _stage_append(repo, f"{PKG}/{PKG_SKILL}", sentence)
        code, out = _hook(repo, entry)
        assert code == 0, f"consistent tree refused for {sentence!r}: {out}"
        assert "validation failed" not in out and DANGLING not in out, out
        _reset(repo)
    _stage_append(repo, f"{PKG}/{PKG_SKILL}", DANGLING_SENTENCE)
    code, out = _hook(repo, entry)
    assert code != 0 and _names_template_and_skill(out), f"paired refusal missing: {out}"


def _break_skills_dir(repo: Path) -> str:
    shutil.rmtree(repo / PKG / "templates" / "skills")
    other = sorted((repo / PKG / "templates" / "agents").glob("*.md"))[0]
    _stage_append(repo, str(other.relative_to(repo)), HARMLESS_SENTENCE)
    return r"cannot read ability directory"


def _break_validator(repo: Path) -> str:
    (repo / PKG / "scripts" / "registry_validator.py").unlink()
    _stage_append(repo, f"{PKG}/{PKG_SKILL}", DANGLING_SENTENCE)
    return r"registry_validator"


def _break_manifest(repo: Path) -> str:
    (repo / ".build_manifest.json").unlink()
    _stage_append(repo, f"{PKG}/{PKG_SKILL}", DANGLING_SENTENCE)
    return r"CANNOT LOCATE PACKAGE"


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("breaker", [_break_skills_dir, _break_validator, _break_manifest],
                         ids=["no_skills_dir", "no_validator", "no_manifest"])
def test_gate_fails_rather_than_passes_when_no_skills_directory_resolves(
    shared_reference_layout: Path, tmp_path: Path, breaker
) -> None:
    # covers: INF-700b-2-i
    # angle: failure
    """AC-4: a missing directory, module or configuration file must not yield exit zero."""
    entry = _layout_entry(shared_reference_layout)
    repo = _consumer(tmp_path, shared_reference_layout)
    expected = breaker(repo)
    code, out = _hook(repo, entry)
    assert code != 0, f"gate passed with the dependency absent ({breaker.__name__}): {out!r}"
    assert out.strip(), "non-zero exit with empty output"
    assert re.search(expected, out), f"output does not name the cause {expected!r}: {out}"


@pytest.mark.shared_layout_reader
def test_gate_scans_the_consumer_root_not_the_package_checkout(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: INF-700b-2-i
    # angle: seam
    """AC-1/AC-6: reached through a symlinked .leafcutter whose target sits OUTSIDE the repo
    beside a CLEAN package, the gate scans the consumer's own (dangling) package copy.
    A __file__-relative resolver would scan the clean package and exit zero."""
    entry = _layout_entry(shared_reference_layout)
    outside = tmp_path / "outside"
    outside.mkdir()
    _copy(_layout_hook_dir(shared_reference_layout),
          outside / ".leafcutter" / "scripts" / "commit_guardian")
    _copy_package(outside)
    _write_manifest(outside)
    repo = _consumer(tmp_path, shared_reference_layout, leafcutter_link=outside / ".leafcutter")
    assert (repo / ".leafcutter").is_symlink()
    _stage_append(repo, f"{PKG}/{PKG_SKILL}", DANGLING_SENTENCE)
    code, out = _hook(repo, entry)
    assert code != 0, f"consumer's dangling package copy was not scanned: {out}"
    assert _names_template_and_skill(out), f"consumer violation not reported: {out}"
    _reset(repo)
    _stage_append(repo, f"{PKG}/{PKG_SKILL}", HARMLESS_SENTENCE)
    code, out = _hook(repo, entry)
    assert code == 0, f"control (consumer package clean) refused: {out}"


@pytest.mark.shared_layout_reader
def test_checker_is_present_in_the_deployed_tree_after_build(shared_reference_layout: Path) -> None:
    # covers: INF-700b-2-i
    # angle: deployed
    """AC-3: run_hook.py and check_agent_registry.py, at the paths the built entry names,
    exist in the built tree, with _resolve_root.py beside them."""
    argv = shlex.split(_layout_entry(shared_reference_layout))
    named = [Path(a) for a in argv[1:] if a.endswith(".py")]
    assert {p.name for p in named} == {"run_hook.py", "check_agent_registry.py"}, argv
    for rel in named:
        assert (shared_reference_layout / rel).is_file(), f"entry names {rel}, absent from the build"
    beside = (shared_reference_layout / named[0]).parent / "_resolve_root.py"
    assert beside.is_file(), f"_resolve_root.py not deployed beside the hook: {beside}"
