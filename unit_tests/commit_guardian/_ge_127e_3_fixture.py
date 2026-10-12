"""
MODULE: unit_tests/commit_guardian/_ge_127e_3_fixture.py
COVERS: GE-127e-3 (shared fixture module -- carries no tests of its own)

GOAL: Fixture builders and extraction helpers for GE-127e-3's seven
    descriptors -- every further action a refusal names must be carried out
    from the SAME non-interactive subprocess-shaped context the hook itself
    runs in, every "already done" claim must be independently reproducible
    from that same run's own inputs, no future-tense promise may appear or
    be enacted, and a refusal naming nothing at all must be compliant.

REUSED, NOT REINVENTED. Per the ticket's own instruction, this module
    imports rather than re-implements the git/subprocess plumbing already
    proven out in this package: ``_ge_127e_1_fixture`` (``run_check``,
    ``run_check_via_hook``, ``build_into``, ``fresh_repo_dir``,
    ``init_repo``, ``commit_all``, ``stage_all``, the part-source builders)
    and ``_ge_127e_2_fixture`` (``build_disposable_commit_guardian``,
    ``run_check_in``, ``fresh_disposable_repo`` -- the disposable,
    git-repo-local copy of the production modules the mandatory mutation
    proofs run against, per this file's own module docstring's model:
    "note run_check_in targets the disposable copy while run_check targets
    the real tree -- keep that distinction").

THE ANTI-GREP DISCHARGE, STATED ONCE HERE. ``extract_named_actions`` never
    hardcodes ``/code-refactoring-specialist`` (or any other token): it reads
    backtick-quoted spans out of the REAL text a real refusal emits and
    keeps only the ones shaped like a further action a reader could try to
    carry out -- a slash command (``/foo``) or an agent reference
    (``@foo``), the two forms this component already uses to name "something
    to run... a helper to use, or a specialist to bring in." A sentence
    added later that names a NEW helper is picked up automatically; nothing
    here needs updating for that to happen.
    ``attempt_action_from_subprocess_context`` then genuinely ATTEMPTS each
    extracted token from the same kind of context ``check_file_size.py``
    itself runs in -- a non-interactive subprocess, with no live agent
    session and no shell alias pre-installed for it -- via ``shutil.which``
    (which itself, for a token containing "/", checks that exact path
    rather than searching ``$PATH``, mirroring exactly how ``subprocess``
    would resolve the same string) followed by a real ``subprocess.run`` if
    and only if something resolves. This is "carry it out", not "check it is
    mentioned" -- the discharge CLAUDE.md's "Gate / Workflow ACs" section
    and this AC's architect-review both require.

WHY THE MUTATION PROOFS RUN AGAINST A "PROSPECTIVE FIX" BASELINE, NOT
    AGAINST TODAY'S REAL SHIPPED TEXT. Today's real, unfixed
    ``_print_too_large_file`` already names an unkeepable action (the
    `/code-refactoring-specialist` pointer -- see
    ``test_ge_127e_3_incumbent_and_already_done.py``, which is RED against
    it for that reason, on the real tree, with no mutation involved). Layering
    the BA's injections on top of THAT already-red baseline would not
    isolate each injection's own signal -- a red result would be
    ambiguous between "the pre-existing defect" and "the injection". Per
    architect-review's own design ruling 2 ("delete, don't soften"), this
    module's ``apply_prospective_fix_delete_helper_pointer`` builds, on a
    DISPOSABLE copy only, the one narrow textual change design ruling 2
    prescribes (removing the ``if filepath.endswith(".py") ... else ...``
    block that prints the unkeepable pointer -- nothing else in the
    function is touched), so each mutation test's "RED under injection /
    GREEN on revert" cycle is measured against a clean floor and reflects
    ONLY the injected sentence's own effect. This narrows, rather than
    replaces, python-coder's task: it is silent on the exact wording of the
    surrounding sentences, which remains python-coder's to decide.

DECISION HISTORY
- 2026-09-23 [GE-127e-3/test-writer]: Initial authoring.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_1_fixture as e1  # noqa: E402
import _ge_127e_2_fixture as e2  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
from _file_description import describe_file  # noqa: E402

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 10

# Re-exported so every test_ge_127e_3_*.py file can import ONE module.
fresh_repo_dir = e1.fresh_repo_dir
init_repo = e1.init_repo
commit_all = e1.commit_all
stage_all = e1.stage_all
run_check = e1.run_check
run_check_via_hook = e1.run_check_via_hook
build_into = e1.build_into
make_part_source = e1.make_part_source
make_multi_part_fixture = e1.make_multi_part_fixture
PY_LIMIT = e1._PY_LIMIT
fresh_disposable_repo = e2.fresh_disposable_repo
build_disposable_commit_guardian = e2.build_disposable_commit_guardian
run_check_in = e2.run_check_in
stage_two_different_files = e2.stage_two_different_files
extract_per_file_too_large_blocks = e2.extract_per_file_too_large_blocks
block_for_suffix = e2.block_for_suffix
extract_quoted_length_and_limit = e1.extract_quoted_length_and_limit
extract_named_portions = e1.extract_named_portions
extract_sides = e1.extract_sides
has_no_division_marker = e1.has_no_division_marker

# ---------------------------------------------------------------------------
# Staging -- a single covered file, over its limit, for a real refusal.
# ---------------------------------------------------------------------------


def stage_single_oversized_py_file(root: Path, name: str = "oversized.py") -> Path:
    """Establish an under-limit .py file, then stage it over PY_LIMIT."""
    target = root / name
    target.write_text(make_part_source("placeholder_stub", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit file")
    target.write_text(make_part_source("oversized_body", PY_LIMIT + 60), encoding="utf-8")
    stage_all(root)
    return target


def stage_single_oversized_sql_file(root: Path, sql_limit: int, name: str = "oversized.sql") -> Path:
    """Establish an under-limit .sql file, then stage it over *sql_limit*.

    Raw padded content, not valid SQL -- ``describe_file``'s SQL extractor
    may or may not resolve it into parts, which is irrelevant to what this
    file's tests check (the GENERIC fallback sentence in
    ``_print_too_large_file``'s else branch), only the length verdict and
    the refusal text matter here.
    """
    target = root / name
    target.write_text("-- placeholder\n" * 5, encoding="utf-8")
    commit_all(root, "establish under-limit file")
    target.write_text("\n".join(f"-- line {i:05d}" for i in range(sql_limit + 50)) + "\n", encoding="utf-8")
    stage_all(root)
    return target


# ---------------------------------------------------------------------------
# Extraction -- generic, reads the actual emitted text, hardcodes nothing.
# ---------------------------------------------------------------------------

_BACKTICK_SPAN_RE = re.compile(r"`([^`]+)`")
_SLASH_COMMAND_RE = re.compile(r"^(/[\w-]+)")
_AGENT_REF_RE = re.compile(r"^(@[\w-]+)")

_FUTURE_PROMISE_RE = re.compile(
    r"\bwill\s+be\s+(queued|scheduled|produced|generated|created|sent|provided|engaged|run|performed|reviewed|processed)\b"
    r"|\bqueued\s+for\s+(follow[- ]?up|review|processing)\b"
    r"|\b(follow[- ]?up\s+(report|review)\s+will)\b",
    re.IGNORECASE,
)


def extract_named_actions(refusal_text: str) -> list[str]:
    """Extract every further-action token named in *refusal_text*.

    A named action is a backtick-quoted slash command (``/foo``) or an
    ``@agent`` reference -- read from the text's own backtick spans, never
    hardcoded. See this module's docstring for why this is the discharge of
    the anti-grep trap rather than a string match on a known-bad line.
    """
    actions: list[str] = []
    for span in _BACKTICK_SPAN_RE.findall(refusal_text):
        token = span.strip()
        match = _SLASH_COMMAND_RE.match(token) or _AGENT_REF_RE.match(token)
        if match:
            actions.append(match.group(1))
    return actions


def find_future_promise_statements(refusal_text: str) -> list[str]:
    """Return every substring of *refusal_text* reading as a future-tense
    promise that something will be done on the author's behalf later."""
    return [m.group(0) for m in _FUTURE_PROMISE_RE.finditer(refusal_text)]


def attempt_action_from_subprocess_context(action: str, target_file: str) -> tuple[bool, str]:
    """Genuinely attempt to carry out *action* from a non-interactive
    subprocess context -- no live agent session, no pre-installed alias.

    Returns:
        (actionable, detail) -- actionable is True only if *action*
        resolves to a real executable AND that executable runs and exits 0.
    """
    resolved = shutil.which(action)
    if resolved is None:
        return False, f"{action!r} does not resolve to any executable from this subprocess's PATH/filesystem (shutil.which found nothing)."
    try:
        result = subprocess.run(
            [resolved, target_file],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{action!r} resolved to {resolved!r} but could not be executed: {exc}"
    if result.returncode != 0:
        return False, f"{action!r} ran but exited {result.returncode}: {result.stderr.strip()!r}"
    return True, f"{action!r} ran successfully: {result.stdout.strip()!r}"


def snapshot_files(root: Path) -> set[Path]:
    """A set of every file under *root*, for a before/after "nothing new
    was written for later consumption" comparison.

    Excludes ``__pycache__``/``.pyc`` -- the interpreter's own import
    bytecode cache, an artifact of the disposable copy's modules being
    imported at all, not something the CHECK ITSELF wrote for later
    consumption. Counting it would falsely redden every disposable-copy
    run, in a way with no connection to this AC's own subject.

    Also excludes ``.git/objects``: git's own auto-gc can write a transient
    ``tmp_pack_*`` there at any moment (flaked in CI), unrelated to the check.
    Only that subtree is excluded -- a stray file the check leaves elsewhere
    in ``.git`` or the working tree is still caught.
    """
    objects = root / ".git" / "objects"
    return {
        p
        for p in root.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix != ".pyc"
        and objects not in p.parents
    }


def independent_description_for(filepath: str, content: str, quoted_length: int):
    """Call the REAL, unmutated ``describe_file`` directly, independently of
    any subprocess run, so a claim printed by a run can be checked against a
    fresh computation over the SAME inputs that run had."""
    return describe_file(filepath, content, quoted_length)


# ---------------------------------------------------------------------------
# Disposable-copy mutations -- never touch templates/scripts/commit_guardian/
# ---------------------------------------------------------------------------

_MAIN_GUARD = 'if __name__ == "__main__":'


def _insert_before_main_guard(dest: Path, injected_code: str) -> None:
    """Insert *injected_code* into *dest*'s ``check_file_size.py`` text,
    immediately BEFORE the ``if __name__ == "__main__": sys.exit(main())``
    guard -- never appended at the end of the file.

    ``check_file_size.py`` is a SCRIPT, not a pure library module (unlike
    ``_file_description.py``, the target of this package's established
    "append a redefinition, reassign after full module exec" idiom): its
    own ``sys.exit(main())`` call raises ``SystemExit`` and halts execution
    of the module the instant it is reached, so any override appended AFTER
    that line is dead code that a real run of this script as ``__main__``
    can never reach. Inserting BEFORE the guard keeps the override on the
    only code path that actually executes, while the reassignment mechanics
    (a redefinition bound at module-exec time, read by ``main()`` via a
    global name lookup made at CALL time, not at def time) are otherwise
    identical to that established idiom.
    """
    path = dest / "check_file_size.py"
    original = path.read_text(encoding="utf-8")
    marker_index = original.index(_MAIN_GUARD)
    if marker_index == -1:
        raise AssertionError(f"{path} does not contain the expected {_MAIN_GUARD!r} guard.")
    mutated = original[:marker_index] + injected_code + "\n\n" + original[marker_index:]
    path.write_text(mutated, encoding="utf-8")


def apply_prospective_fix_delete_helper_pointer(dest: Path) -> None:
    """On a DISPOSABLE copy only: remove the ``if filepath.endswith(".py")
    ... else ...`` block that prints the `/code-refactoring-specialist`
    pointer, per architect-review's design ruling 2 ("delete, don't
    soften"). Nothing else in ``_print_too_large_file`` is touched. This is
    the clean floor the mandatory mutation proofs below are measured
    against -- see this module's docstring for why.
    """
    injected_code = (
        "# TEST-INJECTED PROSPECTIVE FIX (GE-127e-3/test-writer): remove the\n"
        "# if/else block that names an unkeepable helper pointer, per\n"
        "# architect-review's design ruling 2. Nothing else changes.\n"
        "def _print_too_large_file(filepath, lines, limit):  # noqa: F811 -- intentional test override\n"
        '    print("\\u274c FILE TOO LARGE:")\n'
        '    print(f"   {filepath}")\n'
        '    print(f"   Lines: {lines} (Limit: {limit})")\n'
        "    _print_measures_line()\n"
        "    print()\n"
        "    _print_file_description(filepath, lines)\n"
        '    print("   Please refactor and split this file before committing.")\n'
        "    _print_asymmetry_advice()\n"
        '    print("   You MUST split the file to make it easier and less token consuming for agents.")\n'
        '    print("   (We enforce this check to force refactoring of older files over time).\\n")\n'
    )
    _insert_before_main_guard(dest, injected_code)


def apply_uninvokable_helper_injection(dest: Path, action_token: str) -> None:
    """On top of whatever `_print_too_large_file` currently is: insert one
    sentence naming a helper the run never invokes and that cannot be
    carried out as written -- the BA's injection 1, the exact shape of the
    recorded anti-precedent (e.g. claiming a specialist has been engaged).
    """
    injected_code = (
        "# TEST-INJECTED MUTATION (GE-127e-3/test-writer, BA injection 1):\n"
        "# name a helper the run never invokes and that cannot be carried\n"
        "# out as written -- the recorded anti-precedent's exact shape.\n"
        "_PRE_INJECTION_PRINT_TOO_LARGE_FILE = _print_too_large_file\n\n\n"
        "def _print_too_large_file(filepath, lines, limit):  # noqa: F811 -- intentional test override\n"
        "    _PRE_INJECTION_PRINT_TOO_LARGE_FILE(filepath, lines, limit)\n"
        f'    print("   A refactoring specialist has already been engaged for this file via `{action_token}`.")\n'
    )
    _insert_before_main_guard(dest, injected_code)


def apply_future_promise_injection(dest: Path) -> None:
    """On top of whatever `_print_too_large_file` currently is: insert a
    sentence stating the file has been queued for follow-up -- the BA's
    injection 2, the future-tense version of the same defect."""
    injected_code = (
        "# TEST-INJECTED MUTATION (GE-127e-3/test-writer, BA injection 2):\n"
        "# a future-tense promise that work will be done later.\n"
        "_PRE_PROMISE_PRINT_TOO_LARGE_FILE = _print_too_large_file\n\n\n"
        "def _print_too_large_file(filepath, lines, limit):  # noqa: F811 -- intentional test override\n"
        "    _PRE_PROMISE_PRINT_TOO_LARGE_FILE(filepath, lines, limit)\n"
        '    print("   A follow-up report on this file will be produced after this commit.")\n'
    )
    _insert_before_main_guard(dest, injected_code)
