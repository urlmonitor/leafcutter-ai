"""
MODULE: test_acs_100i_7_i_pass_is_real
GOAL: Pin ACS-100i-7-i — prove that ACS-100i-7's headline result ("zero records
    refused on this rule") is a real pass and not an empty examination. The gate
    must still bite inside the whole-store pass, and a run that examined nothing
    must not be reported as success.
BUSINESS CONTEXT: KI-ACS-001. scripts/ac_store/validate_ac_schema.py used to take
    FILE paths and do no globbing; handed a bare directory it printed "No YAML
    files to validate." and exited 0 — a success-shaped result from a run that
    checked nothing. The store-wide sweep prescribed in CLAUDE.md was itself a
    no-op from 2026-08-10 to 2026-08-18 for exactly this reason. Without the last
    two tests below, "zero refusals" is indistinguishable from "validated
    nothing". Both halves are needed: an empty examination must fail loudly, AND
    a directory that holds records must actually be walked — a validator that
    simply refused every directory would satisfy the first half vacuously.
ARCHITECTURE: The "copy of the store into which one record has been added" is a
    logical copy — the real corpus's parsed records plus one record materialized
    on disk under pytest's tmp_path. The real store is never written to, and the
    added record is a genuine on-disk YAML file produced by the real serializer,
    so the by-file-path scenario has a real path to name.

AC: ACS-100i-7-i (docs/acceptance-criteria/ac-store/
    ACS-100-structured-requirements/ACS-100i-7-i.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acs_100i_support import (  # noqa: E402
    AC_STORE_DIR,
    SCHEMA_VALIDATOR_CLI,
    base_ac_record,
    run_cli,
    verdict,
    whole_store_pass,
    write_ac_yaml,
)


def _declaring_record() -> dict:
    """A record that declares a package surface and supplies a list-form spec."""
    return base_ac_record(
        id="ACS-998",
        title="Seeded record declaring a package surface with an unstructured spec",
        package_surface=True,
        it_requirements=["A list", "of requirement strings"],
    )


def test_whole_store_pass_refuses_exactly_the_seeded_declaring_record(tmp_path):
    # covers: ACS-100i-7-i
    """ACS-100i-7-i s1: given a copy of the store into which ONE record has been
    added carrying `package_surface: true` and list-form implementation
    requirements, the whole-store pass must refuse exactly one record ON THIS
    RULE — that one — and must name it by file path.

    Currently RED: today the same pass refuses 244 records on this rule (the 243
    undeclared build records the proxy trigger over-matches, plus this one,
    refused merely for carrying an unrecognised `package_surface` property).

    This is what makes ACS-100i-7's zero-refusal claim falsifiable: the gate
    must still bite inside the very pass that reports zero.

    Scoped to rule-attributed refusals, matching the 244 figure above. The
    unscoped reading — "the store has exactly one refusal of any kind" — cannot
    hold alongside ACS-100i-7 s2, which requires the 37 pre-existing unrelated
    refusals (playwright framework, absent `components`) to remain unchanged,
    file for file. Both readings cannot be satisfied at once, and those 37 are
    outside this change's scope. Attribution keeps the assertion discriminating:
    before the narrowing it is 244, not 1.
    """
    seeded_path = write_ac_yaml(tmp_path, "ACS-998.yaml", _declaring_record())
    seeded_doc = yaml.safe_load(seeded_path.read_text(encoding="utf-8"))

    refusals = whole_store_pass(extra={seeded_path: seeded_doc})

    refused_paths = sorted(
        str(p) for p, v in refusals.items() if v.refused_on_package_surface_rule
    )
    assert refused_paths == [str(seeded_path)], (
        "the whole-store pass must refuse exactly the seeded declaring record "
        f"on the package-surface rule and nothing else; it refused "
        f"{len(refused_paths)} records: "
        f"{[p for p in refused_paths if p != str(seeded_path)][:10]}"
    )
    assert refusals[seeded_path].refused_on_package_surface_rule, (
        "the seeded record must be refused BECAUSE it declared a package "
        "surface without a structured spec, not incidentally; messages: "
        f"{list(refusals[seeded_path].messages)}"
    )


def test_single_file_check_reproduces_the_whole_store_refusal(tmp_path):
    # covers: ACS-100i-7-i
    """ACS-100i-7-i s2: passing that one record to the validator by file path
    must refuse it with the same message the whole-store pass produced.

    Currently RED: the two verdicts already agree today, but only because both
    report the same incidental "additional properties are not allowed" error.
    The final assertion — that the shared refusal is attributable to the
    package-surface rule — is what fails, and is what makes this scenario mean
    "the gate bites the same way in both modes" rather than "both modes are
    equally broken".
    """
    seeded_path = write_ac_yaml(tmp_path, "ACS-998.yaml", _declaring_record())
    seeded_doc = yaml.safe_load(seeded_path.read_text(encoding="utf-8"))

    whole_store = whole_store_pass(extra={seeded_path: seeded_doc})[seeded_path]
    single_file = verdict(seeded_doc)
    cli = run_cli(SCHEMA_VALIDATOR_CLI, str(seeded_path))

    assert single_file.messages == whole_store.messages, (
        "validating the record on its own must produce the same refusal the "
        f"whole-store pass produced; single-file={list(single_file.messages)} "
        f"whole-store={list(whole_store.messages)}"
    )
    assert cli.returncode != 0, (
        f"the shipped CLI must refuse it too; exit={cli.returncode}\n{cli.output}"
    )
    assert str(seeded_path) in cli.output, (
        f"the refusal must name the record by file path; output:\n{cli.output}"
    )
    assert single_file.refused_on_package_surface_rule, (
        "the shared refusal must be attributable to the package-surface rule, "
        "otherwise both modes agree only on an incidental error; messages: "
        f"{list(single_file.messages)}"
    )


def test_empty_examination_is_not_reported_as_success(tmp_path):
    # covers: ACS-100i-7-i
    """ACS-100i-7-i s3: a run in which the validator examined no records must not
    report success — the empty examination is reported as such and is
    distinguishable from a pass.

    KI-ACS-001: the validator used to print "No YAML files to validate." and exit
    0, so CLAUDE.md's prescribed store-wide sweep silently checked nothing for
    eight days while reporting clean the whole time.

    A directory holding no AC YAML is the case that reaches the empty-examination
    branch now that a directory argument is walked recursively (see the companion
    test below). Both spellings of "nothing to check" are covered: a directory
    with no YAML at all, and a directory holding only non-YAML files.
    """
    empty_dir = tmp_path / "no-records-here"
    empty_dir.mkdir()
    (tmp_path / "decoys").mkdir()
    (tmp_path / "decoys" / "README.md").write_text("not an AC\n", encoding="utf-8")

    for target in (empty_dir, tmp_path / "decoys"):
        run = run_cli(SCHEMA_VALIDATOR_CLI, str(target))

        assert run.returncode != 0, (
            "a run that examined zero records must not exit 0; passing "
            f"{target} exited {run.returncode} with:\n{run.output}"
        )
        assert "OK:" not in run.output, (
            f"an empty examination must not be reported as a pass; output:\n{run.output}"
        )
        assert str(target) in run.output, (
            "the report must name what it was handed so the caller can see what "
            f"went unexamined; output:\n{run.output}"
        )


def test_a_directory_argument_actually_examines_the_records_under_it():
    # covers: ACS-100i-7-i
    """ACS-100i-7-i s3, the other half: the empty-examination report is only an
    honest answer when a directory that DOES hold records is genuinely walked.

    A validator that refused every directory would also satisfy "never reports a
    false pass" — vacuously, by never checking anything. This pins the behaviour
    that makes the guarantee worth having: handed the real store, the run reaches
    individual record files rather than reporting that it examined none.

    Deliberately asserts nothing about the exit code. The store carries
    pre-existing schema violations unrelated to this branch, and whether it is
    momentarily clean is not this test's subject — that records were EXAMINED is.
    """
    run = run_cli(SCHEMA_VALIDATOR_CLI, str(AC_STORE_DIR))

    assert "no AC YAML files were validated" not in run.output, (
        "the real store directory holds thousands of records, so a run over it "
        "that reports examining none is the KI-ACS-001 no-op regressing; "
        f"output:\n{run.output[:2000]}"
    )
    examined_a_record = ".yaml" in run.output or "OK: all " in run.output
    assert examined_a_record, (
        "the run must show it reached individual record files — either by naming "
        "a .yaml file or by reporting a count of files validated; output:\n"
        f"{run.output[:2000]}"
    )
