"""
MODULE: unit_tests/commit_guardian/_ge_132a_1_harness.py
COVERS: shared harness for the GE-132a-1 test files (test_ge_132a_1_*.py) -- a
    check registered without a remedy declaration is refused, the excused list
    only shrinks, a declaration for a check that is not registered is refused,
    and the shared declaration loader (owned constraint). Holds no tests.

GOAL: Behavioural proof through a REAL ``git commit``. The scratch repo is wired
    by a real ``pre-commit install`` with the ``check-hook-parity`` stanza copied
    from the ``.pre-commit-config.yaml`` build.py generated into the shared
    deployed layout (never hand-typed). The DEPLOYED guardian scripts are copied
    into the scratch repo's ``scripts/commit_guardian/`` so a module the build
    forgot to deploy shows up as a failed commit, not a green source-tree import.
    Manifests and routing tables are the REAL files re-serialised with
    ``json.dumps`` (fixture authenticity), edited in memory only where an arm
    needs the change under test.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.2): the registered
    pre-commit hook -- ``git commit`` -> pre-commit -> generated stanza ->
    deployed run_hook.py -> deployed check_hook_parity.py.

LOADER CONTRACT assumed (ticket "Delivers To"): module ``_remedy_declarations``
    beside the check exposes ``load(hook_id)`` returning a dict carrying
    ``hook_id``, ``disposition``, ``instruction``, ``agent``, ``skills`` and
    ``source`` (path of the supplying file), or a missing result (None, or a
    dict with no ``disposition``). Project root is the process cwd.

MARKERS: the layout is only READ, so layout tests are ``shared_layout_reader``;
    no private build.py is spawned.

NOT TESTED BEHAVIOURALLY: templates/commit-guardian/check_hook_parity.py (the
    legacy-dir copy) is not a runtime surface -- nothing registers or deploys it
    -- so mirroring the change into it has no observable behaviour to run.

DECISION HISTORY
- 2026-10-12 [GE-132a-1/test-writer]: Initial RED authoring (single file).
- 2026-10-12 [GE-132a-1/restructuring-specialist]: Split out of
  test_ge_132a_1.py (672 measured lines, limit 400) into this harness plus
  test_ge_132a_1_registration.py, test_ge_132a_1_excused_list.py and
  test_ge_132a_1_loader_fail_closed.py. Helpers moved verbatim.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
MANIFEST_PATH = GUARDIAN_DIR / "commit_guardian.json"
SEED_PATH = REPO_ROOT / "templates" / "scripts" / "precommit-autofix.json"
SKILL_PATH = REPO_ROOT / "templates" / "skills" / "precommit-autofix" / "SKILL.md"
PRE_GE132_REF = "bd4ecb9a"
HOOK_ID = "check-hook-parity"
SEED_REL = "templates/scripts/precommit-autofix.json"
MANIFEST_RELS = ("templates/scripts/commit_guardian/commit_guardian.json", "scripts/commit_guardian/commit_guardian.json")
SEED_RELS = (SEED_REL, "scripts/precommit-autofix.json")
LOCAL_REL = ".claude/precommit-autofix.json"
HOOK_TIMEOUT = 180
GIT_TIMEOUT = 60
ENV = {**os.environ, "COMMIT_AGENT_MODE": "1"}
DECL = {
    "disposition": "engage-specialist",
    "instruction": "Reduce the flagged function's branching.",
    "agent": "python-coder",
    "skills": ["complexity-reduction"],
}


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=check
    )


def _real_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _real_seed() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _hooks(manifest: dict) -> list[dict]:
    return manifest["hooks_manifest"]["hooks"]


def _gating_ids(manifest: dict) -> set[str]:
    """Judgment-tier hooks staged at pre-commit: the population the rule covers."""
    return {h["id"] for h in _hooks(manifest) if h.get("tier") == "judgment" and "pre-commit" in h.get("stages", [])}


def _declared_ids(*tables: dict) -> set[str]:
    """A rule is a declaration only when it carries a disposition."""
    return {r["hook_id"] for t in tables for r in t.get("rules", []) if r.get("disposition")}


def _undeclared(manifest: dict, *tables: dict) -> set[str]:
    return _gating_ids(manifest) - _declared_ids(*tables)


def _widget_hook(hook_id: str) -> dict:
    return {
        "id": hook_id, "tier": "judgment", "name": hook_id, "entry": "python x.py", "language": "system",
        "stages": ["pre-commit"], "pass_filenames": False, "script": hook_id.replace("-", "_") + ".py",
    }


def _clean_seed(manifest: dict) -> dict:
    """The real seed minus rules for unregistered checks, with check-complexity declared."""
    seed = _real_seed()
    registered = {h["id"] for h in _hooks(manifest)}
    seed["rules"] = [r for r in seed["rules"] if r["hook_id"] in registered]
    seed["blocking_hook_ids"] = [i for i in seed.get("blocking_hook_ids", []) if i in registered]
    for rule in seed["rules"]:
        if rule["hook_id"] == "check-complexity":
            rule.update(DECL)
    return seed


def _with_parity(manifest: dict, baseline: set[str]) -> dict:
    """Point hook_parity at nothing but the manifest, and seed the excused list."""
    out = copy.deepcopy(manifest)
    parity = out["hook_parity"]
    parity.update(runtime_dir="absent/runtime", legacy_template_dir="absent/legacy", deployed_output_dir="absent/deployed")
    parity["manifests"] = {"canonical": MANIFEST_RELS[0], "legacy": "absent/legacy/commit_guardian.json"}
    parity["undeclared_remedy_baseline"] = sorted(baseline)
    return out


def _deployed_guardian(layout: Path) -> Path:
    found = [layout / rel for rel in ("scripts/commit_guardian", ".leafcutter/scripts/commit_guardian") if (layout / rel).is_dir()]
    assert found, f"no deployed commit_guardian dir under {layout}"
    return found[0]


def _stanza(layout: Path) -> dict:
    config = yaml.safe_load((layout / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = {h["id"]: h for repo in config["repos"] for h in repo["hooks"]}
    assert HOOK_ID in hooks, f"generated config has no {HOOK_ID} stanza"
    return hooks[HOOK_ID]


def _dump(path: Path, data: dict | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_tables(root: Path, manifest: dict | str, seed: dict | str) -> None:
    for rel in MANIFEST_RELS:
        _dump(root / rel, manifest)
    for rel in SEED_RELS:
        _dump(root / rel, seed)


def _stage(root: Path, *rels: str) -> None:
    for rel in rels:
        _git(["add", rel], root)


def _scratch(layout: Path, root: Path, manifest: dict, seed: dict, local: dict | str | None = None) -> tuple[Path, dict]:
    """Real git repo whose history holds the tables, with the generated stanza installed."""
    stanza = dict(_stanza(layout))
    root.mkdir(parents=True)
    shutil.copytree(_deployed_guardian(layout), root / "scripts" / "commit_guardian", ignore=shutil.ignore_patterns("__pycache__"))
    tokens = []
    for token in stanza["entry"].split():
        marker = "scripts/commit_guardian/"
        tokens.append(str(root / token[token.index(marker):]) if marker in token else token)
    stanza["entry"] = " ".join(tokens)
    _write_tables(root, manifest, seed)
    if local is not None:
        _dump(root / LOCAL_REL, local)
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "ge132a1@example.com"], root)
    _git(["config", "user.name", "GE-132a-1 fixture"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-q", "--no-verify", "-m", "baseline"], root)
    (root / ".pre-commit-config.yaml").write_text(
        yaml.safe_dump({"repos": [{"repo": "local", "hooks": [stanza]}]}), encoding="utf-8"
    )
    done = subprocess.run(
        ["pre-commit", "install", "--hook-type", "pre-commit"], cwd=str(root), capture_output=True, text=True,
        timeout=GIT_TIMEOUT, check=False,
    )
    assert done.returncode == 0, f"pre-commit install: {done.stdout}{done.stderr}"
    return root, stanza


def _head(root: Path) -> str:
    return _git(["rev-parse", "HEAD"], root).stdout.strip()


def _commit(root: Path, message: str = "change the registered checks") -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "commit", "-m", message], cwd=str(root), capture_output=True, text=True,
        timeout=HOOK_TIMEOUT, check=False, env=ENV,
    )


def _passed(output: str, name: str) -> bool:
    return re.search(re.escape(name) + r"[.\s]*Passed", output) is not None


def _lines_naming(output: str, name: str) -> str:
    pattern = re.compile(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-])")
    return "\n".join(line for line in output.splitlines() if pattern.search(line))


def _refused(root: Path, before: str, commit: subprocess.CompletedProcess) -> str:
    output = commit.stdout + commit.stderr
    assert commit.returncode != 0, f"commit was accepted: {output!r}"
    assert _head(root) == before, "HEAD moved on a refused commit"
    return output


def _accepted(root: Path, before: str, commit: subprocess.CompletedProcess, stanza: dict) -> str:
    output = commit.stdout + commit.stderr
    assert _passed(output, stanza["name"]), f"check did not run and pass: {output!r}"
    assert commit.returncode == 0, f"commit was refused: {output!r}"
    assert _head(root) != before, "HEAD did not advance"
    return output


# ---------------------------------------------------------------------------
# Old-install tables and the all-declared seed (shared by several files)
# ---------------------------------------------------------------------------
_DRIVER = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import _remedy_declarations as m\n"
    "print(json.dumps({h: m.load(h) for h in sys.argv[2:]}))\n"
)


def _pre_ge132_table() -> dict:
    shown = subprocess.run(
        ["git", "show", f"{PRE_GE132_REF}:templates/scripts/precommit-autofix.json"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
    )
    assert shown.returncode == 0, f"pre-GE-132 table not retrievable from {PRE_GE132_REF}: {shown.stderr}"
    return json.loads(shown.stdout)


def _old_install_tables() -> tuple[dict, dict, dict]:
    """(local, seed, manifest): local is the REAL pre-GE-132 table (no
    dispositions); the seed carries declarations; file-size is declared in both
    with DIFFERENT dispositions so local-wins is observable."""
    local = _pre_ge132_table()
    assert not _declared_ids(local), "pre-GE-132 table already carries dispositions"
    seed = copy.deepcopy(local)
    for rule in seed["rules"]:
        if rule["hook_id"] == "check-complexity":
            rule.update(DECL)
        if rule["hook_id"] == "check-file-size":
            rule.update(disposition="mechanical-autofix", instruction="seed text", agent=None, skills=[])
    for rule in local["rules"]:
        if rule["hook_id"] == "check-file-size":
            rule.update(disposition="author-clears", instruction="local text", agent=None, skills=[])
    return local, seed, _real_manifest()


def _all_declared_seed(manifest: dict) -> tuple[dict, set[str]]:
    """The clean seed with a declaration for every gating check (so only the
    ratchet, never 'no declaration', can refuse), plus the ids it had to declare."""
    seed = _clean_seed(manifest)
    missing = _undeclared(manifest, seed)
    for hook_id in sorted(missing):
        seed["rules"].append({"hook_id": hook_id, "category": "structural", **DECL})
    assert not _undeclared(manifest, seed)
    return seed, missing
