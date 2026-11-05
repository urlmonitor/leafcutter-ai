"""
MODULE: unit_tests/commit_guardian/test_ge_113c_4.py
GOAL: GE-113c-4 -- the architecture parent-link check
      (templates/scripts/commit_guardian/check_mermaid_parent_link.py)
      inspects the staged documents in every layout it ships in, and refuses
      a broken parent link.
BUSINESS CONTEXT: The hook sets REPO_ROOT = Path(__file__).resolve().parents[2]
      -- templates/ for the source copy, .leafcutter/ for the installed copy
      -- and joins every staged path and every declared parent to it. Neither
      copy ever finds the staged documents, so it passes everything
      (KI-CG-20261016-mermaid-parent-link-root-inside-package). These tests
      are the code-aware test design of GE-113c-4, written exactly as its
      test_spec lists them.
ARCHITECTURE: Each test builds a real temporary git repository, stages real
      fixture documents (frontmatter via yaml.safe_dump) and runs the hook as
      a subprocess; see _ge_113c_4_5_fixtures for the installed layout.
"""
from __future__ import annotations

import shutil
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

HOOK = "check_mermaid_parent_link.py"
DIAGRAMS = "docs/architecture/diagrams"
CHILD_REL = f"{DIAGRAMS}/c2-901-example.md"
PARENT_REL = f"{DIAGRAMS}/c1-901-parent.md"
CHILD_NAME = "c2-901-example.md"
PARENT_NAME = "c1-901-parent.md"
COULD_NOT_CHECK = "RESULT: could_not_check"


def _write_child(root: Path) -> None:
    body = (
        "# Example container\n\n"
        "```mermaid\nC4Container\n  title Example\n```\n\n"
        f"Parent: [{PARENT_NAME}]({PARENT_NAME})\n"
    )
    write_markdown(
        root / CHILD_REL,
        {"flight_level": "L2", "parent": PARENT_REL},
        body,
    )


def _write_parent(root: Path, *, lists_child: bool) -> None:
    children = [f"{DIAGRAMS}/c2-902-sibling.md"]
    if lists_child:
        children.append(CHILD_REL)
    body = "# Parent context\n\n```mermaid\nC4Context\n  title Parent\n```\n"
    write_markdown(
        root / PARENT_REL,
        {"flight_level": "L1", "root": True, "children": children},
        body,
    )


def _broken_repo(tmp_path: Path) -> Path:
    """A git repository staging the child and a parent that omits it."""
    repo = tmp_path / "repo"
    git_init(repo)
    _write_child(repo)
    _write_parent(repo, lists_child=False)
    git_add(repo, CHILD_REL, PARENT_REL)
    return repo


def _assert_refused_naming_both(proc) -> None:
    out = output_of(proc)
    assert proc.returncode == 1, f"expected exit 1 (refusal), got {proc.returncode}:\n{out}"
    assert CHILD_NAME in out, f"refusal does not name {CHILD_NAME}:\n{out}"
    assert PARENT_NAME in out, f"refusal does not name {PARENT_NAME}:\n{out}"
    assert "children" in out, f"refusal does not name the missing children entry:\n{out}"


def test_ge_113c_4_installed_copy_refuses_broken_parent_link_naming_both_documents(tmp_path):
    # covers: GE-113c-4
    # angle: reachability
    """The installed copy, run the way .pre-commit-config.yaml runs it (cwd at the
    repository root, relative script path), refuses the staged broken link."""
    repo = _broken_repo(tmp_path)
    installed = deploy_installed_copy(repo, HOOK)

    proc = run_hook(installed, repo)

    _assert_refused_naming_both(proc)


def test_ge_113c_4_source_copy_refuses_broken_parent_link_naming_both_documents(tmp_path):
    # covers: GE-113c-4
    # angle: criterion
    """The package source copy, run with cwd at the temporary repository,
    refuses the same staged broken link with the same named documents."""
    repo = _broken_repo(tmp_path)

    proc = run_hook(source_copy(HOOK), repo)

    _assert_refused_naming_both(proc)


def test_ge_113c_4_corrected_parent_passes_from_both_copies(tmp_path):
    # covers: GE-113c-4
    # angle: criterion
    """Once the parent lists the child and is restaged, both copies exit 0.

    Control first: the broken fixture must be refused by both copies, so the
    later pass is the check judging a correct link, not the check reading
    nothing.
    """
    repo = _broken_repo(tmp_path)
    installed = deploy_installed_copy(repo, HOOK)
    copies = (installed, source_copy(HOOK))

    for hook in copies:
        broken = run_hook(hook, repo)
        assert broken.returncode == 1, (
            f"control: {hook} did not refuse the broken link:\n{output_of(broken)}"
        )

    _write_parent(repo, lists_child=True)
    git_add(repo, PARENT_REL)

    for hook in copies:
        fixed = run_hook(hook, repo)
        assert fixed.returncode == 0, (
            f"{hook} did not pass the corrected link:\n{output_of(fixed)}"
        )
        assert COULD_NOT_CHECK not in result_lines(fixed)


def test_ge_113c_4_installed_copy_reads_staged_documents_from_the_resolved_project_root(tmp_path):
    # covers: GE-113c-4
    # angle: discrimination
    """The installed copy reads the staged documents and the declared parent from
    the project root the shared resolver names, never from cwd or from a folder
    computed from its own file.

    A decoy copy of both documents with a VALID link sits under .leafcutter/
    (where parents[2] of the installed hook points); a hook that reads the
    child or the parent there would pass. The run from docs/ catches a root
    taken from cwd: that hook would read nothing (pass, or could_not_check).
    """
    repo = _broken_repo(tmp_path)
    installed = deploy_installed_copy(repo, HOOK)
    decoy_root = repo / ".leafcutter"
    _write_child(decoy_root)
    _write_parent(decoy_root, lists_child=True)

    from_root = run_hook(installed, repo)
    from_docs = run_hook(repo / installed, repo / "docs")

    for label, proc in (("cwd=root", from_root), ("cwd=docs/", from_docs)):
        out = output_of(proc)
        assert proc.returncode == 1, f"{label}: expected refusal, got {proc.returncode}:\n{out}"
        assert CHILD_NAME in out and PARENT_NAME in out and "children" in out, (
            f"{label}: refusal does not name both documents and the children entry:\n{out}"
        )
        assert COULD_NOT_CHECK not in result_lines(proc), (
            f"{label}: the staged documents were not read from the project root:\n{out}"
        )


def test_ge_113c_4_staged_document_that_cannot_be_read_does_not_pass(tmp_path):
    # covers: GE-113c-4
    # angle: discrimination
    """A staged architecture document whose working-tree copy is gone is not a
    pass: the installed copy exits non-zero, names the unread path and prints
    'RESULT: could_not_check' through check_outcome.emit_result -- never
    'RESULT: ok', and never a literal minted inside the hook."""
    repo = tmp_path / "repo"
    git_init(repo)
    _write_child(repo)
    git_add(repo, CHILD_REL)
    (repo / CHILD_REL).unlink()
    installed = deploy_installed_copy(repo, HOOK)

    proc = run_hook(installed, repo)
    out = output_of(proc)
    lines = result_lines(proc)
    assert proc.returncode != 0, f"an unread staged document passed (exit 0):\n{out}"
    assert COULD_NOT_CHECK in lines, f"no 'RESULT: could_not_check' line on stdout:\n{out}"
    assert "RESULT: ok" not in lines, f"an unread run reported 'RESULT: ok':\n{out}"
    assert CHILD_NAME in out, f"the unread path is not named:\n{out}"

    instrument_installed_check_outcome(repo)
    traced = run_hook(installed, repo)
    assert f"{EMIT_MARKER} could_not_check" in (traced.stdout or ""), (
        "the could_not_check line was not printed through "
        f"check_outcome.emit_result(OUTCOME_COULD_NOT_CHECK):\n{output_of(traced)}"
    )


def test_ge_113c_4_nothing_staged_still_passes(tmp_path):
    # covers: GE-113c-4
    # angle: criterion
    """With no architecture document in the staged scope, the installed copy
    exits 0 and prints no could_not_check line (GE-120a-4's boundary)."""
    repo = tmp_path / "repo"
    git_init(repo)
    (repo / "notes.txt").write_text("not an architecture document\n", encoding="utf-8")
    git_add(repo, "notes.txt")
    installed = deploy_installed_copy(repo, HOOK)

    proc = run_hook(installed, repo)

    assert proc.returncode == 0, f"empty scope did not pass:\n{output_of(proc)}"
    assert COULD_NOT_CHECK not in result_lines(proc), (
        f"empty scope reported could_not_check:\n{output_of(proc)}"
    )


def test_ge_113c_4_installed_copy_alone_refuses_without_a_source_tree(tmp_path):
    # covers: GE-113c-4
    # angle: reachability
    """The temporary repository holds only the installed copy -- no templates/
    tree -- so the refusal can only come from the installed copy."""
    repo = _broken_repo(tmp_path)
    installed = deploy_installed_copy(repo, HOOK)
    shutil.rmtree(repo / "templates", ignore_errors=True)
    assert not (repo / "templates").exists()

    proc = run_hook(installed, repo)

    _assert_refused_naming_both(proc)
