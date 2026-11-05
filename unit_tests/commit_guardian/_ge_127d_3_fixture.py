"""
MODULE: unit_tests/commit_guardian/_ge_127d_3_fixture.py
COVERS: GE-127d-3 (+ -i, -ii, -iii, -iv), GE-127d-4, GE-127d-5 -- shared REPO,
    HOOK and MEASURE plumbing (carries no tests of its own).

GOAL: Build real, isolated git repositories holding a DISPOSABLE COPY of the
    check-file-size gate (source tree, never mutated in place), run the gate
    directly or through a real ``git commit`` with the registered hook, and
    read the numbers it prints.

OUTCOME VOCABULARY THESE FIXTURES PIN (test-writer design decisions, not
    AC-pinned; python-coder must honour them the way GE-127d-1's
    ``DISAGREEMENT`` / ``Compared N surface(s)`` vocabulary was honoured):
    - every covered MODIFIED file's outcome -- refused or completing -- carries
      ``Previous length: N lines`` and ``New length: M lines`` (the labels the
      existing FILE GREW refusal already uses) and ``This change added A
      measured line(s).`` for a file that stood over its limit; a completing
      outcome for such a file says it is "already over" and never "crossed".
    - a refused new-or-crossing file keeps ``Lines: N (Limit: M)``.
    - the GE-127d-4 backstop refusal carries its own heading and the sentence
      ``measured length fell from A to B while its total line count rose from
      C to D`` plus the words "separate commits" for the remedy.
    - an untokenizable file prints ``INDETERMINATE: reason=...`` (the existing
      token) naming the file and the language by name and saying its content
      "could not be read as" that language; exit 2.

DECISION HISTORY
- 2026-10-20 [GE-127d-3/test-writer]: Initial authoring.
"""

from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127d_2_fixture as fx2  # noqa: E402
from _ge_127d_3_content import EXTENSIONS, PYTHON  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN_SRC = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
HOOK_TIMEOUT = 180

_MEASURE_SCRIPT = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import _file_size_ratchet as r\n"
    "out = {}\n"
    "for p in sys.argv[2:]:\n"
    "    try:\n"
    "        out[p] = r.measure_current_length(p)\n"
    "    except Exception as exc:  # report, never mask\n"
    "        out[p] = 'ERR:' + type(exc).__name__ + ':' + str(exc)\n"
    "print(json.dumps(out))\n"
)

_PREV = re.compile(r"Previous length:\s*(\d+)\s*lines?")
_NEW = re.compile(r"New length:\s*(\d+)\s*lines?")
_ADDED = re.compile(r"added\s+(\d+)\s+(?:measured\s+)?lines?", re.IGNORECASE)
_REQUIRED = re.compile(r"Required length:\s*(\d+)")
BACKSTOP_RE = re.compile(
    r"measured length fell from\s*(\d+)\s*to\s*(\d+)\s*while its total line count rose from\s*(\d+)\s*to\s*(\d+)",
    re.IGNORECASE,
)
SEPARATE_COMMITS_RE = re.compile(r"separate\s+commits?", re.IGNORECASE)


def measure_files(paths: list[Path], src_dir: Path = GUARDIAN_SRC) -> dict[str, int | str]:
    """Measure *paths* with the shared measure in ONE cold subprocess.

    Returns ``{str(path): length}``; a path the measure could not read maps to
    an ``"ERR:..."`` string so a caller can assert on it instead of crashing.
    """
    result = subprocess.run(
        [PYTHON, "-c", _MEASURE_SCRIPT, str(src_dir), *[str(p) for p in paths]],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode != 0:
        message = f"measure subprocess failed: {result.stderr!r}"
        raise AssertionError(message)
    return json.loads(result.stdout)


def measure_texts(items: list[tuple[str, str]], src_dir: Path = GUARDIAN_SRC) -> list[int | str]:
    """Measure each ``(extension, text)`` written to a real temp file (LF bytes kept)."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for index, (ext, text) in enumerate(items):
            path = Path(tmp) / f"m{index}{ext}"
            path.write_bytes(text.encode("utf-8"))
            paths.append(path)
        measured = measure_files(paths, src_dir)
        return [measured[str(p)] for p in paths]


def copy_modules(dest: Path) -> None:
    """Copy the gate, its helpers, the measure sub-package (if any) and the parity gate."""
    fx2.copy_production_modules(dest)
    sub = GUARDIAN_SRC / "_file_size_measure"
    if sub.is_dir():
        shutil.copytree(sub, dest / "_file_size_measure", ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    parity = GUARDIAN_SRC / "check_file_size_rule_parity.py"
    if parity.exists():
        shutil.copy2(parity, dest / parity.name)


def build_repo(root: Path, *, limit: int = 40, limits: dict[str, int] | None = None) -> Path:
    """Compose a gate fixture covering every checked extension at *limit*."""
    dest = root / "scripts" / "commit_guardian"
    copy_modules(dest)
    per_ext = {ext: (limits or {}).get(ext, limit) for ext in EXTENSIONS}
    config = {
        "file_size": {
            "_comment": "GE-127d-3 fixture config.",
            "line_limits": per_ext,
            "default_limit": limit,
            "checked_extensions": list(EXTENSIONS),
            "published_rule_surfaces": ["README.md", "commit_guardian.json"],
        }
    }
    (dest / "commit_guardian.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (dest / "README.md").write_text("GE-127d-3 fixture placeholder.\n", encoding="utf-8")
    fx2.init_repo(root)
    fx2.git(["branch", "-M", "main"], root)
    return dest


def write_bytes(root: Path, rel: str, text: str, *, crlf: bool = False) -> None:
    """Write *text* under *root*; ``crlf`` converts LF to CRLF on disk."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def commit_files(root: Path, files: dict[str, str]) -> None:
    """Land *files* at HEAD with a plain commit (NO hook installed yet -- setup only)."""
    for rel, text in files.items():
        write_bytes(root, rel, text)
        fx2.git(["add", rel], root)
    result = fx2.commit_bypassing_hook(root, "setup: previous version")
    assert result.returncode == 0, f"setup commit failed: {result.stdout!r}{result.stderr!r}"


def stage(root: Path, rel: str, text: str, *, crlf: bool = False) -> None:
    """Write and ``git add`` the staged version of *rel*."""
    write_bytes(root, rel, text, crlf=crlf)
    fx2.git(["add", rel], root)


def run_gate(root: Path) -> tuple[subprocess.CompletedProcess, str]:
    """Run the fixture's own check_file_size.py directly; return (result, output)."""
    result = fx2.run_check_file_size(root)
    return result, fx2.combined_output(result)


def change_outcome(root: Path, rel: str, head_text: str | None, staged_text: str, *, limit: int = 40,
                   limits: dict[str, int] | None = None) -> tuple[subprocess.CompletedProcess, str]:
    """One whole scenario: fresh repo, *head_text* committed (if any), *staged_text* staged, gate run."""
    build_repo(root, limit=limit, limits=limits)
    # A populated HEAD holding a covered file is what makes the gate judge at all: with no covered
    # file in history it reports EMPTY HISTORY and skips, so a "new file" scenario seeds a bystander.
    commit_files(root, {rel: head_text} if head_text is not None else {"seed_bystander.py": "SEED = 1\n"})
    stage(root, rel, staged_text)
    return run_gate(root)


def install_hook(root: Path) -> None:
    """Wire the registered hook alone (AFTER every setup commit) for a real ``git commit``."""
    fx2.write_precommit_config(root)
    fx2.install_precommit(root)


def hook_commit(root: Path, message: str = "change under test") -> tuple[subprocess.CompletedProcess, str]:
    """A REAL ordinary ``git commit`` through the registered run_hook.py path."""
    result = fx2.commit(root, message)
    return result, fx2.combined_output(result)


def outcome_numbers(output: str) -> dict[str, int | None]:
    """Previous/new length, added lines and required length the outcome states."""
    def first(pattern: re.Pattern[str]) -> int | None:
        match = pattern.search(output)
        return int(match.group(1)) if match else None
    return {"previous": first(_PREV), "new": first(_NEW), "added": first(_ADDED), "required": first(_REQUIRED)}


def start_merge(root: Path, rel: str, base: str, head_text: str, other_text: str, resolved: str) -> None:
    """Leave a REAL merge in progress (MERGE_HEAD present) with *resolved* staged."""
    commit_files(root, {rel: base})
    fx2.git(["checkout", "-q", "-b", "other"], root)
    commit_files(root, {rel: other_text})
    fx2.git(["checkout", "-q", "main"], root)
    commit_files(root, {rel: head_text})
    fx2.git(["merge", "--no-commit", "--no-ff", "other"], root)  # a conflict is expected and irrelevant
    stage(root, rel, resolved)
    assert (root / ".git" / "MERGE_HEAD").exists(), "fixture failed to leave MERGE_HEAD in place"


def deployed_guardian_dir() -> Path:
    """The DEPLOYED commit_guardian directory of the shared reference layout."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        producer = importlib.import_module("scripts.suite_performance._shared_layout_producer")
        layout = producer.get_or_produce_shared_layout()
    finally:
        sys.path.remove(str(REPO_ROOT))
    for candidate in (layout / ".leafcutter" / "scripts" / "commit_guardian", layout / "scripts" / "commit_guardian"):
        if candidate.is_dir():
            return candidate
    message = f"no deployed commit_guardian directory under {layout}"
    raise AssertionError(message)


def degraded_gate_script(dest: Path, old_rule_source: str) -> Path:
    """Write a wrapper that replaces the shared measure IN-PROCESS by the old rule, then runs the gate."""
    wrapper = dest / "run_with_degraded_measure.py"
    wrapper.write_text(
        "import sys\n"
        "sys.path.insert(0, sys.path[0])\n"
        + old_rule_source
        + "import _file_size_ratchet as r\n"
        "r.count_content_lines = old_count\n"
        "r.measure_current_length = lambda fp, *a, **k: old_count(r.read_current_content(fp))\n"
        "import check_file_size as c\n"
        "for name in ('count_content_lines', 'measure_current_length'):\n"
        "    if hasattr(c, name):\n"
        "        setattr(c, name, getattr(r, name))\n"
        "sys.exit(c.main())\n",
        encoding="utf-8",
    )
    return wrapper


def plain_line_count(text: str) -> int:
    """The measure-independent total physical line count (LF/CRLF/no-trailing-newline safe)."""
    return len(text.replace("\r\n", "\n").splitlines())
