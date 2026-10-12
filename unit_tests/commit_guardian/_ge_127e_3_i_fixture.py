"""
MODULE: unit_tests/commit_guardian/_ge_127e_3_i_fixture.py
COVERS: GE-127e-3-i (shared fixture module -- carries no tests of its own)

GOAL: Fixture builders, reason-line extraction, and disposable-copy mutation
    appliers for GE-127e-3-i's eight descriptors -- a file whose contents
    could not be described states that plainly and names the reason, and
    whether guidance exists never moves the commit verdict in either
    direction.

REUSED, NOT REINVENTED. Imports the git/subprocess plumbing and disposable
    -copy machinery already proven out on this component: ``_ge_127e_3_fixture``
    (itself re-exporting ``_ge_127e_1_fixture`` and ``_ge_127e_2_fixture``),
    including ``_insert_before_main_guard`` -- ``check_file_size.py`` ends in
    ``if __name__ == "__main__": sys.exit(main())``, so an override appended
    at end-of-file is dead code a real run can never reach; every mutation
    below is inserted BEFORE that guard.

THE REASON-LINE CONTRACT THIS MODULE'S EXTRACTOR ASSUMES. Per
    architect-review's design ruling 2, the could-not-describe state reuses
    ``_file_size_ratchet.py``'s ``TOKEN: reason=<text>`` line shape but mints
    a THIRD token distinct from ``INDETERMINATE`` and ``EMPTY HISTORY``. This
    module's ``find_could_not_describe_reason`` deliberately does not pin
    that third token's exact spelling (python-coder's to choose) -- it reads
    ANY ``<TOKEN>: reason=<text>`` line that is not one of the two
    already-established tokens, so the test contract is the SHAPE and the
    exclusion, never a guessed literal name.

THE VERDICT-INDEPENDENCE MUTATIONS RUN AGAINST A DISPOSABLE COPY'S main(),
    NOT A PRINT FUNCTION. Unlike GE-127e-3's helper-pointer mutation (a pure
    textual/print-only change), BA injections 1 and 3 change what the
    verdict IS for a file, not merely what gets printed about it -- the
    injection point is necessarily the classification loop inside main(),
    since that is where verdict and description meet. Each mutation
    redefines main() wholesale (a faithful copy of the real classification
    loop plus the one described defect), which ``check_file_size.py``'s own
    module-exec-order binds as the version main-guard's ``sys.exit(main())``
    actually calls. BA injection 2 (a substitute-advice fallback) is a pure
    print-time change and only overrides ``_print_file_description``.

WHY NO "PROSPECTIVE FIX" BASELINE IS NEEDED HERE, UNLIKE GE-127e-3'S.
    GE-127e-3's mutation proofs ran against a disposable "already fixed"
    baseline because today's REAL tree was already red for an unrelated,
    pre-existing reason (the incumbent helper-pointer sentence). This AC's
    verdict-independence property (a verdict decided before the description
    step runs) is ALREADY true of today's real, unmodified
    ``check_file_size.py`` -- architect-review's design ruling 1 confirms
    this is "ALREADY structurally satisfied" -- so the REAL production tree
    itself is a valid, honest control/revert baseline for BA injections 1
    and 3; no disposable "prospective fix" text edit is required to obtain
    one.

DECISION HISTORY
- 2026-09-28 [GE-127e-3-i/test-writer]: Initial authoring.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_3_fixture as fx3  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CONFIG = json.loads((_COMMIT_GUARDIAN_DIR / "commit_guardian.json").read_text(encoding="utf-8"))

# Re-exported so every test_ge_127e_3_i_*.py file can import ONE module.
fresh_repo_dir = fx3.fresh_repo_dir
init_repo = fx3.init_repo
commit_all = fx3.commit_all
stage_all = fx3.stage_all
run_check = fx3.run_check
run_check_via_hook = fx3.run_check_via_hook
build_into = fx3.build_into
make_part_source = fx3.make_part_source
make_multi_part_fixture = fx3.make_multi_part_fixture
fresh_disposable_repo = fx3.fresh_disposable_repo
build_disposable_commit_guardian = fx3.build_disposable_commit_guardian
run_check_in = fx3.run_check_in
extract_per_file_too_large_blocks = fx3.extract_per_file_too_large_blocks
block_for_suffix = fx3.block_for_suffix
PY_LIMIT = fx3.PY_LIMIT
SH_LIMIT = _CONFIG["file_size"]["line_limits"][".sh"]

_UNDECODABLE_BYTES = b"\xff\xfe\x00\x01not valid utf-8\n" * 5

# ---------------------------------------------------------------------------
# Reason-line extraction -- the SHAPE is fixed, the token's spelling is not.
# ---------------------------------------------------------------------------

_KNOWN_TOKENS = {"INDETERMINATE", "EMPTY HISTORY"}
_REASON_LINE_RE = re.compile(r"^\s*([A-Z][A-Z _-]*?):\s*reason=(.+?)\s*$", re.MULTILINE)


def find_could_not_describe_reason(block_text: str) -> str | None:
    """Return the reason text of a NEW could-not-describe token line in
    *block_text*, or None if absent.

    Deliberately excludes the two pre-existing tokens (``INDETERMINATE``,
    ``EMPTY HISTORY``) so this can never be satisfied by either of those
    already-shipped, differently-purposed lines.
    """
    for token, reason in _REASON_LINE_RE.findall(block_text):
        if token.strip() not in _KNOWN_TOKENS:
            return reason.strip()
    return None


def extract_indeterminate_reason(output: str) -> str | None:
    """Return INDETERMINATE's own reason text, or None if absent."""
    match = re.search(r"INDETERMINATE:\s*reason=(.+)", output)
    return match.group(1).strip() if match else None


# ---------------------------------------------------------------------------
# Staging -- undescribable and describable content, over and under limit.
# ---------------------------------------------------------------------------


def _garbled_python(n_lines: int) -> str:
    """Text guaranteed to raise SyntaxError under ast.parse, of exactly
    *n_lines* physical lines (no docstring/comment for count_content_lines
    to strip, so the file's measured length is exactly *n_lines*)."""
    return "\n".join(f"???garbled_syntax_line_{i:05d}(((" for i in range(n_lines)) + "\n"


def stage_unparseable_over_limit_py_file(root: Path, name: str = "unparseable_over.py") -> Path:
    """A .py file over PY_LIMIT whose content cannot be parsed at all --
    the "content that would not parse" cause."""
    target = root / name
    target.write_text(make_part_source("placeholder_stub", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit file")
    target.write_text(_garbled_python(PY_LIMIT + 60), encoding="utf-8")
    stage_all(root)
    return target


def stage_unparseable_under_limit_py_file(root: Path, name: str = "unparseable_under.py") -> Path:
    """The same unparseable content, but staged UNDER PY_LIMIT."""
    target = root / name
    target.write_text(make_part_source("placeholder_stub", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit file")
    target.write_text(_garbled_python(PY_LIMIT - 40), encoding="utf-8")
    stage_all(root)
    return target


def stage_no_extractor_over_limit_sh_file(root: Path, name: str = "no_extractor_over.sh") -> Path:
    """A .sh file over its own limit -- a covered kind with NO registered
    extractor at all, the "no extractor for the kind" cause, distinct from
    an extractor that ran and located nothing."""
    target = root / name
    target.write_text("\n".join(f"# line {i}" for i in range(10)) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit file")
    body = "\n".join(f"echo line_{i:05d}" for i in range(SH_LIMIT + 60))
    target.write_text(body + "\n", encoding="utf-8")
    stage_all(root)
    return target


def stage_under_half_py_file(root: Path, name: str = "under_half.py") -> Path:
    """A .py file over PY_LIMIT whose ONE located top-level part accounts for
    well under half its quoted length -- the "part set that cannot account
    for the quoted length" cause. The bulk of the file is module-level
    statements (no def/class), which extract_python_parts never locates."""
    target = root / name
    target.write_text(make_part_source("placeholder_stub", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit file")
    tiny_func = make_part_source("tiny_helper", 10)
    filler_count = PY_LIMIT + 50
    filler = "\n".join(f"module_level_var_{i:05d} = {i}" for i in range(filler_count))
    target.write_text(filler + "\n" + tiny_func + "\n", encoding="utf-8")
    stage_all(root)
    return target


def stage_describable_under_limit_py_file(root: Path, name: str = "describable_under.py") -> Path:
    """A small, cleanly-describable .py file that stands under PY_LIMIT."""
    target = root / name
    target.write_text(make_part_source("placeholder_stub", 5) + "\n", encoding="utf-8")
    commit_all(root, "establish file")
    content = make_multi_part_fixture([("alpha_helper", 20), ("beta_helper", 20)])
    target.write_text(content, encoding="utf-8")
    stage_all(root)
    return target


def stage_unmeasurable_length_py_file(root: Path, name: str = "unmeasurable.py") -> Path:
    """A staged .py file whose CURRENT content cannot be decoded as UTF-8 --
    triggers CurrentLengthUnmeasurableError (GE-127a-1-i's INDETERMINATE),
    for the vocabulary descriptor's second, length-unmeasurable arm."""
    target = root / name
    target.write_text(make_part_source("placeholder_stub", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit file")
    target.write_bytes(_UNDECODABLE_BYTES)
    stage_all(root)
    return target


# ---------------------------------------------------------------------------
# Disposable-copy mutations -- never touch templates/scripts/commit_guardian/
# ---------------------------------------------------------------------------

_VERDICT_INDEPENDENCE_PRELUDE = """
def main():  # noqa: F811 -- intentional test override
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    try:
        staged_files = get_staged_files()
    except PreviousLengthSourceError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return 2
    if not staged_files:
        return 0
    covered_files = {fp: is_new for fp, is_new in staged_files.items() if should_check_file(fp)}
    measured_kinds, unmeasured_kinds = _classify_staged_extensions(staged_files)
    previous_lengths, indeterminate_exit = _resolve_ratchet_or_indeterminate(list(covered_files))
    if indeterminate_exit is not None:
        return indeterminate_exit
    grown_files = []
    failed_files = []
    passed_files = []
    try:
        for filepath, is_new in covered_files.items():
            verdict, lines, reference = _classify_file(filepath, previous_lengths)
"""

_VERDICT_INDEPENDENCE_TAIL = """
            if verdict == "grew":
                grown_files.append((filepath, reference, lines))
            elif verdict == "too_large":
                failed_files.append((filepath, lines, reference))
            else:
                passed_files.append((filepath, lines, is_new))
    except CurrentLengthUnmeasurableError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return 2
    print("\\n\\U0001F4CF File Size Check\\n")
    _print_scope_declaration(measured_kinds, unmeasured_kinds)
    print(f"\\U0001F4CA Compared {len(previous_lengths)} file(s) against their previous length.\\n")
    for filepath, previous, lines in grown_files:
        _print_grown_file(filepath, previous, lines, get_limit_for_extension(filepath))
    for filepath, lines, limit in failed_files:
        _print_too_large_file(filepath, lines, limit)
    if passed_files:
        print(f"\\u2705 PASSED: {len(passed_files)} files checked")
        for filepath, lines, is_new in passed_files:
            status = "new" if is_new else "modified"
            print(f"   - {filepath} ({status}, {lines} lines - OK)")
    if grown_files or failed_files:
        return 1
    return 0
"""


def apply_verdict_independence_violation(dest: Path) -> None:
    """BA injection 1: a description failure downgrades an already-decided
    too_large/grew verdict to a clean pass, for the SAME file. Overrides
    main() wholesale on the disposable copy only -- the injection point is
    necessarily the classification loop, since that is where verdict and
    description meet; a print-only override cannot move the exit status.
    """
    body = (
        "            if verdict in (\"grew\", \"too_large\"):\n"
        "                content = _read_content_for_description(filepath)\n"
        "                description = describe_file(filepath, content, lines) if content is not None else None\n"
        "                if description is None:\n"
        "                    # TEST-INJECTED MUTATION (GE-127e-3-i, BA injection 1):\n"
        "                    # a description failure downgrades an already-decided\n"
        "                    # refusal to a clean pass.\n"
        "                    passed_files.append((filepath, lines, is_new))\n"
        "                    continue\n"
    )
    injected_code = _VERDICT_INDEPENDENCE_PRELUDE + body + _VERDICT_INDEPENDENCE_TAIL
    fx3._insert_before_main_guard(dest, injected_code)


def apply_refuse_any_describable_file_violation(dest: Path) -> None:
    """BA injection 3: refuse any file for which named parts could be
    produced, regardless of its measured length. Overrides main() wholesale
    on the disposable copy only."""
    body = (
        "            if verdict == \"pass\":\n"
        "                content = _read_content_for_description(filepath)\n"
        "                description = describe_file(filepath, content, lines) if content is not None else None\n"
        "                if description is not None:\n"
        "                    # TEST-INJECTED MUTATION (GE-127e-3-i, BA injection 3):\n"
        "                    # refuse any file for which named parts could be\n"
        "                    # produced, regardless of its measured length.\n"
        "                    failed_files.append((filepath, lines, get_limit_for_extension(filepath)))\n"
        "                    continue\n"
    )
    injected_code = _VERDICT_INDEPENDENCE_PRELUDE + body + _VERDICT_INDEPENDENCE_TAIL
    fx3._insert_before_main_guard(dest, injected_code)


def apply_substitute_advice_violation(dest: Path) -> None:
    """BA injection 2: when the description cannot be produced, fall back
    to a fixed sentence of general refactoring advice -- a print-only
    override of _print_file_description."""
    injected_code = (
        "def _print_file_description(filepath, quoted_length):  # noqa: F811 -- intentional test override\n"
        "    content = _read_content_for_description(filepath)\n"
        "    if content is None:\n"
        "        return\n"
        "    description = describe_file(filepath, content, quoted_length)\n"
        "    if description is None:\n"
        "        # TEST-INJECTED MUTATION (GE-127e-3-i, BA injection 2): a fixed\n"
        "        # sentence of general refactoring advice stands in for the\n"
        "        # missing description.\n"
        '        print("   General refactoring advice: consider extracting the largest")\n'
        '        print("   top-level definitions in this file into their own modules.")\n'
        "        return\n"
        "    for line in format_description_lines(description):\n"
        "        print(line)\n"
        "    print()\n"
    )
    fx3._insert_before_main_guard(dest, injected_code)
