"""
MODULE: unit_tests/test_complexity_reduction_skill.py
COVERS: CR-100b-2 -- the complexity-reduction skill is packaged, installed, and
    every score it states is the shipped checker's own.

GOAL: Pin what can be checked about an instruction document without a model:
    the numbers it states, the files it points at, and that a fresh install
    carries it.

EVIDENCE STRENGTH, STATED PLAINLY:
  - The measured-example test recomputes every labelled score with the real
    calculate_complexities / calculate_sql_complexity from
    templates/scripts/commit_guardian. It runs them in a subprocess because both
    checkers import a bare ``config`` module, which must not collide with other
    tests' imports in the shared pytest process.
  - The deployed test reads the shared reference layout that build.py produced
    (``shared_layout_reader``: read only, no private build).

AC references: CR-100b-2.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SKILL_ID = "complexity-reduction"
_SKILL_PATH = _REPO_ROOT / "templates" / "skills" / _SKILL_ID / "SKILL.md"
_SKILL_REGISTRY = _REPO_ROOT / "config" / "skill_registry.json"
_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_GUARDIAN_CONFIG = _GUARDIAN_DIR / "commit_guardian.json"
_AGENTS_DIR = _REPO_ROOT / "templates" / "agents"

_EXAMPLE_RE = re.compile(r"```(python|sql)\n(.*?)```", re.DOTALL)
_MARKER_RE = re.compile(r"^(?:#|--) measured: (.+)$")
_SYS_PATH_RE = re.compile(r"sys\.path\.insert\(0, '([^']+)'\)")
_GUARDIAN_FILES = (
    "check_complexity.py",
    "check_sql_complexity.py",
    "config.py",
    "commit_guardian.json",
)

# Runs in a child interpreter: argv[1] is the commit_guardian directory, stdin
# is a JSON list of [lang, body] pairs, stdout is a JSON list of scores.
_SCORER = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from check_complexity import calculate_complexities
from check_sql_complexity import calculate_sql_complexity
scores = []
for lang, body in json.load(sys.stdin):
    if lang == "python":
        scores.append(dict(calculate_complexities(body)))
    else:
        scores.append(calculate_sql_complexity(body))
print(json.dumps(scores))
"""


def _skill_text() -> str:
    """Return the skill template's text.

    Returns:
        The full SKILL.md text of the complexity-reduction template.
    """
    return _SKILL_PATH.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    """Parse the YAML frontmatter at the top of a SKILL.md text.

    Args:
        text: SKILL.md content beginning with a ``---`` delimited block.

    Returns:
        The parsed frontmatter mapping.
    """
    _, block, _ = text.split("---", 2)
    return yaml.safe_load(block)


def _examples(text: str) -> list[tuple[str, str]]:
    """Return every fenced python or sql block in the skill.

    Args:
        text: SKILL.md content.

    Returns:
        ``(lang, body)`` pairs in document order.
    """
    return _EXAMPLE_RE.findall(text)


def _claimed(lang: str, body: str) -> dict[str, int] | int | None:
    """Read the measured marker on an example's first line.

    Args:
        lang: ``python`` or ``sql``.
        body: The fenced block's content.

    Returns:
        For python, a mapping of function name to claimed score; for sql, the
        claimed file score; None when the first line carries no marker.
    """
    match = _MARKER_RE.match(body.splitlines()[0])
    if not match:
        return None
    if lang == "sql":
        return int(match.group(1))
    pairs = (item.strip().split("=") for item in match.group(1).split(","))
    return {name: int(score) for name, score in pairs}


def _scores(examples: list[tuple[str, str]]) -> list:
    """Score every example with the shipped checkers, in a child interpreter.

    Args:
        examples: ``(lang, body)`` pairs to score.

    Returns:
        One entry per example: a name-to-score mapping for python, an int for sql.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _SCORER, str(_GUARDIAN_DIR)],
        input=json.dumps(examples),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_REPO_ROOT),
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, f"scoring subprocess failed: {proc.stderr[-2000:]}"
    return json.loads(proc.stdout)


def _registry_entries() -> list[dict]:
    """Return the skill registry entries whose id is complexity-reduction.

    Returns:
        The matching entries from config/skill_registry.json.
    """
    registry = json.loads(_SKILL_REGISTRY.read_text(encoding="utf-8"))
    return [entry for entry in registry["skills"] if entry.get("id") == _SKILL_ID]


def test_every_measured_example_matches_the_shipped_checker() -> None:
    # covers: CR-100b-2
    # angle: criterion
    """Every python/sql example carries a measured marker, and every labelled
    score equals what the shipped checker computes for that example."""
    examples = _examples(_skill_text())
    assert len(examples) >= 10, f"expected the skill's example catalogue, found {len(examples)}"

    unlabelled = [body.splitlines()[0] for lang, body in examples if _claimed(lang, body) is None]
    assert not unlabelled, f"examples without a measured marker: {unlabelled}"

    mismatches = []
    for (lang, body), actual in zip(examples, _scores(examples)):
        claimed = _claimed(lang, body)
        if lang == "sql" and claimed != actual:
            mismatches.append(f"sql {body.splitlines()[1]!r}: claimed {claimed}, checker {actual}")
        if lang == "python":
            for name, score in claimed.items():
                if actual.get(name) != score:
                    mismatches.append(f"python {name}: claimed {score}, checker {actual.get(name)}")
    assert not mismatches, "labelled scores disagree with the checker:\n" + "\n".join(mismatches)


def test_shipped_defaults_quoted_by_the_skill_match_commit_guardian_json() -> None:
    # covers: CR-100b-2
    # angle: discrimination
    """The limits table names the config keys and quotes their shipped values."""
    text = _skill_text()
    shipped = json.loads(_GUARDIAN_CONFIG.read_text(encoding="utf-8"))
    for section in ("complexity", "sql_complexity"):
        row = re.search(rf"\| `{section}\.max_score` \| (\d+) \|", text)
        assert row, f"the limits table has no row naming `{section}.max_score`"
        assert int(row.group(1)) == shipped[section]["max_score"], (
            f"skill quotes {section}.max_score = {row.group(1)}, "
            f"commit_guardian.json ships {shipped[section]['max_score']}"
        )


def test_skill_never_recommends_removing_observability() -> None:
    # covers: CR-100b-2
    # angle: failure
    """The never-remove-observability rule is stated, and no technique heading
    offers removing logging or RAISE NOTICE."""
    text = _skill_text()
    assert "never remove observability" in text.lower()
    headings = re.findall(r"^#### .+$", text, flags=re.MULTILINE)
    offending = [
        heading for heading in headings
        if re.search(r"remov|drop|delet|comment out", heading, re.IGNORECASE)
        and re.search(r"log|notice", heading, re.IGNORECASE)
    ]
    assert not offending, f"technique headings that remove observability: {offending}"


def test_registry_entry_points_at_the_template() -> None:
    # covers: CR-100b-2
    # angle: seam
    """One registry entry, portable, resolving to the template whose
    frontmatter name is the same id."""
    entries = _registry_entries()
    assert len(entries) == 1, f"expected one {_SKILL_ID} registry entry, found {len(entries)}"
    entry = entries[0]
    assert entry["portable"] is True and entry["domain"] is None
    assert entry["components"], "registry entry must declare components"
    template_dir = _REPO_ROOT / entry["template_path"].removeprefix("leafcutter/")
    assert template_dir == _SKILL_PATH.parent, f"template_path resolves to {template_dir}"
    assert _frontmatter(_skill_text())["name"] == _SKILL_ID


def test_every_refusal_naming_the_skill_names_a_packaged_skill() -> None:
    # covers: CR-100b-2
    # angle: reachability
    """Each guardian check or agent template that sends the author to the
    complexity-reduction skill names a skill with a template and a registry entry."""
    sources = sorted(_GUARDIAN_DIR.glob("*.py")) + sorted(_AGENTS_DIR.glob("*.md"))
    naming = [path.name for path in sources if _SKILL_ID in path.read_text(encoding="utf-8")]
    assert "check_complexity.py" in naming, "check_complexity.py no longer names the skill"
    assert _SKILL_PATH.is_file(), f"{naming} name {_SKILL_ID}, but no template exists"
    assert _registry_entries(), f"{naming} name {_SKILL_ID}, but it is not registered"


@pytest.mark.shared_layout_reader
def test_installed_project_has_the_skill_and_the_files_its_commands_use(
    shared_reference_layout: Path,
) -> None:
    # covers: CR-100b-2
    # angle: deployed
    """A fresh install carries the rendered skill, and every directory its
    commands put on sys.path holds the checker files they import."""
    deployed = shared_reference_layout / ".claude" / "skills" / _SKILL_ID / "SKILL.md"
    assert deployed.is_file(), f"{deployed} was not deployed"
    text = deployed.read_text(encoding="utf-8")
    assert _frontmatter(text)["name"] == _SKILL_ID
    assert "{{" not in text, "deployed skill still holds an unrendered placeholder"

    command_dirs = set(_SYS_PATH_RE.findall(text))
    assert command_dirs, "deployed skill gives no measurement command"
    for rel_dir in command_dirs:
        missing = [
            name for name in _GUARDIAN_FILES
            if not (shared_reference_layout / rel_dir / name).is_file()
        ]
        assert not missing, f"{rel_dir} in the installed project lacks {missing}"


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-09 [main-session/CR-100b-2]: Created with the complexity-reduction
  skill template. Scores are recomputed in a child interpreter so the
  checkers' bare `config` import stays out of the shared pytest process.
====================================================================
"""
