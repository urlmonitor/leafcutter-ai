"""
MODULE: test_inf_1100d_4
AC: INF-1100d-4 -- "The package refuses to ship a database address again"

GOAL: RED-baseline behavioral tests proving the not-yet-implemented
    shipped-address check CLI (contract documented in
    ``_inf_1100d_4_shipped_address_harness.py``) does what this AC's
    criteria demands: passes over the real shipped roots today's fix leaves
    clean, fails on the real pre-fix bytes naming every genuinely-affected
    file, flags a reintroduced address of either supported scheme, and
    accepts a build-output directory as a scan target.

WHY A CLI SUBPROCESS, NOT AN IN-PROCESS IMPORT: every test_spec entry for
    this AC names ``surface_invoked`` or otherwise treats "the shipped-
    address check" as a runnable command -- this is also the normal-suite
    entry point per this AC's own it_requirements ("Runs in the normal test
    suite ... in under 10 s"). ``run_check()`` invokes it as a real
    subprocess so a reachability regression (the check existing but not
    being wired to anything real) cannot hide behind an import.

GIT-VERIFIED DISCREPANCY IN THIS AC'S OWN CRITERIA TEXT: the criteria and
    notes name FIVE shipped files as carrying the address at the pinned
    pre-work commit ``e919a24f`` -- the two under ``templates/agents/``, the
    two under ``config/``, and ``templates/workflows/test.md``. Reading the
    real bytes of all five via ``git show e919a24f:<path>`` (verified both
    manually and by the assertion inside
    ``test_shipped_address_check_fails_on_pre_fix_sources_naming_every_file``
    below) shows ``templates/workflows/test.md`` contains no
    ``<scheme>://...`` address at that commit -- only unrelated
    "port 5403" prose, which does not match this AC's own detection rule
    (a scheme prefix is required). This test file therefore asserts
    per-file/per-line findings for the FOUR files that genuinely contain a
    matching address, and separately asserts (rather than silently
    omitting) that the check correctly finds nothing in ``test.md`` at that
    commit. Asserting a false "test.md is flagged" claim here would make
    this test permanently unable to go green even against a correct
    implementation, which is worse than a narrower, git-verified claim --
    see this AC's own Source-of-Truth Discipline. This discrepancy should
    be surfaced to the ticket/AC owner for a wording fix; it does not change
    what the check itself must do.

MUST_CATCH MAPPING (from this AC's own IT-PO enrichment notes):
    - "match only the one literal" -> the mysql-scheme half of
      ``test_shipped_address_check_flags_reintroduced_address_with_file_and_line``
      goes red if only the postgresql literal is matched.
    - "scan only templates/" -> the pre-fix test's assertions on the two
      ``config/`` files go red if ``config/`` is never scanned.
    - "zero-file scan exits 0" -> the ``scanned_file_count`` assertion in
      ``test_shipped_address_check_passes_on_current_shipped_roots`` goes
      red if a zero-file scan reports success.

Per the coordinator's explicit instruction, each scenario gets its OWN test
    function (never ``self.subTest``).
"""
# @ac-tag: INF-1100d-4

from __future__ import annotations

from ._inf_1100d_4_shipped_address_harness import (
    PRE_FIX_SHIPPED_FILES,
    build_address,
    check_output,
    deployed_agent_file,
    find_line_with_address,
    finding_reported,
    git_show,
    materialize_pre_fix_tree,
    old_shipped_address,
    run_check,
    scanned_file_count,
    write_shipped_file,
)


def test_shipped_address_check_passes_on_current_shipped_roots():
    # covers: INF-1100d-4
    # angle: reachability
    """AC-INF-1100d-4: over the real ``templates/`` and ``config/`` trees,
    the check exits 0 and reports a non-zero count of scanned files.

    Invokes the REAL production entry point (a subprocess over the
    not-yet-existing check CLI -- the normal-suite entry point per this
    AC's own it_requirements) and consumes both the exit code and the
    printed scanned-file count in assertions, not merely importing a
    module or checking a symbol exists.

    Currently RED because the check script does not exist yet (and, until
    INF-1100d-4's own dependencies INF-1100d-1/-2 land in this worktree,
    because the real shipped roots may still carry the address); either
    reason is a valid non-zero exit for a TDD red baseline.
    """
    result = run_check()

    assert result.returncode == 0, (
        "expected the shipped-address check to pass over the current "
        f"templates/ and config/ trees; argv failed with returncode="
        f"{result.returncode!r}, output={check_output(result)!r}"
    )

    count = scanned_file_count(result.stdout)
    assert count is not None and count > 0, (
        "a clean run must report a non-zero count of scanned shipped "
        f"files -- a scan that found zero files must not report success "
        f"(INF-1100d-4 it_requirements); stdout={result.stdout!r}"
    )


def test_shipped_address_check_fails_on_pre_fix_sources_naming_every_file(tmp_path):
    # covers: INF-1100d-4
    # angle: real_artifact
    """AC-INF-1100d-4: over a temp shipped tree holding the real pre-fix
    bytes of the shipped source files (materialised via ``git show
    e919a24f:<path>``, never a hand-typed reconstruction), the check exits
    non-zero and names each of the genuinely-affected files with the exact
    line number the address appears on in those real bytes.

    The pinned commit's real content for ``templates/workflows/test.md``
    contains no matching address (see this module's docstring) -- this is
    asserted explicitly below via ``find_line_with_address`` returning
    None, rather than silently omitted, so this fact stays verified against
    the real git object rather than merely claimed in a comment.
    """
    materialize_pre_fix_tree(tmp_path)

    address = old_shipped_address()
    expected_lines: dict[str, int] = {}
    for rel_path in PRE_FIX_SHIPPED_FILES:
        content = git_show(rel_path)
        line = find_line_with_address(content, address)
        if line is not None:
            expected_lines[rel_path] = line

    # Ground truth: exactly four of the five named files genuinely carry
    # the address at the pinned commit -- and test.md is not one of them.
    assert "templates/workflows/test.md" not in expected_lines, (
        "expected templates/workflows/test.md to carry no matching address "
        "at the pinned pre-fix commit; this repo's real git history "
        "changed underneath this test if it now does"
    )
    assert len(expected_lines) == 4, (
        f"expected exactly 4 of the 5 named pre-fix files to carry a "
        f"matching address; found {sorted(expected_lines)!r}"
    )

    result = run_check(source_root=tmp_path)

    assert result.returncode != 0, (
        "expected the check to fail over the real pre-fix bytes; "
        f"got returncode=0, output={check_output(result)!r}"
    )

    output = check_output(result)
    for rel_path, line in expected_lines.items():
        filename = rel_path.rsplit("/", 1)[-1]
        assert finding_reported(output, filename, line), (
            f"expected {filename!r} to be named with line {line} (where "
            f"the address appears in the real pre-fix bytes of "
            f"{rel_path!r}) in the check's output; output={output!r}"
        )


def test_shipped_address_check_flags_reintroduced_address_with_file_and_line(tmp_path):
    # covers: INF-1100d-4
    # angle: criterion
    """AC-INF-1100d-4: a template reintroducing the old postgresql address,
    and another reintroducing a mysql-scheme address, are each reported
    with file and line, with a non-zero exit.

    Two files, two schemes -- catches the must_catch "match only the one
    literal": a check that hardcodes just the postgresql example would
    leave the mysql file unflagged.
    """
    postgres_address = old_shipped_address()
    mysql_address = build_address("mysql", "h", 3306, "d", user="u", password="p")

    pg_file = write_shipped_file(
        tmp_path,
        "templates/agents/reintroduced-postgres.md",
        ["# Example agent", "Connect with:", postgres_address, "Done."],
    )
    mysql_file = write_shipped_file(
        tmp_path,
        "templates/agents/reintroduced-mysql.md",
        ["# Example agent", mysql_address, "Done."],
    )

    result = run_check(source_root=tmp_path)

    assert result.returncode != 0, (
        "expected the check to fail when a shipped template reintroduces "
        f"an address; got returncode=0, output={check_output(result)!r}"
    )

    output = check_output(result)
    assert finding_reported(output, pg_file.name, 3), (
        f"expected {pg_file.name!r} to be named with line 3 (the "
        f"postgresql address line); output={output!r}"
    )
    assert finding_reported(output, mysql_file.name, 2), (
        f"expected {mysql_file.name!r} to be named with line 2 (the "
        f"mysql address line) -- a check that matches only the postgresql "
        f"literal would miss this; output={output!r}"
    )


def test_shipped_address_check_scans_build_output_directory(tmp_path):
    # covers: INF-1100d-4
    # angle: deployed
    """AC-INF-1100d-4: pointed at a built-layout directory (a synthetic
    ``.leafcutter`` tree, per this AC's own it_requirements -- 'until then a
    synthetic built tree', never a real ``build.py`` subprocess run per
    CLAUDE.md), the check flags an address in a built agent file.
    """
    address = build_address("postgresql", "db.example.internal", 5403, "LIVE",
                             user="trader", password="trader")
    deployed_file = deployed_agent_file(tmp_path, f"Connect with: {address}")

    result = run_check(build_root=tmp_path)

    assert result.returncode != 0, (
        "expected the check to flag an address inside a built-output "
        f"directory; got returncode=0, output={check_output(result)!r}"
    )
    output = check_output(result)
    assert finding_reported(output, deployed_file.name, 2), (
        f"expected {deployed_file.name!r} to be named with line 2 (the "
        f"address line) when scanning a build-output directory; "
        f"output={output!r}"
    )
