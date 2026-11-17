"""Support for the AR-400a-1 / -2 / AR-400c-1 reference-gate tests (TDD red phase).

ASSUMED PRODUCTION CONTRACT (the coder implements exactly this; every assertion below is
phrased against what the real entry points PRINT or RETURN, never against a helper name):

  * ``registry_validator.validate_agent_registry(package_root)`` RETURNS one error string per
    path-form reference to a skill that the package does not ship. The string names the
    specialist (or, for a shared guide, the guide's repo-relative file), the ability id, the
    repo-relative file and the 1-based line, and contains the phrase ``ability does not exist``.
  * the CLI ``python scripts/registry_validator.py`` prints each as ``ERROR: <string>`` and
    exits 1; ``build._validate_all`` returns 1 (the build aborts before any deploy phase).
  * the run STATES the examined counts in its stdout, in any phrasing that puts the number
    next to the word ``definition(s)`` / ``guide(s)`` -- ``61 specialist definitions``,
    ``definitions examined: 61``, ``definitions_examined=61`` all parse (see ``reported``).
  * a zero population (no definitions, or no guides) is a returned error that says ``zero``
    (or ``0``) next to ``definition`` / ``guide`` and names the absolute location looked in.
  * ``check_skills_invoked_xref`` and its print loop are gone: no ``skills_invoked`` line.

Fixtures: template frontmatter bytes come from ``yaml.safe_dump``; registry records are
deep copies of a real record (``product-owner``) written with ``json.dumps``; the slice is a
REAL copy of ``templates/`` (the scanner's ``rglob`` does not follow symlinks, so a symlinked
slice would examine nothing) and the real ``config/``.
"""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

_SUP = Path(__file__).resolve().parent.parent / "agents" / "_ar_200b_2_support.py"
_spec = importlib.util.spec_from_file_location("_ar_200b_2_support", _SUP)
assert _spec is not None and _spec.loader is not None, f"cannot load {_SUP}"
S = importlib.util.module_from_spec(_spec)
sys.modules["_ar_200b_2_support"] = S
_spec.loader.exec_module(S)

REPO_ROOT: Path = S.REPO_ROOT
GHOST = "ghost-ability"
GHOST_SENTENCE = f"Load `.claude/skills/{GHOST}/SKILL.md` and follow it"
KIND = "ability does not exist"
FILLER = "Plain descriptive prose that names no ability."


def make_slice(base: str | Path) -> Path:
    """A clean copied package slice whose ``templates/`` is a REAL copy (no symlinks)."""
    root = S.make_clean_package(Path(base) / "pkg")
    for entry in sorted((root / "templates").iterdir()):
        if entry.is_symlink():
            target = entry.resolve()
            entry.unlink()
            if target.is_dir():
                shutil.copytree(target, entry, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(target, entry)
    return root


def make_build_package(base: str | Path) -> Path:
    """The slice plus a REAL copy of ``scripts/`` and ``docs/`` so a spawned ``build.py``
    resolves ITS package root to the copy and can never write through into the real tree."""
    root = make_slice(base)
    for name in ("scripts", "docs"):
        dest = root / name
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        elif dest.is_dir():
            shutil.rmtree(dest)
        shutil.copytree(REPO_ROOT / name, dest, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def _registry(root: Path) -> dict:
    return json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))


def _write_registry(root: Path, data: dict) -> None:
    (root / "config" / "agent_registry.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def pad_to_line(prefix: str, line_no: int, sentence: str) -> str:
    """``prefix`` + filler so ``sentence`` sits on 1-based ``line_no`` of the result."""
    lines = prefix.splitlines()
    assert len(lines) < line_no, f"prefix already has {len(lines)} lines, cannot reach {line_no}"
    lines += [FILLER] * (line_no - 1 - len(lines))
    lines.append(sentence)
    out = "\n".join(lines) + "\n"
    assert out.splitlines()[line_no - 1] == sentence
    return out


def put_line(path: Path, line_no: int, sentence: str) -> None:
    """Make ``sentence`` line ``line_no`` of an existing file (replacing what was there)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    lines += [FILLER] * max(0, line_no - len(lines))
    lines[line_no - 1] = sentence
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert path.read_text(encoding="utf-8").splitlines()[line_no - 1] == sentence


def plant_agent(root: Path, name: str = "probe-agent", *, sentence: str | None = None,
                line: int = 40, grants: tuple[str, ...] = ()) -> Path:
    """Plant one specialist (template via yaml.safe_dump + registry record cloned from the
    real ``product-owner``). With ``sentence`` it lands on 1-based ``line`` of the file."""
    fm: dict = {"name": name, "description": f"{name} planted specialist",
                "tools": "Bash, Read, Skill", "model": "sonnet", "produces": "analysis",
                "skills": [{"skill_id": g, "mode": "always"} for g in grants]}
    front = "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n"
    text = pad_to_line(front, line, sentence) if sentence else front + "\nbody\n"
    path = root / "templates" / "agents" / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    data = _registry(root)
    rec = copy.deepcopy(next(a for a in data["agents"] if a["id"] == "product-owner"))
    rec.update({"id": name, "name": name, "tier": "utility", "template_path": f"templates/agents/{name}.md"})
    rec["skills_invoked"] = [{"skill_id": g, "mode": "always"} for g in grants]
    data["agents"] = [a for a in data["agents"] if a["id"] != name] + [rec]
    _write_registry(root, data)
    return path


def plant_skill(root: Path, name: str, *, sentence: str | None = None, line: int = 12) -> Path:
    """Create ``templates/skills/<name>/SKILL.md`` (frontmatter via yaml.safe_dump)."""
    front = "---\n" + yaml.safe_dump({"name": name, "description": f"{name} planted ability"},
                                      sort_keys=False) + "---\n"
    d = root / "templates" / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    text = pad_to_line(front, line, sentence) if sentence else front + "\nbody\n"
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    return d / "SKILL.md"


def grant_to(root: Path, agent: str, skill_id: str) -> None:
    """Add a ``skills:`` grant to a planted agent's template and registry record."""
    path = root / "templates" / "agents" / f"{agent}.md"
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    head = yaml.safe_load(text[3:end])
    head["skills"] = list(head.get("skills") or []) + [{"skill_id": skill_id, "mode": "always"}]
    path.write_text("---\n" + yaml.safe_dump(head, sort_keys=False) + text[end + 1:], encoding="utf-8")
    data = _registry(root)
    for rec in data["agents"]:
        if rec["id"] == agent:
            rec["skills_invoked"] = list(rec.get("skills_invoked") or []) + [{"skill_id": skill_id, "mode": "always"}]
    _write_registry(root, data)


def cli(root: Path) -> tuple[int, str]:
    """The real ``python scripts/registry_validator.py`` over ``root`` -> (exit, stdout+stderr)."""
    cp = S.run_registry_cli(root)
    return cp.returncode, cp.stdout + "\n" + cp.stderr


def validate(root: Path) -> tuple[list[str], str]:
    return S.run_validate(root)


def build_door(root: Path) -> tuple[int, str]:
    """``build._validate_all`` -- the exact decision ``build.py main()`` aborts on (1 == abort)."""
    sys.path.insert(0, str(S.REPO_ROOT))
    import build

    buf = io.StringIO()
    with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        config = build.load_config(None, Path(tmp))
        rc = build._validate_all(config, root, False, False)
    return rc, buf.getvalue()


def lines_of(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip()]


def findings(text_or_errors: str | list[str], ability: str, subject: str | None = None) -> list[str]:
    """Lines/errors of the ``ability does not exist`` kind for ``ability`` (optionally for a subject)."""
    items = lines_of(text_or_errors) if isinstance(text_or_errors, str) else list(text_or_errors)
    return [e for e in items if ability in e and KIND in e.lower() and (subject is None or subject in e)]


def names_line(entry: str, rel_file: str, line_no: int) -> bool:
    """The entry names the repo-relative file and the 1-based line (``:40`` or ``line 40``)."""
    return rel_file in entry and re.search(rf"(?:line\s*{line_no}\b|:{line_no}\b)", entry) is not None


def reported(text: str, word: str) -> list[int]:
    """Every integer the run printed next to ``definition(s)`` / ``guide(s)``."""
    found: list[int] = []
    for ln in text.splitlines():
        found += [int(m.group(1)) for m in re.finditer(rf"(\d+)\s+(?:\w+\s+){{0,2}}?{word}s?\b", ln, re.I)]
        found += [int(m.group(1)) for m in re.finditer(rf"{word}s?(?:\s+\w+){{0,2}}?\s*[:=]\s*(\d+)", ln, re.I)]
    return found


def expected_counts(root: Path) -> tuple[int, int]:
    """(definitions, guides) derived INDEPENDENTLY from the copied tree: definitions are the
    registry agents whose template resolves under templates/agents/; guides are every other
    ``.md`` under templates/ (what ``check_skill_refs.scan`` walks)."""
    agents_dir = root / "templates" / "agents"
    defs = set()
    for rec in _registry(root)["agents"]:
        tp = rec.get("template_path")
        if tp and (root / tp).is_file() and (root / tp).resolve().parent == agents_dir.resolve():
            defs.add((root / tp).resolve())
    every = {p.resolve() for p in (root / "templates").rglob("*.md")}
    return len(defs), len(every - defs)


def is_zero_message(entry: str, word: str, location: Path) -> bool:
    """States zero ``word`` (definition/guide) examined and names the absolute location."""
    return (re.search(rf"(?:\bzero\b|\b0\b)[^\n]*{word}", entry, re.I) is not None
            and str(location) in entry)


def success_line(text: str) -> list[str]:
    """Lines that read as a clean verdict ('OK' / 'no faults' / 'consistent (no errors)')."""
    return [ln for ln in lines_of(text)
            if re.search(r"\bOK\b|no faults|no findings|\(no errors\)", ln, re.I)]
