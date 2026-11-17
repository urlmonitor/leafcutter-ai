"""
MODULE: unit_tests/ac_store/_rule_check_fixtures.py
GOAL: Shared fixture construction and real-CLI invocation helpers for the
    requirement rule check test family (test_acd_2500a_*.py in
    unit_tests/ac_store/ and unit_tests/ac_driven_dev/rule_check/).
BUSINESS CONTEXT: ACD-2500a-1 introduces scripts/ac_store/requirement_rule_check.py,
    a fail-closed rule check that plan-feature runs after every authoring stage.
    Tickets 06-17 (ACD-2500a-1 .. ACD-2500a-3-ii) all drive it the same way, so the
    store/record/CLI plumbing lives here once instead of being re-implemented per
    test file (precedent: _declared_files_fixtures.py, _acs_100i_fixtures.py).
ARCHITECTURE: Records are written with the REAL serializer (yaml.safe_dump), never
    as hand-typed YAML literals (Fixture Authenticity Rule); the one deliberate
    exception is `unreadable_record_text()`, whose whole point is malformed bytes.
    Every store is built under a tmp root laid out like a real consumer repo:

        <tmp>/docs/acceptance-criteria/<component>/<feature>/<ID>.yaml
        <tmp>/docs/acceptance-criteria/index.yaml        (verbatim copy)
        <tmp>/docs/components.json                       (verbatim copy)
        <tmp>/config/ac_store_schema.json                (verbatim copy)

    so a rule-source test can edit the TMP copies and point the check at them via
    --schema / --components-registry / --surface-map. The shipped files are never
    modified. The check's own `--repo-root` is always the tmp root (the check's
    inference falls back to the cwd otherwise, which would silently change where
    declared-files existence is judged: architect note, section 2).

PUBLIC API (what the other rule-check test writers build on):

    valid_record(record_id, **overrides) -> dict
        A fully schema-valid requirement record. It declares files with
        `to_be_created` entries, so the declared-files seam has nothing to report
        and no `not evaluated` finding appears (architect note D2): a test that
        asserts "exactly N findings" can therefore count literally. `overrides`
        replace/extend any field; pass `field=None` through `drop=` to remove one.

    hierarchy(prefix="ACD-9990", children=2, *, l1=None, child=None) -> list[dict]
        A COHERENT L0 -> L1 -> L2 chain with correct parent/child links, so the
        back-link family finds nothing to say. children=2 gives the 4-record folder
        of ACD-2500a-1's example: <prefix> (L0), <prefix>a (L1), <prefix>a-1,
        <prefix>a-2 (L2). `l1` / `child` are per-record overrides: `l1` is a dict
        applied to the L1; `child` maps a 1-based child index to a dict of
        overrides, e.g. child={2: {"expects_from": {...}}}.

    roots(count, prefix="ACD-99") -> list[dict]
        `count` independent root (L0) records ACD-99?0.., with no parent at all.

    make_store(tmp_path, records, *, component_dir="ac-driven-dev",
               feature="rule-check-demo") -> Store
        Writes the layout above. `records` may be empty (the folder still exists).

    Store: .repo_root (Path), .folder (Path), .location (repo-root-relative POSIX
        str, the value to pass to --location), .rel(id_or_name) (repo-root-relative
        POSIX path of a record file), .path(id) (absolute Path), .schema,
        .registry, .index (tmp copies), .read(id) (parsed dict),
        .write(record) (add/overwrite a record), .snapshot_path (before-state file).

    cli_argv(store, *extra, stage="ba", location=None) -> list[str]
        `--location <store.location> --repo-root <tmp> --stage <stage>` plus a
        `--before-snapshot` file freshly built from the records currently on disk
        (before-state == current state, so the readiness family has nothing to
        restore). Pass `readiness_before={id: value}` via `write_snapshot()` and
        your own `--before-snapshot` in `extra` to simulate a raised readiness.

    write_snapshot(store, overrides=None) -> Path
        (Re)writes store.snapshot_path as {id: readiness} from disk, then applies
        `overrides` ({id: value|None}); returns the path.

    run_cli(argv, cwd=None) -> (exit_code, report_dict)
        Calls requirement_rule_check.main(argv) IN PROCESS with stdout captured
        and cwd switched to `cwd` (use store.repo_root for relative --location).
        Fails the test loudly if stdout is not exactly one JSON document.

    run_cli_subprocess(argv, cwd=None) -> CliRun
        The same through `python scripts/ac_store/requirement_rule_check.py` in a
        real subprocess: .exit_code, .report, .stdout, .stderr. Use for the
        `# angle: reachability` tests.

    check_store(store, *extra, stage="ba") -> (exit_code, report_dict)
        cli_argv + run_cli with cwd = store.repo_root. The usual one-liner.

    findings_for(report, record_id=None, rule_family=None) -> list[dict]
    snapshot_tree(folder) -> dict[str, bytes]      (byte-identity assertions)

    other_families(report) -> dict
    check_store_other_families(...) / run_cli_subprocess_other_families(...)
        The report without the "protected fields" family's `not evaluated` entries
        (ACD-2500a-2-vi / -vii list every record so under a readiness-only snapshot
        and at stages the owner map does not list). For tests written before that
        family that assert ANOTHER family's exact findings; every other finding,
        including any protected-fields blocker, is kept.
    BLOCKERS: the dispositions that fail a verdict.

FAMILY NAMES (canonical strings from the architect note, section 3): constants
    FAMILY_* below; they are the report's `rule_family` values.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts" / "ac_store"
CLI_SCRIPT = SCRIPTS_DIR / "requirement_rule_check.py"

FAMILY_BACKLINKS = "parent-to-child back-links"
FAMILY_COMPONENTS = "non-empty graph component list"
FAMILY_READINESS = "readiness never raised to approved by an authoring agent"
FAMILY_CONTRACTS = "producer/consumer contract symmetry"
FAMILY_DOC_TRIGGERS = "documentation trigger to documentation requirement mapping"
FAMILY_RECORD_SCHEMA = "record schema"
FAMILY_RECORD_READABLE = "record readable"
FAMILY_TEST_INTENT = "test intent coverage"
FIVE_FAMILIES = (
    FAMILY_BACKLINKS,
    FAMILY_COMPONENTS,
    FAMILY_READINESS,
    FAMILY_CONTRACTS,
    FAMILY_DOC_TRIGGERS,
)

DISPOSITION_FIXED = "fixed"
DISPOSITION_DECISION = "needs a decision"
DISPOSITION_FAILED = "failed"
DISPOSITION_NOT_EVALUATED = "not evaluated"
BLOCKERS = (DISPOSITION_DECISION, DISPOSITION_FAILED)

_DEFAULT_COMPONENT_DIR = "ac-driven-dev"
_DEFAULT_FEATURE = "rule-check-demo"
_LEVELS = ("L0", "L1", "L2", "L3")


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------
def valid_record(record_id: str, *, drop: tuple[str, ...] = (), **overrides: Any) -> dict:
    """Return a fully schema-valid requirement record for `record_id`.

    Declares one `to_be_created` file (a path that cannot exist in any repo), so no
    declared-files existence report and no `not evaluated` noise is produced.
    """
    slug = record_id.lower().replace("-", "_")
    record: dict[str, Any] = {
        "id": record_id,
        "components": ["ac_driven_dev"],
        "readiness": "draft",
        "priority": "medium",
        "title": f"Fixture requirement {record_id}",
        "component": "ac-driven-dev",
        "level": "L2",
        "status": "active",
        "req_status": "draft",
        "work_status": "todo",
        "criteria": (
            "Given a fixture record,\nWhen the rule check runs,\n"
            "Then it is a valid requirement.\n"
        ),
        "depends_on": [],
        "covered_by": [],
        "implemented_by": [],
        "assigned_agent": "python-coder",
        "estimated_complexity": "S",
        "delivers_to": None,
        "expects_from": None,
        "declared_files": [
            {"path": f"scripts/ac_store/_fixture_{slug}.py", "state": "to_be_created"}
        ],
        "origin_agent": "business-analyst",
        "created": "2026-10-12",
        "superseded_by": None,
    }
    record.update(copy.deepcopy(overrides))
    for key in drop:
        record.pop(key, None)
    return record


def roots(count: int, prefix: str = "ACD-99") -> list[dict]:
    """`count` independent root (L0) records with no parent: ACD-990, ACD-991, ..."""
    return [
        valid_record(f"{prefix}{index}", level="L0") for index in range(count)
    ]


def hierarchy(
    prefix: str = "ACD-9990",
    children: int = 2,
    *,
    l1: dict | None = None,
    child: dict[int, dict] | None = None,
) -> list[dict]:
    """A coherent L0 -> L1 -> L2 chain: 2 + `children` records, links all correct."""
    l1_id = f"{prefix}a"
    child_ids = [f"{l1_id}-{n}" for n in range(1, children + 1)]
    l0 = valid_record(prefix, level="L0", covered_by=[l1_id])
    l1_fields = {"depends_on": [prefix], "covered_by": list(child_ids), **(l1 or {})}
    l1_rec = valid_record(l1_id, level="L1", **l1_fields)
    kids = [
        valid_record(
            cid, **{"level": "L2", "depends_on": [l1_id], **((child or {}).get(n, {}))}
        )
        for n, cid in enumerate(child_ids, start=1)
    ]
    return [l0, l1_rec, *kids]


def unreadable_record_text(record_id: str = "ACD-9992") -> str:
    """Record text whose YAML syntax error is reported at LINE 7 (PyYAML SafeLoader).

    Deliberately malformed bytes: the one fixture that is hand-typed on purpose.
    """
    return (
        f"id: {record_id}\n"
        "title: Broken record\n"
        "component: ac-driven-dev\n"
        "level: L0\n"
        "status: active\n"
        "criteria: fine\n"
        "readiness: draft: oops: [x\n"
    )


# --------------------------------------------------------------------------
# test intent (ACD-2500b-1-i): additive helpers, the API above is unchanged
# --------------------------------------------------------------------------
def intent_criteria(clauses: list[str]) -> str:
    """Gherkin criteria whose Then/And outcome lines are exactly `clauses`, in order.

    The first clause is the `Then`, every further one an `And`; lines end in `,`
    except the last (`.`), as the real store's criteria do, so a clause added later
    flips the old last clause's trailing punctuation (architect note, conflict 2).
    """
    lines = ["Given a fixture record,", "When the rule check runs,"]
    for index, clause in enumerate(clauses):
        keyword = "Then" if index == 0 else "And"
        end = "." if index == len(clauses) - 1 else ","
        lines.append(f"{keyword} {clause}{end}")
    return "\n".join(lines) + "\n"


def intent_entry(clause: str, needs_test: bool = True, reason: str = "The outcome needs proof.") -> dict:
    """One `test_intent` entry: {clause, needs_test, reason} (the shape of ACD-2500b-1)."""
    return {"clause": clause, "needs_test": needs_test, "reason": reason}


def intent_record(
    record_id: str,
    clauses: list[str],
    entries: list[dict] | None = None,
    **overrides: Any,
) -> dict:
    """A valid record whose criteria carry `clauses` and whose test_intent is `entries`.

    `entries` defaults to exactly one verbatim entry per clause (full coverage).
    """
    if entries is None:
        entries = [intent_entry(clause) for clause in clauses]
    return valid_record(
        record_id,
        criteria=intent_criteria(clauses),
        test_intent=copy.deepcopy(entries),
        **overrides,
    )


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------
def _dump(record: dict) -> str:
    return yaml.safe_dump(record, sort_keys=False, allow_unicode=True)


class Store:
    """A tmp consumer-style repo holding one feature folder of records."""

    def __init__(self, repo_root: Path, folder: Path):
        self.repo_root = repo_root
        self.folder = folder
        self.schema = repo_root / "config" / "ac_store_schema.json"
        self.registry = repo_root / "docs" / "components.json"
        self.index = repo_root / "docs" / "acceptance-criteria" / "index.yaml"
        self.snapshot_path = repo_root / "_before_snapshot.json"

    @property
    def location(self) -> str:
        """Repo-root-relative POSIX path of the feature folder (the --location value)."""
        return self.folder.relative_to(self.repo_root).as_posix()

    def path(self, record_id: str) -> Path:
        return self.folder / f"{record_id}.yaml"

    def rel(self, name: str) -> str:
        """Repo-root-relative POSIX path of a record id or file name in the folder."""
        file_name = name if "." in name else f"{name}.yaml"
        return (self.folder / file_name).relative_to(self.repo_root).as_posix()

    def read(self, record_id: str) -> dict:
        return yaml.safe_load(self.path(record_id).read_text(encoding="utf-8"))

    def write(self, record: dict) -> Path:
        """Add or overwrite one record file (real serializer, LF endings)."""
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.path(record["id"])
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_dump(record))
        return target

    def write_text(self, name: str, text: str) -> Path:
        """Write raw text as `name` in the folder (README.md, a malformed record)."""
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.folder / name
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return target


def make_store(
    tmp_path: Path,
    records: list[dict],
    *,
    component_dir: str = _DEFAULT_COMPONENT_DIR,
    feature: str = _DEFAULT_FEATURE,
) -> Store:
    """Build the tmp repo layout described in the module docstring."""
    repo_root = Path(tmp_path)
    for rel in (
        "config/ac_store_schema.json",
        "docs/components.json",
        "docs/acceptance-criteria/index.yaml",
    ):
        source = REPO_ROOT / rel
        target = repo_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    folder = repo_root / "docs" / "acceptance-criteria" / component_dir / feature
    folder.mkdir(parents=True, exist_ok=True)
    store = Store(repo_root, folder)
    for record in records:
        store.write(record)
    return store


def write_snapshot(store: Store, overrides: dict[str, Any] | None = None) -> Path:
    """Write {id: readiness} for every readable record on disk, then apply overrides."""
    snapshot: dict[str, Any] = {}
    for path in sorted(store.folder.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and data.get("id"):
            snapshot[str(data["id"])] = data.get("readiness")
    snapshot.update(overrides or {})
    store.snapshot_path.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
    return store.snapshot_path


def cli_argv(
    store: Store, *extra: str, stage: str = "ba", location: str | None = None
) -> list[str]:
    """Standard argv for `requirement_rule_check` against `store` (see module docstring)."""
    argv = [
        "--location", store.location if location is None else location,
        "--repo-root", str(store.repo_root),
        "--stage", stage,
    ]
    if "--before-snapshot" not in extra and "--before-ref" not in extra and stage != "approval":
        argv += ["--before-snapshot", str(write_snapshot(store))]
    return [*argv, *extra]


# --------------------------------------------------------------------------
# running the check
# --------------------------------------------------------------------------
class CliRun(NamedTuple):
    exit_code: int
    report: dict
    stdout: str
    stderr: str


def _parse_report(stdout: str, context: str) -> dict:
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(  # noqa: TRY003
            f"stdout must be exactly ONE JSON document ({context}); got {exc}: {stdout[:800]!r}"
        ) from exc
    assert isinstance(report, dict), f"report must be a JSON object ({context}): {report!r}"
    return report


@contextlib.contextmanager
def _working_directory(path: Path | None):
    if path is None:
        yield
        return
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def run_cli(argv: list[str], cwd: Path | None = None) -> tuple[int, dict]:
    """Run `requirement_rule_check.main(argv)` in process; return (exit_code, report)."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import requirement_rule_check  # noqa: PLC0415 - absence is the red state under test

    buffer = io.StringIO()
    with _working_directory(cwd), contextlib.redirect_stdout(buffer):
        exit_code = requirement_rule_check.main(list(argv))
    return exit_code, _parse_report(buffer.getvalue(), f"main({argv!r})")


def run_cli_subprocess(argv: list[str], cwd: Path | None = None) -> CliRun:
    """Run the check as `python scripts/ac_store/requirement_rule_check.py ...`."""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), *argv],
        cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
    )
    report = _parse_report(
        proc.stdout, f"subprocess argv={argv!r} exit={proc.returncode} stderr={proc.stderr[:800]!r}"
    )
    return CliRun(proc.returncode, report, proc.stdout, proc.stderr)


def check_store(
    store: Store, *extra: str, stage: str = "ba", location: str | None = None
) -> tuple[int, dict]:
    """The usual one-liner: build argv for `store`, run in process from its repo root."""
    return run_cli(cli_argv(store, *extra, stage=stage, location=location), cwd=store.repo_root)


# --------------------------------------------------------------------------
# assertions helpers
# --------------------------------------------------------------------------
def findings_for(
    report: dict, record_id: str | None = None, rule_family: str | None = None
) -> list[dict]:
    """Findings of `report` filtered by record id and/or rule family."""
    return [
        finding
        for finding in report.get("findings", [])
        if (record_id is None or finding.get("record_id") == record_id)
        and (rule_family is None or finding.get("rule_family") == rule_family)
    ]


FAMILY_PROTECTED = "protected fields"


def other_families(report: dict) -> dict:
    """A copy of `report` without the protected-fields family's `not evaluated` entries."""
    kept = [
        finding for finding in report.get("findings", [])
        if not (finding.get("rule_family") == FAMILY_PROTECTED
                and finding.get("disposition") == DISPOSITION_NOT_EVALUATED)
    ]
    return {**report, "findings": kept}


def check_store_other_families(
    store: Store, *extra: str, stage: str = "ba", location: str | None = None
) -> tuple[int, dict]:
    """check_store, its report passed through other_families."""
    exit_code, report = check_store(store, *extra, stage=stage, location=location)
    return exit_code, other_families(report)


def run_cli_subprocess_other_families(argv: list[str], cwd: Path | None = None) -> CliRun:
    """run_cli_subprocess, its parsed report passed through other_families (stdout untouched)."""
    run = run_cli_subprocess(argv, cwd=cwd)
    return run._replace(report=other_families(run.report))


def finding_text(finding: dict) -> str:
    """message + serialized detail: where a finding names the value it changed."""
    return f"{finding.get('message', '')} {json.dumps(finding.get('detail'), sort_keys=True)}"


def snapshot_tree(folder: Path) -> dict[str, bytes]:
    """{relative file name: bytes} for every file under `folder` (byte-identity checks)."""
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(Path(folder).rglob("*"))
        if path.is_file()
    }


# --------------------------------------------------------------------------
# real git repo helpers (additive; used by the --changed-since review tests)
# --------------------------------------------------------------------------
def git(repo_root: Path, *argv: str) -> str:
    """Run `git <argv>` in `repo_root` (identity and autocrlf pinned); return stdout."""
    proc = subprocess.run(
        ["git", "-c", "user.name=rc-test", "-c", "user.email=rc-test@example.invalid",
         "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *argv],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert proc.returncode == 0, f"git {argv} failed: {proc.stderr}"
    return proc.stdout


def init_git_repo(repo_root: Path) -> None:
    """`git init` a tmp repo root (a real repository, never a mock)."""
    git(repo_root, "init", "-q")


def commit_all(repo_root: Path, message: str = "commit") -> None:
    """Stage everything under `repo_root` and commit it."""
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", message)


def changed_since_argv(store: Store, rev: str = "HEAD", *extra: str, stage: str = "ba") -> list[str]:
    """argv for `--changed-since REV` mode, shaped like the plan-feature.js dispatch."""
    return [
        "--changed-since", rev, "--stage", stage,
        "--store-root", str(store.repo_root / "docs" / "acceptance-criteria"),
        "--repo-root", str(store.repo_root), "--before-ref", rev, *extra,
    ]
