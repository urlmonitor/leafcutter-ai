"""
MODULE: test_bp_900g_8_v_frontmatter_reuse
GOAL: Pin BP-900g-8-v, -vi and -vii: template_compiler.parse_frontmatter reuses
    the parse of a frontmatter text it has already parsed, returns exactly what
    the reference pure-Python parse returns, and keeps yaml.SafeLoader.
BUSINESS CONTEXT: A fresh-consumer build called parse_frontmatter 1,606 times
    over 176 distinct texts, about half of the build's CPU time. The libyaml
    loader was rejected (it accepts a tab next to a colon, which yaml.SafeLoader
    rejects), so the saving comes from parsing each distinct text once.

CONTRACT FOR THE CODER:
    * ``template_compiler._parsed_frontmatter(fm_text)`` is a
      ``functools.lru_cache``-wrapped function returning the parsed mapping for a
      frontmatter text; it exposes ``cache_clear`` and ``cache_info``.
    * ``template_compiler._FRONTMATTER_CACHE_SIZE`` is its finite bound.
    * ``parse_frontmatter`` returns a deep copy of the stored parse each call.

RED BEFORE THE FIX: the loader-count tests fail by assertion (one load per call),
    the bound test fails by absence of the memo, and the loader-class and
    equality tests are the guard rails that must stay green.
"""

from __future__ import annotations

import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import template_compiler as _tc  # noqa: E402 -- after sys.path setup
import yaml  # noqa: E402

_REAL_LOAD = yaml.load

_EDGE_CASES = {
    "date_and_int_and_bool": "---\nwhen: 2026-11-16\ncount: 7\nflag: true\nname: x\n---\nbody\n",
    "quoted_strings": "---\na: 'single: quoted'\nb: \"double # quoted\"\nc: '123'\n---\nbody\n",
    "multiline_scalars": (
        "---\ndescription: |\n  line one\n  line two\nfolded: >\n  a\n  b\nlist:\n  - one\n  - two\n---\nbody\n"
    ),
    "empty_frontmatter": "---\n---\nbody\n",
    "malformed_yaml": "---\nkey: [unclosed\n  other: : :\n---\nbody\n",
    "tab_after_colon": "---\na:\t1\nb: 2\n---\nbody\n",
    "tab_after_comma": "---\na: [1,\t2]\n---\nbody\n",
    "non_mapping_scalar": "---\njust a string\n---\nbody\n",
    "non_mapping_list": "---\n- a\n- b\n---\nbody\n",
    "no_frontmatter": "# Title\n\nbody only\n",
    "unterminated": "---\na: 1\nno closing marker\n",
    "anchors_share_objects": "---\nbase: &b [1, 2]\nother: *b\n---\nbody\n",
}


def _reference_parse(text: str):
    """The pre-change computation: parse_frontmatter's splitting plus a direct SafeLoader load."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    try:
        fm = yaml.load(fm_text, Loader=yaml.SafeLoader) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def _canon(value):
    """Order- and type-preserving canonical form, so == cannot hide a reordering or int/bool/date swap."""
    if isinstance(value, dict):
        return ("dict", tuple((_canon(k), _canon(v)) for k, v in value.items()))
    if isinstance(value, list):
        return ("list", tuple(_canon(v) for v in value))
    return (type(value).__name__, value)


def _clear_memo() -> None:
    memo = getattr(_tc, "_parsed_frontmatter", None)
    if memo is not None:
        memo.cache_clear()


def _real_template_texts() -> list[tuple[str, str]]:
    out = []
    for path in sorted((_REPO_ROOT / "templates").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):
            out.append((str(path.relative_to(_REPO_ROOT)), text))
    return out


class _LoadRecorder:
    """Wrap yaml.load, recording the Loader class and the text of every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, type]] = []

    def __call__(self, stream, Loader=None):  # noqa: N803 -- mirrors yaml.load's keyword
        self.calls.append((stream, Loader))
        return _REAL_LOAD(stream, Loader=Loader)


class TestFrontmatterEqualsReference(unittest.TestCase):
    def setUp(self) -> None:
        _clear_memo()

    # covers: BP-900g-8-v
    def test_every_real_template_frontmatter_equals_the_reference_parse(self) -> None:
        texts = _real_template_texts()
        self.assertGreater(len(texts), 50, "expected many real templates with frontmatter")
        non_empty = 0
        for name, text in texts:
            ref_fm, ref_body = _reference_parse(text)
            non_empty += bool(ref_fm)
            for attempt in ("first", "second"):
                fm, body = _tc.parse_frontmatter(text)
                self.assertEqual(_canon(fm), _canon(ref_fm), f"{name}: {attempt} parse differs")
                self.assertEqual(body, ref_body, f"{name}: {attempt} body differs")
        self.assertGreater(non_empty, 50, "real templates must actually yield frontmatter")

    # covers: BP-900g-8-v
    def test_synthetic_edge_cases_match_the_reference_and_survive_caller_mutation(self) -> None:
        for name, text in _EDGE_CASES.items():
            ref_fm, ref_body = _reference_parse(text)
            first_fm, first_body = _tc.parse_frontmatter(text)
            self.assertEqual(_canon(first_fm), _canon(ref_fm), name)
            self.assertEqual(first_body, ref_body, name)
            self._mutate(first_fm)
            second_fm, second_body = _tc.parse_frontmatter(text)
            self.assertEqual(_canon(second_fm), _canon(ref_fm), f"{name}: mutation leaked into a later parse")
            self.assertEqual(second_body, ref_body, name)
        self.assertEqual(_tc.parse_frontmatter(_EDGE_CASES["malformed_yaml"])[0], {})
        self.assertEqual(_tc.parse_frontmatter(_EDGE_CASES["empty_frontmatter"])[0], {})

    @staticmethod
    def _mutate(fm) -> None:
        if isinstance(fm, dict):
            fm["__injected__"] = True
            for value in list(fm.values()):
                if isinstance(value, list):
                    value.append("__injected__")
        elif isinstance(fm, list):
            fm.append("__injected__")

    # covers: BP-900g-8-v
    def test_parse_returns_independent_copies_of_a_shared_text(self) -> None:
        text = _EDGE_CASES["multiline_scalars"]
        first, _ = _tc.parse_frontmatter(text)
        second, _ = _tc.parse_frontmatter(text)
        self.assertIsNot(first, second)
        self.assertIsNot(first["list"], second["list"])
        self.assertEqual(copy.deepcopy(first), second)


class TestLoaderInvocations(unittest.TestCase):
    def setUp(self) -> None:
        _clear_memo()

    def _record(self):
        recorder = _LoadRecorder()
        return recorder, mock.patch.object(_tc.yaml, "load", side_effect=recorder)

    # covers: BP-900g-8-vi
    def test_repeated_text_invokes_the_loader_once(self) -> None:
        text = _EDGE_CASES["date_and_int_and_bool"]
        recorder, patch = self._record()
        with patch:
            for _ in range(20):
                _tc.parse_frontmatter(text)
        self.assertEqual(len(recorder.calls), 1, "twenty parses of one text must load once")

    # covers: BP-900g-8-vi
    def test_distinct_texts_are_each_loaded_and_never_cross_answered(self) -> None:
        recorder, patch = self._record()
        with patch:
            a1, _ = _tc.parse_frontmatter("---\nname: alpha\n---\nb")
            b1, _ = _tc.parse_frontmatter("---\nname: alphb\n---\nb")
            a2, _ = _tc.parse_frontmatter("---\nname: alpha\n---\nb")
            same_fm_other_body, _ = _tc.parse_frontmatter("---\nname: alpha\n---\nanother body")
        self.assertEqual(len(recorder.calls), 2, "two distinct frontmatter texts, two loads")
        self.assertEqual((a1["name"], b1["name"], a2["name"]), ("alpha", "alphb", "alpha"))
        self.assertEqual(same_fm_other_body["name"], "alpha")

    # covers: BP-900g-8-vi
    def test_failed_parse_is_also_loaded_once(self) -> None:
        text = _EDGE_CASES["malformed_yaml"]
        recorder, patch = self._record()
        with patch:
            results = [_tc.parse_frontmatter(text)[0] for _ in range(5)]
        self.assertEqual(results, [{}] * 5)
        self.assertEqual(len(recorder.calls), 1)

    # covers: BP-900g-8-vi
    def test_reuse_is_in_memory_only_and_bounded(self) -> None:
        bound = getattr(_tc, "_FRONTMATTER_CACHE_SIZE", None)
        self.assertIsInstance(bound, int, "the memo must declare a finite size bound")
        # assertIsInstance does not narrow for mypy; repeat its check so `bound` is an int below.
        assert isinstance(bound, int)
        self.assertGreater(bound, 0)
        memo = _tc._parsed_frontmatter
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with mock.patch.object(tempfile, "tempdir", tmp):
                    for i in range(bound + 50):
                        _tc.parse_frontmatter(f"---\nname: n{i}\n---\nbody")
                leftovers = os.listdir(tmp)
            finally:
                os.chdir(old_cwd)
        self.assertEqual(leftovers, [], "parsing must not write anything to disk")
        self.assertLessEqual(memo.cache_info().currsize, bound)
        self.assertEqual(memo.cache_info().maxsize, bound)


class TestLoaderClass(unittest.TestCase):
    def setUp(self) -> None:
        _clear_memo()

    # covers: BP-900g-8-vii
    def test_parse_frontmatter_uses_the_pure_python_safe_loader(self) -> None:
        recorder = _LoadRecorder()
        with mock.patch.object(_tc.yaml, "load", side_effect=recorder):
            for text in _EDGE_CASES.values():
                _tc.parse_frontmatter(text)
        self.assertTrue(recorder.calls, "the loader must have been exercised")
        for _, loader in recorder.calls:
            self.assertIs(loader, yaml.SafeLoader)
            self.assertIsNot(loader, getattr(yaml, "CSafeLoader", object()))

    # covers: BP-900g-8-vii
    def test_tab_adjacent_to_colon_or_comma_still_gives_empty_frontmatter(self) -> None:
        for name in ("tab_after_colon", "tab_after_comma"):
            text = _EDGE_CASES[name]
            for attempt in ("first", "second"):
                fm, body = _tc.parse_frontmatter(text)
                self.assertEqual(fm, {}, f"{name}: {attempt} parse must be empty")
                self.assertEqual(body, "body\n")


if __name__ == "__main__":
    unittest.main()
