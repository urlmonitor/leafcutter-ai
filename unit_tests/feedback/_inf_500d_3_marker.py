"""
MODULE: _inf_500d_3_marker
GOAL: Lift the submit / read-back / recovery-search commands of the DEPLOYED instruction surfaces,
    run them in a copied layout against a stand-in submit entry point, and work out which value
    the agent records -- for the INF-500d-3-iv / -v / -vi test files.
BUSINESS CONTEXT: INF-500d-3 makes ``submit_feedback.py`` print one ``submit-failed:<reason>:<category>``
    stderr line on every failure it controls. The CALLER (an instruction surface) records the
    marker. These helpers execute what the instructions prescribe instead of grepping them.
ARCHITECTURE: Builds on the INF-500d-3-ii harness (``_inf_500d_3_helpers``, ``_inf_500d_3_ii_check``,
    ``_inf_500d_3_ii_run``) and adds only what that harness lacks: discovery of the read-back
    command (the 3-ii ``searches()`` only matches the sidecar grep), discovery of the deployed
    copies of the shared sign-off block, a stand-in entry point, and the capture precedence of
    INF-500d-3 as a pure function over the commands' outputs.

CONTRACT FOR THE INSTRUCTIONS (the llm-expert edits the surfaces against it):
    * A submit command is a logical line running ``submit_feedback.py`` with ``2>`` to a per-run file.
    * Its read-back of the run's own failure line is ONE command line that starts with a command word
      (sed, awk, grep, cat ...), names the SAME per-run file (same placeholders) and carries the literal
      ``submit-failed:``. It prints the line by its prefix and exits 0 when the file has none
      (a prefix-print such as ``sed -n``; a bare grep exits 1 and is refused).
    * Its recovery search is ONE command line naming the same per-run file and carrying ``sidecar:``.
    * No prescribed command chains, pipes or subshells.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from unit_tests.feedback import _inf_500d_3_helpers as h3
from unit_tests.feedback._inf_500d_3_ii_check import COMBOS, RUN_A, Redirect, Run, fill, logical_lines, redirects
from unit_tests.feedback._inf_500d_3_ii_run import error_file, prepare, run_shell
from unit_tests.feedback._inf_500d_4_vi_helpers import _SCRIPT_PREFIX_RE

BLOCK_HEADING = "## Sign-off (when ticket_path is provided)"
BLOCK_SIGNATURE = "**Comment heading (signoff §3):**"
FAILURE_PREFIX = "submit-failed:"
SINK_PREFIX = "[submit_feedback] sink:"
RECOVERED_ID = "fb_2026-11-16_1a2b3c4d"
DECOY_NEWEST_ID = "fb_2026-08-25_9057159a"
COMMAND_WORDS = frozenset({"sed", "awk", "grep", "cat", "tail", "head", "cut", "perl", "python3", "python", "tr"})
EVENT_KINDS = ("mechanical-retry", "cross-agent-rework", "brainstorm-escalation", "halt")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")

_STUB = (
    "import json, os, sys\n"
    "cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stub_config.json')))\n"
    "for line in cfg['stderr']:\n"
    "    print(line, file=sys.stderr)\n"
    "sys.exit(cfg['rc'])\n"
)


# ---------------------------------------------------------------------------
# the deployed copies of the shared sign-off block
# ---------------------------------------------------------------------------

def shared_block_region(text: str) -> str | None:
    """The appended shared sign-off block inside a deployed agent, or None when it carries none."""
    at = text.find(BLOCK_SIGNATURE)
    if at < 0:
        return None
    start = text.rfind(BLOCK_HEADING, 0, at)
    end = text.find("\n## ", at)
    return text[(start if start >= 0 else at):(len(text) if end < 0 else end)]


def block_copies(surfaces: dict[str, str]) -> dict[str, str]:
    """{deployed path: block text} for every deployed agent that carries the shared block (never a fixed list)."""
    found = {}
    for rel, text in sorted(surfaces.items()):
        region = shared_block_region(text) if rel.startswith("agents/") else None
        if region:
            found[rel] = region
    return found


# ---------------------------------------------------------------------------
# lifting
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Recipe:
    surface: str
    submit: Redirect
    readbacks: tuple[str, ...]  # command lines that read the run's own ``submit-failed:`` line
    searches: tuple[str, ...]   # command lines that read the run's own ``sidecar:`` line

    @property
    def event_kind(self) -> str | None:
        return next((k for k in EVENT_KINDS if k in self.submit.target), None)


def _is_command(logical: str) -> bool:
    words = logical.lstrip("$ ").split(None, 1)
    return bool(words) and words[0] in COMMAND_WORDS


def _reads_file(logical: str, red: Redirect) -> bool:
    return all(fill(red.target, run) in fill(logical, run) for run in COMBOS)


def lift_recipes(surface: str, text: str) -> list[Recipe]:
    """One recipe per redirecting submit command of ``text``, with the read commands of its own file."""
    lines = logical_lines(text)
    found = []
    for red in redirects(surface, text):
        reads, searches = [], []
        for _number, logical in lines:
            if "submit_feedback.py" in logical or not _is_command(logical) or not _reads_file(logical, red):
                continue
            if FAILURE_PREFIX in logical:
                reads.append(logical)
            if "sidecar:" in logical:
                searches.append(logical)
        found.append(Recipe(surface, red, tuple(reads), tuple(searches)))
    return found


def six_surface_recipes(surfaces: dict[str, str]) -> tuple[list[tuple[str, Recipe]], list[str]]:
    """(label, recipe) for the six surfaces of INF-500d-3-v, and one message per surface that lifted nothing."""
    problems, found = [], []
    copies = block_copies(surfaces)
    if len(copies) < 5:
        problems.append(f"only {len(copies)} deployed copies of the shared sign-off block discovered (about 24 expected)")
    for rel, region in copies.items():
        lifted = lift_recipes(rel, region)
        if not lifted:
            problems.append(f"{rel}: the shared sign-off block carries no redirecting submit command")
        found += [(f"{rel}#block", r) for r in lifted]
    for label, rel, floor in (("python-coder", "agents/python-coder.md", 1),
                              ("documentation-verifier", "agents/documentation-verifier.md", 1),
                              ("user-surface-smoker", "agents/user-surface-smoker.md", 1),
                              ("ticket-supervisor", "agents/ticket-supervisor.md", 4),
                              ("epic-supervisor", "agents/epic-supervisor.md", 1)):
        lifted = lift_recipes(rel, surfaces.get(rel, ""))
        if len(lifted) < floor:
            problems.append(f"{label}: {len(lifted)} redirecting submit command(s) lifted, {floor} expected")
        found += [(label, r) for r in lifted]
    return found, problems


def distinct(labelled: list[tuple[str, Recipe]]) -> list[tuple[str, Recipe]]:
    """Identical recipes (the shared block's copies) are run once; the copies agree by construction."""
    seen, out = set(), []
    for label, recipe in labelled:
        key = (recipe.submit.command, recipe.readbacks, recipe.searches)
        if key not in seen:
            seen.add(key)
            out.append((label, recipe))
    return out


def compound_operators(command: str) -> list[str]:
    """Chain / pipe / subshell operators outside quotes (the shell convention bans every one)."""
    bare = _QUOTED.sub("", command)
    return [op for op in ("&&", "||", ";", "|", "$(", "`") if op in bare]


def category_of(command: str, run: Run = RUN_A) -> str:
    match = re.search(r"--category\s+(\S+)", fill(command, run))
    assert match, f"no --category in {command!r}"
    return match.group(1)


# ---------------------------------------------------------------------------
# the stand-in entry point and the copied layout
# ---------------------------------------------------------------------------

def set_stub(layout: h3.Layout, stderr_lines: list[str], rc: int) -> None:
    """Replace the copied layout's submit_feedback.py by one that prints nothing on stdout, the given
    stderr lines, and exits ``rc``."""
    script = layout.out_root / "scripts" / "feedback" / "submit_feedback.py"
    script.write_text(_STUB, encoding="utf-8")
    (script.parent / "stub_config.json").write_text(json.dumps({"stderr": stderr_lines, "rc": rc}), encoding="utf-8")


def remove_entry_point(layout: h3.Layout) -> None:
    (layout.out_root / "scripts" / "feedback" / "submit_feedback.py").unlink()


def remove_declaration(layout: h3.Layout) -> None:
    (layout.out_root / "config" / "knowledge_sink.json").unlink()


def vocabulary(layout: h3.Layout) -> dict:
    path = layout.out_root / "scripts" / "feedback" / "submit_failure_reasons.json"
    assert path.is_file(), f"vocabulary missing in the copied layout: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def reason_ids(layout: h3.Layout) -> list[str]:
    return [r["id"] for r in vocabulary(layout)["reasons"]]


def plant_decoys(layout: h3.Layout) -> list[Path]:
    """Recovery files of other agents (the newest holds DECOY_NEWEST_ID) and another agent's error file."""
    planted = []
    for index, (name, text) in enumerate((("feedback_id_100.txt", "fb_2026-08-25_00000001"),
                                          ("feedback_id_200.txt", "fb_2026-08-25_00000002"),
                                          ("feedback_id_300.txt", DECOY_NEWEST_ID))):
        path = layout.tmpdir / name
        path.write_text(text + "\n", encoding="utf-8")
        os.utime(path, (1_700_000_000 + index * 100, 1_700_000_000 + index * 100))
        planted.append(path)
    other = layout.tmpdir / "feedback_err_99-other-ticket.md_pr-reviewer.txt"
    other.write_text(f"sidecar:{planted[-1]}\n", encoding="utf-8")
    return [*planted, other]


# ---------------------------------------------------------------------------
# running a recipe and deciding what the agent records
# ---------------------------------------------------------------------------

@dataclass
class Outcome:
    category: str
    rc: int
    stdout: str
    err_file: Path
    err_text: str
    readback_out: list[str]
    readback_rc: list[int]
    search_out: list[str]
    search_rc: list[int]

    @property
    def failure_lines(self) -> list[str]:
        return [ln for out in self.readback_out for ln in out.splitlines() if ln.startswith(FAILURE_PREFIX)]

    @property
    def recovery_paths(self) -> list[Path]:
        paths = []
        for out in self.search_out:
            for ln in out.splitlines():
                text = ln.strip().removeprefix("sidecar:").strip()
                if text:
                    paths.append(Path(text))
        return paths

    @property
    def has_sink_line(self) -> bool:
        return any(ln.startswith(SINK_PREFIX) for ln in self.err_text.splitlines())

    @property
    def value(self) -> str:
        return decide(self.stdout, self.failure_lines, self.recovery_paths, self.has_sink_line, self.category)

    @property
    def recorded(self) -> str:
        return f"feedback-id: {self.value}"


def decide(stdout: str, failure_lines: list[str], recovery_paths: list[Path], has_sink_line: bool, category: str) -> str:
    """INF-500d-3's capture precedence over the outputs of the lifted commands."""
    if stdout.strip():
        return stdout.strip()
    for path in recovery_paths:
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if h3.ID_RE.fullmatch(text):
                return text
    if failure_lines:
        return f"({failure_lines[0]})"
    if recovery_paths or has_sink_line:
        return f"(submit-failed:written-uncited:{category})"
    return f"(submit-failed:facility-unavailable:{category})"


def execute(recipe: Recipe, layout: h3.Layout, run: Run = RUN_A, *, category: str | None = None) -> Outcome:
    """Run the submit command, then each lifted read command, each as its own bash -c call."""
    command = recipe.submit.command
    if category:
        command = re.sub(r"--category\s+\S+", f"--category {category}", command)
    proc = run_shell(prepare(command, run, layout), layout)
    target = error_file(recipe.submit, run, layout)
    err_text = target.read_text(encoding="utf-8") if target.is_file() else ""
    reads = [run_shell(prepare(c, run, layout), layout) for c in recipe.readbacks]
    finds = [run_shell(prepare(c, run, layout), layout) for c in recipe.searches]
    return Outcome(category_of(command, run), proc.returncode, proc.stdout, target, err_text,
                   [r.stdout for r in reads], [r.returncode for r in reads],
                   [r.stdout for r in finds], [r.returncode for r in finds])


def run_case(recipe: Recipe, layout: h3.Layout, stderr_lines: list[str], rc: int = 1, *,
             run: Run = RUN_A, category: str | None = None) -> Outcome:
    set_stub(layout, stderr_lines, rc)
    return execute(recipe, layout, run, category=category)


def failure_line(reason: str, category: str) -> str:
    return f"{FAILURE_PREFIX}{reason}:{category}"


# ---------------------------------------------------------------------------
# the live-surface-tester capture block (INF-500d-3-iv)
# ---------------------------------------------------------------------------

def lift_capture_block(text: str) -> list[str]:
    """Fenced code blocks of the agent's OWN text (not the appended shared block) that submit and capture FB_ID."""
    own = text
    region = shared_block_region(text)
    if region:
        own = text.replace(region, "")
    blocks = re.findall(r"```[a-z]*\n(.*?)```", own, flags=re.DOTALL)
    return [b for b in blocks if "submit_feedback.py" in b and "FB_ID" in b]


def run_block(block: str, layout: h3.Layout, run: Run = RUN_A):
    """Run a lifted multi-line capture block with bash; report its last exit status and FB_ID."""
    text = fill(block, run).replace("/tmp/", f"{layout.tmpdir}/")
    text = _SCRIPT_PREFIX_RE.sub(lambda m: f"{layout.out_root}/{m.group(1)}", text)
    script = text.rstrip("\n") + "\n__rc=$?\nprintf 'RC=%s\\nFB=%s' \"$__rc\" \"$FB_ID\"\n"
    proc = run_shell(script, layout)
    match = re.search(r"RC=(\d+)\nFB=(.*)\Z", proc.stdout, flags=re.DOTALL)
    assert match, f"the block printed no RC/FB report: stdout={proc.stdout!r} stderr={proc.stderr[:300]!r}"
    return int(match.group(1)), match.group(2)
