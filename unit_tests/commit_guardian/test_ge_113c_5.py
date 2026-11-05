"""
MODULE: unit_tests/commit_guardian/test_ge_113c_5.py
GOAL: GE-113c-5 -- the decision-record cross-reference check
      (templates/scripts/commit_guardian/check_adr_cross_reference.py)
      inspects the staged records, the component registry and the
      decision-record folder of the project it guards, in every layout it
      ships in.
BUSINESS CONTEXT: The hook sets REPO_ROOT = Path(__file__).resolve().parents[2]
      and reads every staged path, docs/components.json and the ADR folder
      from it. From the installed .leafcutter/ copy (and from the templates/
      source copy) none of those exist, a missing ADR reads as empty
      frontmatter and the check reports nothing: it is inert. These tests are
      the code-aware test design of GE-113c-5, written exactly as its
      test_spec lists them.
ARCHITECTURE: Each test builds a real temporary git repository, writes the
      registry with json.dumps and the markdown frontmatter with
      yaml.safe_dump, stages real files and runs the hook as a subprocess;
      see _ge_113c_4_5_fixtures for the installed layout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

from _ge_113c_4_5_fixtures import (  # noqa: E402
    EMIT_MARKER,
    deploy_installed_copy,
    git_add,
    git_init,
    instrument_installed_check_outcome,
    output_of,
    result_lines,
    run_hook,
    source_copy,
    write_markdown,
)

HOOK = "check_adr_cross_reference.py"
ADR_STEM = "ADR-901-example"
ADR_REL = f"docs/architecture/adrs/{ADR_STEM}.md"
DETAIL_REL = "docs/architecture/components/commit-guardian.md"
DECOY_DETAIL_REL = "docs/architecture/components/decoy-commit-guardian.md"
REGISTRY_REL = "docs/components.json"
COULD_NOT_CHECK = "RESULT: could_not_check"


def _write_registry(root: Path, detail_ref: str = DETAIL_REL) -> None:
    path = root / REGISTRY_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    registry = {"components": {"commit_guardian": {"detail_ref": detail_ref}}}
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _write_detail(root: Path, rel: str = DETAIL_REL, *, mentions_adr: bool) -> None:
    body = "# Commit guardian\n\nThe pre-commit check runner.\n"
    if mentions_adr:
        body += f"\nConstrained by [{ADR_STEM}](../adrs/{ADR_STEM}.md).\n"
    write_markdown(root / rel, {"title": "Commit guardian"}, body)


def _write_adr(root: Path) -> None:
    write_markdown(
        root / ADR_REL,
        {"status": "accepted", "components": ["commit_guardian"]},
        "# ADR-901: Example decision\n\nAn example decision record.\n",
    )


def _repo_with_staged_adr(tmp_path: Path) -> Path:
    """Registry + detail doc without the back-link, and the ADR staged."""
    repo = tmp_path / "repo"
    git_init(repo)
    _write_registry(repo)
    _write_detail(repo, mentions_adr=False)
    _write_adr(repo)
    git_add(repo, ADR_REL)
    return repo


def _finding_lines(proc) -> list[str]:
    """The finding text lines naming the ADR, decoration stripped."""
    return [
        line.strip().lstrip("❌⚠️ ").strip()
        for line in output_of(proc).splitlines()
        if ADR_STEM in line
    ]


def _assert_strict_finding(proc, label: str) -> None:
    out = output_of(proc)
    assert proc.returncode == 1, f"{label}: expected exit 1 under --strict, got {proc.returncode}:\n{out}"
    assert ADR_STEM in out, f"{label}: finding does not name {ADR_STEM}:\n{out}"
    assert "back-link" in out.lower(), f"{label}: finding does not name the missing back-link:\n{out}"
    assert "warn" not in out.lower(), f"{label}: strict finding reported at WARNING severity:\n{out}"


def test_ge_113c_5_installed_copy_reports_missing_cross_reference_for_staged_adr(tmp_path):
    # covers: GE-113c-5
    # angle: reachability
    """The installed copy, run as pre-commit runs it (relative path, cwd at the
    repository root, --strict), refuses the staged ADR whose detail doc lacks
    the back-link, at ERROR severity."""
    repo = _repo_with_staged_adr(tmp_path)
    installed = deploy_installed_copy(repo, HOOK)

    proc = run_hook(installed, repo, "--strict")

    _assert_strict_finding(proc, "installed")
    assert DETAIL_REL in output_of(proc), f"the detail doc is not named:\n{output_of(proc)}"


def test_ge_113c_5_source_and_installed_copies_report_the_same_finding_at_the_strict_setting_severity(tmp_path):
    # covers: GE-113c-5
    # angle: criterion
    """Both copies print the same finding text: --strict exits 1 at ERROR
    severity; the default setting exits 0 and prints it as a WARNING."""
    repo = _repo_with_staged_adr(tmp_path)
    installed = deploy_installed_copy(repo, HOOK)

    strict_installed = run_hook(installed, repo, "--strict")
    strict_source = run_hook(source_copy(HOOK), repo, "--strict")
    _assert_strict_finding(strict_installed, "installed --strict")
    _assert_strict_finding(strict_source, "source --strict")
    assert _finding_lines(strict_installed) == _finding_lines(strict_source)

    warn_installed = run_hook(installed, repo)
    warn_source = run_hook(source_copy(HOOK), repo)
    for label, proc in (("installed", warn_installed), ("source", warn_source)):
        out = output_of(proc)
        assert proc.returncode == 0, f"{label} default setting: expected exit 0, got {proc.returncode}:\n{out}"
        assert ADR_STEM in out and "warning" in out.lower(), (
            f"{label} default setting: finding not printed as a WARNING:\n{out}"
        )
    assert _finding_lines(warn_installed) == _finding_lines(warn_source)
    assert _finding_lines(warn_installed) == _finding_lines(strict_installed)


def test_ge_113c_5_added_cross_reference_clears_the_finding_in_both_copies(tmp_path):
    # covers: GE-113c-5
    # angle: criterion
    """Once the detail doc mentions the ADR and is restaged, both copies exit 0
    with --strict and report no finding.

    Control first: both copies must report the missing back-link, so the
    later silence is the check judging a present link, not reading nothing.
    """
    repo = _repo_with_staged_adr(tmp_path)
    installed = deploy_installed_copy(repo, HOOK)
    copies = (installed, source_copy(HOOK))

    for hook in copies:
        _assert_strict_finding(run_hook(hook, repo, "--strict"), f"control {hook}")

    _write_detail(repo, mentions_adr=True)
    git_add(repo, DETAIL_REL)

    for hook in copies:
        proc = run_hook(hook, repo, "--strict")
        out = output_of(proc)
        assert proc.returncode == 0, f"{hook}: the added back-link did not clear the finding:\n{out}"
        assert "FIX:" not in out, f"{hook}: a finding is still reported:\n{out}"
        assert COULD_NOT_CHECK not in result_lines(proc)


def test_ge_113c_5_registry_and_adr_folder_are_read_from_the_resolved_project_root(tmp_path):
    # covers: GE-113c-5
    # angle: discrimination
    """The registry and the ADR folder come from the project root the shared
    resolver names, never from a folder computed from the hook's own file."""
    # Case 1: a decoy registry under .leafcutter/ (parents[2] of the installed
    # hook) points at a doc that already mentions the ADR; the decoy doc exists
    # at both roots, so reading the decoy registry yields no finding at all.
    repo = _repo_with_staged_adr(tmp_path / "decoy")
    installed = deploy_installed_copy(repo, HOOK)
    decoy_root = repo / ".leafcutter"
    _write_registry(decoy_root, detail_ref=DECOY_DETAIL_REL)
    for root in (repo, decoy_root):
        _write_detail(root, DECOY_DETAIL_REL, mentions_adr=True)

    proc = run_hook(installed, repo, "--strict")
    _assert_strict_finding(proc, "decoy registry")
    assert DETAIL_REL in output_of(proc), (
        f"the finding does not come from the root registry's detail doc:\n{output_of(proc)}"
    )

    # Case 2: only the detail doc (mention removed) is staged; the ADR exists
    # only in the project root's ADR folder, so only a root-based ADR index
    # finds it.
    repo2 = tmp_path / "reverse" / "repo"
    git_init(repo2)
    _write_registry(repo2)
    _write_adr(repo2)
    _write_detail(repo2, mentions_adr=False)
    git_add(repo2, DETAIL_REL)
    installed2 = deploy_installed_copy(repo2, HOOK)

    reverse = run_hook(installed2, repo2, "--strict")
    out = output_of(reverse)
    assert reverse.returncode == 1, f"reverse check: expected exit 1, got {reverse.returncode}:\n{out}"
    assert ADR_STEM in out and DETAIL_REL in out, (
        f"reverse check did not find {ADR_STEM} through the root ADR folder:\n{out}"
    )


def test_ge_113c_5_staged_adr_that_cannot_be_read_does_not_pass(tmp_path):
    # covers: GE-113c-5
    # angle: discrimination
    """A staged ADR whose working-tree copy is gone is not a pass, even at the
    default (non-strict) setting: the installed copy exits non-zero, names the
    unread path and prints 'RESULT: could_not_check' through
    check_outcome.emit_result -- never 'RESULT: ok'."""
    repo = _repo_with_staged_adr(tmp_path)
    (repo / ADR_REL).unlink()
    installed = deploy_installed_copy(repo, HOOK)

    proc = run_hook(installed, repo)
    out = output_of(proc)
    lines = result_lines(proc)
    assert proc.returncode != 0, f"an unread staged ADR passed (exit 0):\n{out}"
    assert COULD_NOT_CHECK in lines, f"no 'RESULT: could_not_check' line on stdout:\n{out}"
    assert "RESULT: ok" not in lines, f"an unread run reported 'RESULT: ok':\n{out}"
    assert ADR_STEM in out, f"the unread path is not named:\n{out}"

    instrument_installed_check_outcome(repo)
    traced = run_hook(installed, repo)
    assert f"{EMIT_MARKER} could_not_check" in (traced.stdout or ""), (
        "the could_not_check line was not printed through "
        f"check_outcome.emit_result(OUTCOME_COULD_NOT_CHECK):\n{output_of(traced)}"
    )


def test_ge_113c_5_nothing_staged_still_passes(tmp_path):
    # covers: GE-113c-5
    # angle: criterion
    """With no ADR or docs/ file in the staged scope, the installed copy exits 0
    and prints no could_not_check line (GE-120a-4's boundary)."""
    repo = tmp_path / "repo"
    git_init(repo)
    _write_registry(repo)
    (repo / "notes.txt").write_text("not a decision record\n", encoding="utf-8")
    git_add(repo, "notes.txt")
    installed = deploy_installed_copy(repo, HOOK)

    proc = run_hook(installed, repo, "--strict")

    assert proc.returncode == 0, f"empty scope did not pass:\n{output_of(proc)}"
    assert COULD_NOT_CHECK not in result_lines(proc), (
        f"empty scope reported could_not_check:\n{output_of(proc)}"
    )
