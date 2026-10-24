"""
MODULE: unit_tests/build_orchestration/_bo_4300f_2_fixtures.py
GOAL: Shared, stdlib-only support for the BO-4300f-2 proofs (tickets/.../14):
    the declared census exemption list, the census scanner, the commit-spelling
    scanner, and the "workspace passage" extractor over the DEPLOYED layout.
BUSINESS CONTEXT: One declared exemption list (two sites with reasons plus the
    seven record folders) is the single place the census reads. The scanner
    patterns are assembled from pieces at import time so that no file of this
    family -- this module included -- spells the old-way commands as literal
    text and therefore never trips the census it implements.
ARCHITECTURE: Pure functions over (root, files). ``tracked_files`` asks git for
    the real tree; fixture-tree tests hand ``scan_tree`` an explicit root. The
    deployed layout comes from the ONE shared build in
    _workspace_maker_fixtures.ensure_deployed_layout (never a build of its own).
    NOT a test file (leading underscore).

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14,
  BO-4300f-2]: Created the red baseline support module.
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14)
====================================================================
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import ensure_deployed_layout

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# --- the ONE declared exemption list ------------------------------------------------
# kind "file": a specific exempt site (never the folder around it).
# kind "folder": a record-of-the-past folder, excluded wholesale by folder.
EXEMPTIONS: list[dict[str, str]] = [
    {
        "kind": "file",
        "path": "templates/scripts/worktree_migrate.py",
        "reason": "BO-4300f-3 one-off cut-over verb: brings over or retires workspaces made the old way.",
    },
    {
        "kind": "file",
        "path": "unit_tests/build_orchestration/_workspace_maker_builders.py",
        "reason": (
            "The legacy_worktree test helper that builds an old-way workspace for the cut-over tests, "
            "and the link_checkout / unlink_checkout helpers (via _run_link), which deliberately run "
            "the raw old-way command to fabricate or remove a linked checkout as test fixtures."
        ),
    },
    {"kind": "folder", "path": "docs/analysis/", "reason": "Analyses are records of the past."},
    {"kind": "folder", "path": "docs/known-issues/", "reason": "Known issues are records of the past."},
    {"kind": "folder", "path": "docs/retrospectives/", "reason": "Retrospectives are records of the past."},
    {"kind": "folder", "path": "changelogs/", "reason": "Changelogs are records of the past."},
    {
        "kind": "folder",
        "path": "docs/architecture/adrs/",
        "reason": "An architecture decision record keeps a past decision and may quote the old commands.",
    },
    {"kind": "folder", "path": "tickets/", "reason": "Tickets are records of the past."},
    {"kind": "folder", "path": "docs/acceptance-criteria/", "reason": "Acceptance criteria are records of the past."},
]
RECORD_FOLDERS = tuple(e["path"] for e in EXEMPTIONS if e["kind"] == "folder")
EXEMPT_FILES = tuple(e["path"] for e in EXEMPTIONS if e["kind"] == "file")

# --- scanner patterns, assembled from pieces (never literal text) -----------------
_NOUN = "work" + "tree"
_SEP = r"""[\s"',\]\[]+"""
# shell form, the -C (folder first) form, argv list and JS template literal all
# reduce to: the noun, separators/quotes/commas, then the verb.
OLD_WAY_RE = re.compile(_NOUN + _SEP + r"(?:" + "ad" + "d|re" + "move)" + r"(?![\w-])")
_G = "g" + "it"
# commit delegation spelling: shell form and argv form
DASH_C_COMMIT_RES = (
    re.compile(_G + r"\s+-C\s+\S+\s+commit\b"),
    re.compile(r"""["']""" + _G + r"""["']\s*,\s*["']-C["']\s*,[^\]\n]*?,\s*["']commit["']"""),
)


def scan_text(text: str, patterns=(OLD_WAY_RE,)) -> list[int]:
    """1-based line numbers of *text* matching any pattern."""
    return [i for i, line in enumerate(text.splitlines(), 1) if any(p.search(line) for p in patterns)]


def is_exempt(relpath: str) -> bool:
    """True when *relpath* (posix) is an exempt file or sits under an exempt record folder."""
    rel = relpath.replace("\\", "/")
    return rel in EXEMPT_FILES or any(rel.startswith(f) for f in RECORD_FOLDERS)


def tracked_files(root: Path = REPO_ROOT) -> list[str]:
    """Posix relative paths of every tracked file of the repository at *root* (plus new, not-yet-added
    files that are not ignored, so a freshly written file is censused before it is ever committed)."""
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(root),
        capture_output=True,
        check=True,
    )
    return [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]


def walk_files(root: Path) -> list[str]:
    """Posix relative paths of every file under *root* (for fixture trees, ``.git`` skipped)."""
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts
    )


def read_text(path: Path) -> str | None:
    """File text, or ``None`` for a binary / unreadable file."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def census(root: Path, files: list[str], patterns=(OLD_WAY_RE,), apply_exemptions: bool = True) -> list[str]:
    """Report each hit as ``file:line`` over *files* (posix paths under *root*)."""
    hits: list[str] = []
    for rel in files:
        if apply_exemptions and is_exempt(rel):
            continue
        text = read_text(root / rel)
        if text is None:
            continue
        hits.extend(f"{rel}:{n}" for n in scan_text(text, patterns))
    return hits


# --- instruction surfaces -----------------------------------------------------------
INSTRUCTION_SURFACE_PREFIXES = (
    "templates/agents/",
    "templates/skills/",
    "templates/commands/",
    "templates/workflows/",
    "templates/workflows-js/",
    "docs/how-to/",
)
INSTRUCTION_SURFACE_FILES = ("CLAUDE.md",)
COMPONENT_FILE_PATTERNS = (
    re.compile(r"^templates/scripts/(worktree\w*|workspace_root)\.py$"),
    re.compile(r"^unit_tests/build_orchestration/_workspace_maker_\w+\.py$"),
    re.compile(r"^unit_tests/build_orchestration/test_bo_4300\w*\.py$"),
)


def commit_census_files(files: list[str]) -> list[str]:
    """The component's own files plus every instruction surface, out of *files*."""
    out = []
    for rel in files:
        if rel in INSTRUCTION_SURFACE_FILES or rel.startswith(INSTRUCTION_SURFACE_PREFIXES):
            out.append(rel)
        elif any(p.match(rel) for p in COMPONENT_FILE_PATTERNS):
            out.append(rel)
    return out


# --- deployed text surfaces & workspace passages -------------------------------------
MAKER_MARKS = ("worktree.py", "workspace maker")
HOWTO_MARK = "get-a-workspace"
_NOUN_PAT = r"(?<![\w-])(?:work" + r"tree|workspace)s?(?![\w-])"
_VERB_PAT = (
    r"(?:creat\w*|mak(?:e|es|ing)|clon(?:e|es|ing)|set(?:s|ting)?\s+up|remov\w*|delet\w*|clear\w*|"
    r"prun\w*|find\w*|locat\w*)"
)
_GAP = r"(?:\W+\w+){0,3}\W+"
_WORKSPACE_PASSAGE_RE = re.compile(
    r"\b" + _VERB_PAT + _GAP + _NOUN_PAT + "|" + _NOUN_PAT + _GAP + _VERB_PAT + r"\b", re.I
)


def deployed_layout() -> Path:
    """The shared deployed install (built once per session by the BO-4300f-4 locator)."""
    return ensure_deployed_layout()


def deployed_instruction_texts() -> dict[str, str]:
    """``{label: text}`` of every deployed charter, skill, workflow text, plus the repo's CLAUDE.md."""
    root = deployed_layout() / ".claude"
    texts: dict[str, str] = {}
    for sub, glob in (("agents", "*.md"), ("skills", "**/*.md"), ("commands", "*.md"), ("workflows", "*.js")):
        for f in sorted((root / sub).glob(glob)):
            t = read_text(f)
            if t is not None:
                texts[f".claude/{sub}/{f.relative_to(root / sub).as_posix()}"] = t
    claude = read_text(REPO_ROOT / "CLAUDE.md")
    assert claude is not None, "CLAUDE.md must be readable"
    texts["CLAUDE.md"] = claude
    return texts


def howto_texts() -> dict[str, str]:
    """Every delivered how-to guide (the project's docs/how-to and the deployed docs/how-to),
    except the two replacement pages themselves."""
    texts: dict[str, str] = {}
    for base, label in ((REPO_ROOT / "docs" / "how-to", "docs/how-to"), (deployed_layout() / "docs" / "how-to", "deployed:docs/how-to")):
        for f in sorted(base.rglob("*.md")):
            if f.name in ("get-a-workspace.md", "clear-a-workspace.md"):
                continue
            t = read_text(f)
            if t is not None:
                texts[f"{label}/{f.relative_to(base).as_posix()}"] = t
    return texts


def paragraphs(text: str) -> list[tuple[int, str]]:
    """``(first line number, paragraph text)`` blocks separated by blank lines."""
    out: list[tuple[int, str]] = []
    start, buf = 1, []
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip():
            if not buf:
                start = i
            buf.append(line)
        elif buf:
            out.append((start, "\n".join(buf)))
            buf = []
    if buf:
        out.append((start, "\n".join(buf)))
    return out


def workspace_passages(text: str) -> list[tuple[int, str]]:
    """Paragraphs that talk about making, finding or clearing a workspace."""
    return [(n, p) for n, p in paragraphs(text) if _WORKSPACE_PASSAGE_RE.search(p)]


def passages_missing_pointer(texts: dict[str, str]) -> list[str]:
    """Workflow scripts (.js) are judged by the workflow-route tests, not here."""
    texts = {k: v for k, v in texts.items() if not k.endswith(".js")}
    return _passages_missing_pointer(texts)


def _passages_missing_pointer(texts: dict[str, str]) -> list[str]:
    """``label:line`` of each workspace passage not naming BOTH the maker and the how-to page."""
    bad = []
    for label, text in texts.items():
        for n, p in workspace_passages(text):
            if not any(m in p for m in MAKER_MARKS) or HOWTO_MARK not in p:
                bad.append(f"{label}:{n}")
    return bad


# --- recipe patterns (own steps to copy / start / install / link / delete a workspace) ---
RECIPE_RES = {
    "old-way add/remove": OLD_WAY_RE,
    "clone": re.compile(_G + r"\s+clone\b"),
    "link or copy of install/hook config": re.compile(
        r"\b(?:ln\s+-\w+|cp\s+(?:-\w+\s+)*)\S*.*(?:\.leafcutter|\.pre-commit-config\.yaml)"
    ),
    "EnterWorktree": re.compile("Enter" + "Work" + "tree"),
    "manual rm": re.compile(r"\brm\s+-\w*[rR]\w*\s+\S*(?:work" + r"tree|workspace)", re.I),
}


def recipe_hits(texts: dict[str, str], only_workspace_passages_for: tuple[str, ...] = ("clone",)) -> list[str]:
    """``label:line (kind)`` for each own-recipe step found in *texts*.

    The ``clone`` kind is judged only inside workspace passages (a clone elsewhere is unrelated)."""
    hits = []
    for label, text in texts.items():
        passage_lines: set[int] = set()
        for n, p in workspace_passages(text):
            passage_lines.update(range(n, n + p.count("\n") + 1))
        for kind, rx in RECIPE_RES.items():
            for ln in scan_text(text, (rx,)):
                if kind in only_workspace_passages_for and ln not in passage_lines:
                    continue
                hits.append(f"{label}:{ln} ({kind})")
    return hits


# --- former ways: shim contract, runners, normalisation -----------------------------------
# A surviving shim of the former set-up script maps each sub-command to the maker:
#   <sub-command> <slug> --repo-root <project>   ->   ensure --kind <kind> --slug <slug> --repo-root <project>
# (ticket 14: setup-ticket -> ticket, create-only -> feature, create-ac-worktree -> ac,
#  create-fastlane-worktree -> fastlane). Absence of the script is equally conforming.
FORMER_SCRIPT = "setup_ticket_worktree.py"
FORMER_FACTS = "worktree_repo_facts.py"
FORMER_RECOVERY = "git_recovery.py"
SHIM_KIND_BY_SUBCOMMAND = {
    "setup-ticket": "ticket",
    "create-only": "feature",
    "create-ac-worktree": "ac",
    "create-fastlane-worktree": "fastlane",
}


def deployed_scripts_dir() -> Path:
    """``<deployed install>/.leafcutter/scripts`` of the shared layout."""
    return deployed_layout() / ".leafcutter" / "scripts"


def run_script(script: Path, args: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a deployed script as a separate process (never an import)."""
    return subprocess.run(
        [sys.executable, str(script), *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False
    )


def one_json(stdout: str) -> dict | None:
    """The single JSON object among the non-blank lines of *stdout*, else ``None``."""
    found = []
    for line in stdout.splitlines():
        try:
            found.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return found[0] if len(found) == 1 and isinstance(found[0], dict) else None


_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?")
_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")


def normalise(answer: dict, tmp: Path) -> str:
    """Canonical text of *answer*: timestamps, commit ids and the fixture's own temp root masked."""
    text = json.dumps(answer, sort_keys=True)
    root = str(tmp)
    forms = {root, root.replace("\\", "\\\\"), root.replace("\\", "/")}
    if len(root) > 1 and root[1] == ":":
        forms.add("/mnt/" + root[0].lower() + root[2:].replace("\\", "/"))
    for form in sorted(forms, key=len, reverse=True):
        text = text.replace(form, "<TMP>")
    text = _SHA_RE.sub("<SHA>", text)
    return _TS_RE.sub("<TS>", text)


def has_registration(project: Path) -> bool:
    """True when the main project holds any linked-workspace registration of the old kind."""
    return (project / ".git" / ("work" + "trees")).exists()


# --- the old-way command texts, for tests that assert a text does NOT carry them ------
# Assembled from pieces so the asserting test never spells the command itself.
OLD_WAY_ADD_TEXT = _G + " " + _NOUN + " " + "ad" + "d"
OLD_WAY_REMOVE_TEXT = _G + " " + _NOUN + " " + "re" + "move"
