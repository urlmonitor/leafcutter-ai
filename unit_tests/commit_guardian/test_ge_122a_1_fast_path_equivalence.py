"""
MODULE: unit_tests/commit_guardian/test_ge_122a_1_fast_path_equivalence.py
GOAL: Differential-equivalence and collision-level regression tests for the
    YAML id-reading fast path in
    templates/scripts/commit_guardian/_uniqueness_scanners.py
    (`_fast_scan_top_level_id`, exercised through the public `_read_yaml_id`).

WHY A SIBLING FILE, NOT test_ge_122a_1.py: that file is already 1037 lines
    covering the whole-collection pass end-to-end (contested/repaired
    fixtures, deployed-layout invocation, hook registration, wall-clock
    performance budget). This module owns exactly one additional, narrower
    concern -- whether the fast id-reading path agrees with a full YAML
    parse on every id shape -- so it is kept separate rather than pushed
    further past that file's existing size, per this ticket's own
    instruction to prefer a sibling module when the primary file is large.

THE BUG (found by pr-reviewer, introduced in commit 2c6b99d6): commit
    2c6b99d6 added `_fast_scan_top_level_id` as a fast path ahead of
    yaml.safe_load in `_read_yaml_id`, to avoid running a full YAML parse
    over ~3100 files just to read one field. It is documented as bailing to
    None -- falling back to a full parse -- on any shape it cannot prove
    equivalent. Verified empirically (see the probe run captured in this
    ticket's sign-off comment) that it is NOT equivalent for several YAML
    tokens PyYAML's safe_load coerces:

        id value      _read_yaml_id (fast path wins)   full yaml.safe_load
        null          'null'                            None
        ~             '~'                               None
        true          'true'                             True
        false         'false'                            False
        yes           'yes'                               True
        no            'no'                                False
        on            'on'                                True
        off           'off'                               False
        007           '007'                               7
        1_000         '1_000'                             1000
        0x1F          '0x1F'                              31
        GE-100<TAB>X  'GE-100\\tX' (accepted as an id)     ScannerError (no
                                                            usable claim)

BUSINESS CONTEXT: this module is a COLLISION DETECTOR
    (check_identifier_uniqueness.run_uniqueness_pass). Two records whose ids
    resolve to the SAME string under YAML collide. If the fast path resolves
    an id differently from what a full parse would produce, two records that
    YAML considers identical -- one declaring `no`, another declaring
    `False` -- look like two DIFFERENT ids to the fast path, and the
    collision this whole GE-122 epic exists to catch is silently MISSED. A
    false green in a duplicate detector is the exact failure this epic
    exists to prevent (see EPIC-GE122UniquenessPassAndRepair/Master_Plan.md).

WHY IT WAS INVISIBLE: the fast path and yaml.safe_load agree over all 3092
    real on-disk AC files (mismatches=0) -- no real record in this store
    happens to use these coercion-sensitive shapes, so a real-artifact check
    could not structurally find this by construction. The wall-clock
    performance fixture added alongside the fast path (see
    TestUniquenessPassPerformanceBudget in test_ge_122a_1.py) only plants
    clean `GE-PERF-<i>` ids, which never exercise a coercion-sensitive
    shape either. Both stayed green.

FIXTURE AUTHENTICITY (per docs/reference/fixture-policy.md): where a shape
    CAN be produced by the real serializer (`yaml.safe_dump`), this module
    writes it that way and reads it back -- e.g. null/true/false/quoted
    strings, all of which round-trip byte-identically through safe_dump's
    default representer. Where a shape CANNOT be produced by safe_dump --
    the YAML-1.1 yes/no/on/off bool spellings (safe_dump's bool
    representer only ever emits true/false), the leading-zero/underscore/hex
    int spellings (safe_dump of an int emits its canonical decimal form,
    never the source spelling), a double-quoted string (safe_dump's default
    representer only ever emits single quotes), an embedded raw tab, a
    duplicate top-level key (impossible to express via a single Python
    dict, whose keys are unique by construction), a UTF-8 BOM, CRLF line
    endings, or trailing whitespace after a value -- this module writes the
    exact bytes directly. Each such case's inline comment states explicitly
    why safe_dump cannot emit it, precisely so a later reader does not
    mistake a legitimate raw write here for the hand-typed-fixture
    antipattern this repo bans elsewhere (EPIC-PhantomDoneFilesTouched): the
    file's raw byte content IS the thing under test in these cases, not a
    stand-in for a value a real serializer would have produced identically.

DECISION HISTORY
- 2026-08-19 [GE-122a-1/test-writer, bug-fix regression]: Initial authoring
  of the differential-equivalence table (TestFastPathAgreesWithFullParse)
  and the collision-level regression test
  (TestFastPathDivergenceHidesARealCollision), per pr-reviewer's finding
  above. Verified against
  templates/scripts/commit_guardian/_uniqueness_scanners.py as it stands
  today (commit 2c6b99d6 and later): see the test-writer sign-off comment
  for the exact RED/PASS split observed per case.
"""

from __future__ import annotations

import importlib
import importlib.util as _ilu
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

# ---------------------------------------------------------------------------
# Canonical paths -- templates/scripts/commit_guardian/ is the source of
# truth (ADR-001: template-is-canonical, .leafcutter/ is a build output).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_SCANNERS_PATH = _COMMIT_GUARDIAN_DIR / "_uniqueness_scanners.py"
_ENTRY_PATH = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"

_NS_AC = "acceptance-criteria"


def _ensure_commit_guardian_on_sys_path() -> None:
    """Insert templates/scripts/commit_guardian/ onto sys.path, once.

    Required because _uniqueness_scanners.py and check_identifier_uniqueness.py
    both use plain top-level sibling imports (``from _uniqueness_types import
    ...``) rather than package-relative imports, mirroring the sys.path
    bootstrap check_identifier_uniqueness.py performs on itself.
    """
    commit_guardian_dir = str(_COMMIT_GUARDIAN_DIR)
    if commit_guardian_dir not in sys.path:
        sys.path.insert(0, commit_guardian_dir)


def _load_scanners_module():
    """Import _uniqueness_scanners.py (the module under test) by real name.

    Returns:
        The imported module, or None if the canonical file is missing.
    """
    if not _SCANNERS_PATH.exists():
        return None
    _ensure_commit_guardian_on_sys_path()
    return importlib.import_module("_uniqueness_scanners")


def _load_entry_module():
    """Dynamically import check_identifier_uniqueness.py under a PRIVATE
    sys.modules key, isolated from any copy test_ge_122a_1.py (or any other
    sibling test file loaded earlier in the same pytest session) may already
    have registered under the plain 'check_identifier_uniqueness' name --
    both are the same on-disk file, but importing under a distinct key
    avoids this module's collision-level test depending on load order with
    respect to other test files in this directory.

    Returns:
        The imported module, or None if the canonical file is missing.
    """
    if not _ENTRY_PATH.exists():
        return None
    _ensure_commit_guardian_on_sys_path()
    spec = _ilu.spec_from_file_location("_ge122a1_fastpath_entry", _ENTRY_PATH)
    mod = _ilu.module_from_spec(spec)
    sys.modules["_ge122a1_fastpath_entry"] = mod
    spec.loader.exec_module(mod)
    return mod


_scanners = _load_scanners_module()
_entry = _load_entry_module()


def _require_scanners(test_case: unittest.TestCase) -> None:
    if _scanners is None:
        test_case.fail(f"_uniqueness_scanners.py not found at canonical path {_SCANNERS_PATH}.")


def _require_entry(test_case: unittest.TestCase) -> None:
    if _entry is None:
        test_case.fail(f"check_identifier_uniqueness.py not found at canonical path {_ENTRY_PATH}.")


# ---------------------------------------------------------------------------
# Independent oracle -- deliberately does NOT call into
# _uniqueness_scanners._parse_yaml_dict (part of the production fallback
# path itself); a shared bug between the oracle and the code under test
# would hide from this comparison. Reads the file the same way _read_yaml_id
# does (utf-8 text) and runs yaml.safe_load directly.
# ---------------------------------------------------------------------------


def _oracle_full_parse_id(path: Path) -> tuple[str | None, str | None]:
    """Independently compute the id a full ``yaml.safe_load`` of `path`
    would produce, using the SAME coercion `_read_yaml_id`'s own full-parse
    fallback applies (``str(data.get("id", "")).strip() or None``).

    Args:
        path: The on-disk fixture file to read and parse.

    Returns:
        A ``(resolved_id_or_None, raise_note_or_None)`` pair. When
        yaml.safe_load itself raises, the resolved id is None (a document
        that does not parse contributes no usable claim -- this is the
        correct behaviour per the bug report, not merely a placeholder) and
        `raise_note` carries a human-readable description of the raise for
        the assertion failure message.
    """
    content = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return None, f"yaml.safe_load raised {type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, None
    record_id = str(data.get("id", "")).strip()
    return (record_id or None), None


# ---------------------------------------------------------------------------
# Fixture writers
# ---------------------------------------------------------------------------


def _write_dumped(path: Path, id_value) -> None:
    """Write an id fixture via the REAL serializer (yaml.safe_dump).

    Use this whenever the shape under test is something safe_dump's default
    representer can reproduce byte-identically -- e.g. None/True/False, or a
    plain/quoted string. Per docs/reference/fixture-policy.md's Fixture
    Authenticity Rule, a hand-typed YAML literal is rejected wherever the
    real serializer can produce the exact same bytes.

    Args:
        path: Destination file path.
        id_value: The Python value to serialize under the top-level ``id``
            key.
    """
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump({"id": id_value}, fh, sort_keys=False)


def _write_dumped_nested(path: Path, data: dict) -> None:
    """Write an arbitrary structured fixture via yaml.safe_dump.

    Args:
        path: Destination file path.
        data: The full document to serialize.
    """
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _write_raw(path: Path, content: str) -> None:
    """Write raw text bytes directly -- legitimate ONLY when the exact
    source-text spelling (not a serialized Python value) is itself the
    thing under test; see each case's `note` below for the specific reason
    yaml.safe_dump cannot emit that shape.

    Args:
        path: Destination file path.
        content: Exact file content to write.
    """
    path.write_text(content, encoding="utf-8")


def _write_raw_bytes(path: Path, content: bytes) -> None:
    """Write raw bytes directly (bypassing text-mode newline translation) --
    used only for the BOM and CRLF cases, where the on-disk byte sequence
    itself (not a decoded string) is the thing under test.

    Args:
        path: Destination file path.
        content: Exact file bytes to write.
    """
    path.write_bytes(content)


# ---------------------------------------------------------------------------
# The differential-equivalence case table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Case:
    """One id-shape case for the differential-equivalence table.

    Attributes:
        name: Short identifier, used as both the subTest label and the
            fixture file stem.
        writer: Callable that writes the fixture file for this case.
        note: Explanation of why a raw write was required for this shape
            (safe_dump cannot emit it), or None when the case is written via
            the real serializer (safe_dump round-trip).
    """

    name: str
    writer: Callable[[Path], None]
    note: str | None


_CASES: list[_Case] = [
    # --- coercion cases: YAML tokens PyYAML's safe_load coerces to a
    # non-string Python value, which the fast path's plain-text scan cannot
    # know to reproduce. ---
    _Case("null_bare", lambda p: _write_dumped(p, None), None),
    _Case(
        "tilde_null",
        lambda p: _write_raw(p, "id: ~\n"),
        "safe_dump's None representer only ever emits the word 'null', "
        "never the '~' spelling -- raw needed to test this exact token.",
    ),
    _Case("true_bare", lambda p: _write_dumped(p, True), None),
    _Case("false_bare", lambda p: _write_dumped(p, False), None),
    _Case(
        "yes_bare",
        lambda p: _write_raw(p, "id: yes\n"),
        "safe_dump's bool representer only ever emits true/false -- the "
        "YAML-1.1 yes/no/on/off spellings cannot be produced by dumping "
        "a Python bool.",
    ),
    _Case(
        "no_bare",
        lambda p: _write_raw(p, "id: no\n"),
        "see yes_bare -- safe_dump never emits 'no' for False.",
    ),
    _Case(
        "on_bare",
        lambda p: _write_raw(p, "id: on\n"),
        "see yes_bare -- safe_dump never emits 'on' for True.",
    ),
    _Case(
        "off_bare",
        lambda p: _write_raw(p, "id: off\n"),
        "see yes_bare -- safe_dump never emits 'off' for False.",
    ),
    _Case(
        "octal_007",
        lambda p: _write_raw(p, "id: 007\n"),
        "safe_dump of the int 7 emits '7'; the leading-zero source "
        "spelling '007' is exactly the shape under test and cannot be "
        "produced by dumping any Python int.",
    ),
    _Case(
        "underscore_1000",
        lambda p: _write_raw(p, "id: 1_000\n"),
        "safe_dump of the int 1000 emits '1000'; the underscore-grouped "
        "source spelling cannot be produced by dumping a Python int.",
    ),
    _Case(
        "hex_0x1F",
        lambda p: _write_raw(p, "id: 0x1F\n"),
        "safe_dump of the int 31 emits '31'; the hex source spelling "
        "cannot be produced by dumping a Python int.",
    ),
    _Case(
        "exp_1e3",
        lambda p: _write_dumped(p, "1e3"),
        None,
    ),  # regression anchor: PyYAML's float resolver requires a decimal
    # point, so '1e3' is NOT resolved as a number by safe_load either --
    # dumping the Python STRING "1e3" round-trips byte-identically.
    # --- quoted forms that must survive as literal strings ---
    _Case("quoted_single_007", lambda p: _write_dumped(p, "007"), None),
    _Case(
        "quoted_double_null",
        lambda p: _write_raw(p, 'id: "null"\n'),
        "safe_dump's default representer only ever emits single-quoted "
        "scalars; a literal DOUBLE-quoted spelling requires a raw write "
        "to exercise that exact token.",
    ),
    _Case("quoted_single_true", lambda p: _write_dumped(p, "true"), None),
    # --- regression anchors: shapes already believed safe ---
    _Case("plain_GE100", lambda p: _write_dumped(p, "GE-100"), None),
    _Case(
        "quoted_single_GE100",
        lambda p: _write_raw(p, "id: 'GE-100'\n"),
        "forcing safe_dump to quote only the id VALUE (not also the 'id' "
        "KEY) requires a custom representer; a raw write preserves the "
        "real shape actually seen in hand-edited store files -- a quoted "
        "value, plain key -- without also quoting the key, which would "
        "stop the fast path's literal 'id:' prefix match from firing at "
        "all and defeat the point of this case.",
    ),
    # --- the case that makes safe_load RAISE: both paths must agree there
    # is no usable claim, never that the fast path invents one. ---
    _Case(
        "tab_in_value",
        lambda p: _write_raw_bytes(p, b"id: GE-100\tX\n"),
        "the raw TAB byte embedded in the scalar is the exact thing under "
        "test; yaml.safe_dump has no way to emit a document a full YAML "
        "parse cannot itself parse.",
    ),
    # --- shapes exercising fast-scan's own line-handling rules ---
    _Case(
        "duplicate_top_level_id",
        lambda p: _write_raw_bytes(p, b"id: GE-100\nid: GE-200\n"),
        "a duplicate top-level key cannot be expressed by dumping a "
        "single Python dict (dict keys are unique by construction); raw "
        "bytes are the only way to construct this malformed-but-parseable "
        "shape. PyYAML's own last-value-wins behaviour is the reference "
        "this fast path claims to match.",
    ),
    _Case(
        "id_nested_under_another_key",
        lambda p: _write_dumped_nested(p, {"meta": {"id": "GE-999"}}),
        None,
    ),  # must NOT be read as a top-level claim -- no `id:` line at column 0
    _Case(
        "utf8_bom",
        lambda p: _write_raw_bytes(p, b"\xef\xbb\xbfid: GE-100\ntitle: bom fixture\n"),
        "a byte-order-mark is inherently a raw byte-level artifact -- "
        "yaml.safe_dump has no parameter to prepend one.",
    ),
    _Case(
        "crlf_line_endings",
        lambda p: _write_raw_bytes(p, b"id: GE-100\r\ntitle: crlf fixture\r\n"),
        "yaml.safe_dump always emits '\\n'-only output -- CRLF line "
        "endings are a raw byte-level artifact of the file itself, which "
        "is exactly the shape under test (a file saved on Windows, or by "
        "a tool that preserves the repo's checked-in line endings).",
    ),
    _Case(
        "trailing_whitespace_after_value",
        lambda p: _write_raw_bytes(p, b"id: GE-100   \ntitle: trailing ws\n"),
        "safe_dump never emits trailing whitespace after a scalar value; "
        "this exercises a hand-edited file's accidental trailing spaces.",
    ),
]


# ---------------------------------------------------------------------------
# Differential equivalence: _read_yaml_id vs. a full yaml.safe_load
# ---------------------------------------------------------------------------


class TestFastPathAgreesWithFullParse(unittest.TestCase):
    """Table-driven differential-equivalence test.

    For every id shape in _CASES, `_read_yaml_id` (the real function
    scan_acceptance_criteria calls on every on-disk AC file) must return
    EXACTLY what an independent full yaml.safe_load of the same on-disk
    file produces. Uses subTest so every shape reports its own pass/fail
    independently -- the first mismatch must never mask the rest.
    """

    def setUp(self) -> None:
        _require_scanners(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_read_yaml_id_matches_full_yaml_safe_load_for_every_shape(self):
        # covers: GE-122a-1
        """AC-1 (bug-fix regression): `_read_yaml_id`'s fast path must never
        resolve an id differently from what a full YAML parse of the same
        file would produce -- a divergence here is exactly how a real
        collision (two records that YAML considers identical) goes
        undetected.

        EXPECTED SPLIT (see this file's module docstring / the test-writer
        sign-off comment for the exact captured run): the coercion cases
        (null, ~, true, false, yes, no, on, off, 007, 1_000, 0x1F) and the
        tab-in-value raise case are RED today -- `_read_yaml_id` returns the
        fast path's literal, unparsed text where a full parse would return
        a different Python-coerced value (or, for the tab case, no usable
        claim at all). The quoted forms, the plain/quoted 'GE-100'
        regression anchors, `1e3`, the duplicate-key case, the nested-id
        case, the BOM case, the CRLF case, and the trailing-whitespace case
        are expected to already PASS -- they are regression anchors, not
        red targets; a correct fix must not break them.
        """
        for case in _CASES:
            with self.subTest(case=case.name):
                path = self.root / f"{case.name}.yaml"
                case.writer(path)

                actual = _scanners._read_yaml_id(path)
                expected, raise_note = _oracle_full_parse_id(path)

                msg = (
                    f"case={case.name!r}: _read_yaml_id(path) returned {actual!r}, "
                    f"but a full yaml.safe_load of the same file produces {expected!r}."
                )
                if raise_note:
                    msg += f" ({raise_note})"
                if case.note:
                    msg += f" [raw-write rationale: {case.note}]"

                self.assertEqual(actual, expected, msg=msg)


# ---------------------------------------------------------------------------
# Collision-level regression: the actual harm, not just the unit mismatch
# ---------------------------------------------------------------------------


class TestFastPathDivergenceHidesARealCollision(unittest.TestCase):
    """test_fast_path_divergence_hides_a_real_collision.

    The unit-level equivalence check above is not the whole risk: this test
    expresses the actual harm the bug report names. Two on-disk AC records
    declare ids ('no' and 'False') that YAML resolves to the SAME boolean
    value (False) -- a genuine collision under the collision detector's own
    stated contract ("two records whose ids resolve to the same string
    collide"). But the fast path treats 'no' and 'False' as two DIFFERENT
    literal strings, so today's `run_uniqueness_pass` reports no collision
    at all over this fixture.
    """

    def setUp(self) -> None:
        _require_entry(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_fast_path_divergence_hides_a_real_collision(self):
        # covers: GE-122a-1
        """AC-1 (bug-fix regression, collision level): build a minimal
        on-disk acceptance-criteria namespace with two records --
        `id: no` and `id: False` -- written as RAW text (yaml.safe_dump's
        bool representer only ever emits lowercase 'true'/'false', never
        the capitalized 'False' or the YAML-1.1 'no' spelling, so neither
        of these exact source tokens can be produced by the real
        serializer; the literal spelling is itself the thing under test).
        Both resolve to Python `False` under a full YAML parse -- str(False)
        == 'False' for both -- so a correct pass must report exactly ONE
        finding naming BOTH claimant paths.

        FAILS TODAY: `_read_yaml_id`'s fast path returns the literal
        strings 'no' and 'False' respectively (never falling back to a full
        parse, since both shapes are ones the fast path believes it can
        resolve unambiguously), so `run_uniqueness_pass` sees two DIFFERENT
        claimed ids and reports no collision in this namespace at all.
        """
        ac_root = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        path_no = ac_root / "collision-a-no.yaml"
        path_false = ac_root / "collision-b-false.yaml"
        path_no.parent.mkdir(parents=True, exist_ok=True)
        path_no.write_text("id: no\ntitle: Collision claimant A, declares 'no'\nlevel: L2\n", encoding="utf-8")
        path_false.write_text(
            "id: False\ntitle: Collision claimant B, declares 'False'\nlevel: L2\n", encoding="utf-8"
        )

        verdict = _entry.run_uniqueness_pass(self.root)

        self.assertFalse(
            verdict.passed,
            msg=(
                "Two records declaring 'no' and 'False' resolve to the SAME "
                "YAML value (False) and must collide; the whole-collection "
                "verdict incorrectly passed."
            ),
        )
        self.assertIn(_NS_AC, verdict.namespaces, msg="Verdict is missing the acceptance-criteria namespace entirely.")
        ac_verdict = verdict.namespaces[_NS_AC]
        self.assertFalse(
            ac_verdict.passed,
            msg="The acceptance-criteria namespace must fail: 'no' and 'False' are the same id under YAML.",
        )
        self.assertEqual(
            len(ac_verdict.findings),
            1,
            msg=(
                f"Expected exactly one finding for the 'no'/'False' collision, "
                f"got {len(ac_verdict.findings)}: {ac_verdict.findings}."
            ),
        )
        finding = ac_verdict.findings[0]
        self.assertEqual(
            str(finding.number),
            "False",
            msg=(
                f"The contested number must be the canonical value a full YAML "
                f"parse produces (str(False) == 'False'), got {finding.number!r}."
            ),
        )
        actual_paths = {Path(p).resolve() if not Path(p).is_absolute() else Path(p) for p in finding.paths}
        actual_paths = {p if p.is_absolute() else (self.root / p).resolve() for p in actual_paths}
        expected_paths = {path_no.resolve(), path_false.resolve()}
        self.assertEqual(
            actual_paths,
            expected_paths,
            msg=(
                f"Finding must name BOTH claimant paths. Expected {expected_paths}, "
                f"got {actual_paths}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
