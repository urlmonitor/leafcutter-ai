"""
MODULE: unit_tests/build_orchestration/test_tq500g3i_review_modlevel.py
GOAL: Review-fix tests (H-1, H-2) for consumer_sweep.py check: module-level code that is not a def,
    class or plain name assignment is compared too, and control characters in a file do not shift
    the compared segments.
BUSINESS CONTEXT: Real scratch git repos, real record and check CLIs.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3i_review_fixtures as rfx

_T = "def test_a():\n    assert 1 == 1\n"
_MOD_CASES = {
    "skip_call": ("import pytest\n\n\n" + _T, "import pytest\n\npytest.skip('x', allow_module_level=True)\n\n\n" + _T),
    "import_changed": ("from a import b\n\n\n" + _T, "from fake import b\n\n\n" + _T),
    "pytestmark_aug": ("import pytest\n\npytestmark = []\n\n\n" + _T,
                       "import pytest\n\npytestmark = []\npytestmark += [pytest.mark.skip]\n\n\n" + _T),
    "tuple_assign": ("A, B = 1, 2\n\n\n" + _T, "A, B = 5, 2\n\n\n" + _T),
    "test_in_if": ("import sys\n\nif sys.platform != 'x':\n\n    def test_p():\n        assert 1 == 1\n",
                   "import sys\n\nif sys.platform != 'x':\n\n    def test_p():\n        assert 2 == 2\n"),
    "fixture_in_try": ("import pytest\n\ntry:\n\n    @pytest.fixture\n    def fx_t():\n        return 1\n"
                       "except ImportError:\n    pass\n",
                       "import pytest\n\ntry:\n\n    @pytest.fixture\n    def fx_t():\n        return 2\n"
                       "except ImportError:\n    pass\n"),
    "environ_added": ("import os\n\n\n" + _T, "import os\n\nos.environ['X'] = '1'\n\n\n" + _T),
}


@pytest.mark.parametrize("case", sorted(_MOD_CASES))
def test_h1_module_level_code_edit_is_unlisted_then_recorded(tmp_path: Path, case: str):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: only def / class / plain Name assignment compared, other module-level code ignored
    base_src, now_src = _MOD_CASES[case]
    ast.parse(base_src), ast.parse(now_src)
    repo = rfx.with_base(tmp_path, fx.REFRESH, base_src, now_src)
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and out["reason"] == "sweep list missing", (case, out)  # no list recorded yet (AC reason)
    assert out["unlisted"] and all(i["file"] == fx.REFRESH for i in out["unlisted"]), (case, out["unlisted"])
    # Recording the symbols the check reported excuses the edit (the pass is not vacuous).
    fx.recorded(repo, [fx.entry(i["file"], i["test"]) for i in out["unlisted"]], fx.W2_KEY)
    proc2, out2 = fx.check(repo)
    fx.assert_check_shape(proc2, out2)
    assert out2["passed"] is True and out2["unlisted"] == [], (case, out2)


@pytest.mark.parametrize("ctl", ["\x0c", "\x1c"], ids=["form_feed", "file_separator"])
def test_h2_control_char_before_test_does_not_hide_last_line_edit(tmp_path: Path, ctl: str):
    # covers: TQ-500g-3-i
    # angle: discrimination
    # must_catch: segments cut with str.splitlines(), so a form feed shifts every later line number
    head = f"# page{ctl}\n\n\ndef test_t():\n    a = 1\n    assert a == 1\n"
    now = head.replace("assert a == 1", "assert a == 2")
    ast.parse(head), ast.parse(now)
    repo = rfx.with_base(tmp_path, fx.REFRESH, head, now)
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False, (repr(ctl), out)
    assert (fx.REFRESH, "test_t") in fx.pairs(out["unlisted"]), (repr(ctl), out["unlisted"])
