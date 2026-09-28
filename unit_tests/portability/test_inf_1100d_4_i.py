"""
MODULE: test_inf_1100d_4_i
AC: INF-1100d-4-i -- "The address check flags real-looking addresses, allows
    obvious placeholders, and leaves unshipped history alone"

GOAL: RED-baseline behavioral tests proving the not-yet-implemented
    shipped-address check CLI (contract documented in
    ``_inf_1100d_4_shipped_address_harness.py``, shared with
    ``test_inf_1100d_4.py``) sits on the correct side of every edge case
    this AC names: a bare host+port and both scheme spellings are flagged
    (S1/S2), placeholders/env-refs/setting-prose are not (S3-S6), a shipped
    ``templates/docs/`` history page is flagged exactly like any other
    shipped file until redacted (S7), and records outside the declared
    shipped roots -- an AC-store YAML and a page in leafcutter's own docs/
    tree -- are never scanned at all (the seam case).

SAME DETECTOR, SAME DECLARED ROOTS: this AC's own it_requirements says
    "Same detector and same declared shipped roots ... as INF-1100d-4. No
    second implementation." -- this file therefore invokes the identical
    CLI contract (``run_check`` / ``--source-root``) as
    ``test_inf_1100d_4.py``, never a second script or a different flag
    shape.

MUST_CATCH MAPPING (from this AC's own IT-PO enrichment notes):
    - "exclude history pages by path" ->
      ``test_address_check_flags_history_page_until_redacted``'s
      before-redaction half goes red if a path-based exemption exists.
    - "require user:password@" ->
      ``test_address_check_flags_bare_host_port_and_both_scheme_spellings``'s
      S1 half goes red if credentials are required to flag a match.
    - "flag any scheme://" ->
      ``test_address_check_allows_placeholders_env_refs_and_setting_prose``
      goes red if S3/S4 are ever flagged.
    - "scan the whole repo" ->
      ``test_address_check_ignores_ac_store_record_and_own_docs_page`` goes
      red if anything outside ``templates/``/``config/`` is scanned.

Per the coordinator's explicit instruction, each scenario gets its OWN test
    function (never ``self.subTest``).
"""
# @ac-tag: INF-1100d-4-i

from __future__ import annotations

from ._inf_1100d_4_shipped_address_harness import (
    build_address,
    check_output,
    old_shipped_address,
    finding_reported,
    run_check,
    scanned_file_count,
    write_shipped_file,
)


def test_address_check_flags_bare_host_port_and_both_scheme_spellings(tmp_path):
    # covers: INF-1100d-4-i
    # angle: reachability
    """AC-INF-1100d-4-i: S1 (a bare ``postgresql://host:port/db`` with no
    credentials) and S2 (the ``postgres://`` scheme spelling, with
    credentials) are each flagged with file and line.

    Invokes the shipped-address check CLI as a real subprocess over a temp
    shipped tree -- this AC's own ``surface_invoked`` for this entry.
    Catches the must_catch "require user:password@" (S1 has none) and
    proves both accepted scheme spellings are matched, not just one.
    """
    s1 = build_address("postgresql", "localhost", 5403, "LIVE")  # no credentials
    s2 = build_address("postgres", "127.0.0.1", 5432, "app", user="app", password="app")

    s1_file = write_shipped_file(tmp_path, "templates/agents/s1-bare-host-port.md", [s1])
    s2_file = write_shipped_file(tmp_path, "templates/agents/s2-postgres-scheme.md", [s2])

    result = run_check(source_root=tmp_path)

    assert result.returncode != 0, (
        "expected the check to flag S1 and/or S2; got returncode=0, "
        f"output={check_output(result)!r}"
    )
    output = check_output(result)
    assert finding_reported(output, s1_file.name, 1), (
        f"S1 (bare host+port, no credentials) must be flagged even without "
        f"a user:password@ prefix; output={output!r}"
    )
    assert finding_reported(output, s2_file.name, 1), (
        f"S2 (the 'postgres://' scheme spelling) must be flagged just like "
        f"'postgresql://'; output={output!r}"
    )


def test_address_check_allows_placeholders_env_refs_and_setting_prose(tmp_path):
    # covers: INF-1100d-4-i
    # angle: boundary
    """AC-INF-1100d-4-i: S3 (an angle-bracket placeholder), S4 (an ``${ENV}``
    reference), S5 (a ``{{config.*}}`` placeholder), and S6 (prose naming
    the setting) produce no findings.

    This is the POSITIVE-CONTROL half of the pair with
    ``test_address_check_flags_bare_host_port_and_both_scheme_spellings``:
    an over-broad "flag any scheme://" implementation (must_catch) would
    flag S3, and an over-broad "flag anything mentioning the setting"
    implementation would flag S6 -- this test's assertions on the exact
    scanned-file count (not merely a bare 'zero findings') would go red on
    a wrong-direction fix that also silently stopped scanning the file.
    """
    s3 = "postgresql://<user>:<password>@<host>:<port>/<database>"
    s4 = "${DB_CONNECTION_TEST}"
    s5 = "{{config.testing_context.db_connection_test}}"
    s6 = "set testing_context.db_connection_test to your test database's address"

    write_shipped_file(tmp_path, "templates/docs/allowed-forms.md", [s3, s4, s5, s6])

    result = run_check(source_root=tmp_path)

    assert result.returncode == 0, (
        "expected placeholders, env-refs, and setting-prose to produce no "
        f"findings; got returncode={result.returncode!r}, "
        f"output={check_output(result)!r}"
    )
    count = scanned_file_count(result.stdout)
    assert count is not None and count >= 1, (
        "a clean pass over a real shipped file must still report it was "
        f"scanned (never silently skipped); stdout={result.stdout!r}"
    )


def test_address_check_flags_history_page_until_redacted(tmp_path):
    # covers: INF-1100d-4-i
    # angle: criterion
    """AC-INF-1100d-4-i (S7): a shipped ``templates/docs/`` page quoting the
    old address as history is flagged exactly like any other shipped file
    -- no path-based exemption for "this is documentation" or "this is
    history" -- and the SAME file passes once the quote is replaced with
    the placeholder form.

    Both halves (before and after) run against the identical file path, so
    a check carrying any exclusion list keyed on ``templates/docs/`` would
    pass the before-half for the wrong reason (path excluded, not address
    absent) -- but that wrong reason is exactly what the before-half's
    non-zero-exit assertion rules out.
    """
    history_line_before = (
        f"Historically this shipped as {old_shipped_address()}, since fixed."
    )
    history_file = write_shipped_file(
        tmp_path, "templates/docs/history-of-the-address.md", [history_line_before]
    )

    before_result = run_check(source_root=tmp_path)
    assert before_result.returncode != 0, (
        "expected a templates/docs/ history page quoting the address to be "
        f"flagged like any other shipped file (no path exemption); "
        f"got returncode=0, output={check_output(before_result)!r}"
    )
    before_output = check_output(before_result)
    assert finding_reported(before_output, history_file.name, 1), (
        f"expected {history_file.name!r} to be named with line 1 before "
        f"redaction; output={before_output!r}"
    )

    redacted_placeholder = "postgresql://<user>:<password>@<host>:<port>/<database>"
    history_line_after = (
        f"Historically this shipped as {redacted_placeholder}, since fixed."
    )
    history_file.write_text(history_line_after + "\n", encoding="utf-8")

    after_result = run_check(source_root=tmp_path)
    assert after_result.returncode == 0, (
        "expected the same file to pass once the address is replaced with "
        f"the placeholder form; got returncode={after_result.returncode!r}, "
        f"output={check_output(after_result)!r}"
    )


def test_address_check_ignores_ac_store_record_and_own_docs_page(tmp_path):
    # covers: INF-1100d-4-i
    # angle: seam
    """AC-INF-1100d-4-i: run over a temp repository-shaped tree, the check
    reports neither an AC-store YAML nor a docs/analysis page that quotes
    the same address -- only ``templates/`` and ``config/`` are declared
    shipped, and there is no exclusion list.

    This pipes the check's own real ``--source-root`` scanning behaviour
    against a tree that ALSO contains a docs/ page and an AC-store record
    quoting the address outside the declared roots -- proving the omission
    follows from the positive root declaration (nothing outside
    ``templates/``/``config/`` is ever visited), not from a path-based
    exclusion list. Catches the must_catch "scan the whole repo": if the
    check ever widened its walk to the whole ``--source-root`` tree instead
    of just ``templates/`` + ``config/``, either unshipped record below
    would get flagged and this test would go red.
    """
    address = old_shipped_address()

    # A clean shipped tree -- nothing here should ever be flagged.
    write_shipped_file(
        tmp_path, "templates/agents/unrelated-agent.md", ["# An unrelated agent"]
    )
    write_shipped_file(tmp_path, "config/skills_config.default.json", ["{}"])

    # Two UNSHIPPED records quoting the address, both outside the declared
    # roots -- an AC-store YAML and a page in leafcutter's own docs/ tree.
    ac_store_file = write_shipped_file(
        tmp_path,
        "docs/acceptance-criteria/infrastructure/EXAMPLE-1.yaml",
        [
            "id: EXAMPLE-1",
            "notes: |",
            f"  Historically this shipped as {address}.",
        ],
    )
    docs_analysis_file = write_shipped_file(
        tmp_path,
        "docs/analysis/2026-09-25-example-history-page.md",
        [f"The old default was `{address}`."],
    )

    result = run_check(source_root=tmp_path)

    assert result.returncode == 0, (
        "expected a source-root scan to ignore records outside the "
        f"declared templates/ and config/ roots; got "
        f"returncode={result.returncode!r}, output={check_output(result)!r}"
    )
    output = check_output(result)
    assert ac_store_file.name not in output, (
        f"the AC-store record {ac_store_file.name!r} is outside the "
        f"declared shipped roots and must never be scanned or flagged; "
        f"output={output!r}"
    )
    assert docs_analysis_file.name not in output, (
        f"the docs/analysis page {docs_analysis_file.name!r} is outside "
        f"the declared shipped roots and must never be scanned or "
        f"flagged; output={output!r}"
    )
