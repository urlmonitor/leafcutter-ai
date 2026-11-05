"""
MODULE: test_acd_2500a_1_i
GOAL: Red-first specification of ACD-2500a-1-i: a rule check that examined zero
    requirement records does not pass (scripts/ac_store/requirement_rule_check.py).
BUSINESS CONTEXT: A misspelled feature-folder name or a README-only folder must not
    read as "all clear". The paired acceptable input (exactly 1 valid record passes
    with a stated count of 1) stops the rule being met by a check that fails
    everything.
ARCHITECTURE: Driven through `main(argv)` and, for the reachability test, a real
    subprocess of the script. The location is passed as an already repo-root-relative
    POSIX path so "the location it was given, unchanged" and "repo-root-relative
    POSIX" (architect note D7) agree.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    # The protected-fields family's 'not evaluated' entries (ACD-2500a-2-vi / -vii)
    # are not this file's subject; every other finding is kept.
    check_store_other_families as check_store,
    cli_argv,
    make_store,
    roots,
    run_cli_subprocess_other_families as run_cli_subprocess,
)


def test_misspelled_folder_is_failed_with_zero_count_and_location(tmp_path):
    # covers: ACD-2500a-1-i
    # angle: failure
    """A location resolving to 0 records is failed, states 0 records checked and
    names the location it was given, unchanged."""
    store = make_store(tmp_path, roots(1))
    misspelled = store.location.replace("rule-check-demo", "rule-chek-demo")

    exit_code, report = check_store(store, location=misspelled)

    assert report["verdict"] == "failed"
    assert report["records_checked"] == 0
    assert report["location"] == misspelled
    assert exit_code == 1


def test_readme_only_folder_is_failed(tmp_path):
    # covers: ACD-2500a-1-i
    # angle: failure
    """A folder holding only a README yields failed with 0 records checked."""
    store = make_store(tmp_path, [])
    store.write_text("README.md", "# Feature folder\n\nNo requirement records yet.\n")

    exit_code, report = check_store(store)

    assert report["verdict"] == "failed"
    assert report["records_checked"] == 0
    assert report["location"] == store.location
    assert exit_code == 1


def test_single_valid_record_passes_with_count_one(tmp_path):
    # covers: ACD-2500a-1-i
    # angle: boundary
    """The paired acceptable input: exactly 1 valid record passes, stating a count of 1."""
    store = make_store(tmp_path, roots(1))

    exit_code, report = check_store(store)

    assert report["verdict"] == "passed", report["findings"]
    assert report["records_checked"] == 1
    assert report["findings"] == []
    assert exit_code == 0


def test_acd_2500a_1_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-1-i
    # angle: reachability
    """Real CLI subprocess: zero records exits non-zero with verdict failed on stdout,
    and the one-valid-record run exits 0 -- the exit status is what plan-feature reads."""
    empty = make_store(tmp_path / "empty", [])
    one = make_store(tmp_path / "one", roots(1))

    empty_run = run_cli_subprocess(cli_argv(empty), cwd=empty.repo_root)
    one_run = run_cli_subprocess(cli_argv(one), cwd=one.repo_root)

    assert empty_run.exit_code == 1, empty_run.stderr
    assert empty_run.report["verdict"] == "failed"
    assert empty_run.report["records_checked"] == 0
    assert one_run.exit_code == 0, one_run.stderr
    assert one_run.report["verdict"] == "passed"
    assert one_run.report["records_checked"] == 1
