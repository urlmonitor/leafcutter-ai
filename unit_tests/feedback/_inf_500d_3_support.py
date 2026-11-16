"""
MODULE: _inf_500d_3_support
GOAL: Shared support for the AC INF-500d-3 tests (``test_inf_500d_3.py`` and ``test_inf_500d_3_exits.py``):
    the copied-layout helpers, the argv builders, the failure-scenario tables and the readers of
    ``submit_failure_reasons.json``. No test lives here; the contract is documented in ``test_inf_500d_3.py``.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, TypedDict, Unpack

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._inf_500d_4_vi_helpers import _enduring, _tmpdir, _worktree

TICKET = "tickets/00_inbox/TICKET-inf-500d-3-probe.md"
SINK_PREFIX = "[submit_feedback] sink: "
PREFIX = "submit-failed:"
VOCAB_NAME = "submit_failure_reasons.json"
REAL_ID_EXAMPLE = "fb_2026-11-16_1a2b3c4d"
MARKER_EXAMPLE = "(submit-failed:destination-unwritable:complete)"
BARE = "(submit-failed)"
_DEV_FULL = "/dev/full"


# ---------------------------------------------------------------------------
# layout, argv and running
# ---------------------------------------------------------------------------

@dataclass
class Lay:
    base: Path
    project: Path
    out_root: Path
    root: Path
    tmpdir: Path
    cwd: Path

    @property
    def sink(self) -> Path:
        return self.root / "feedback.jsonl"


def _layout(base: Path) -> Lay:
    """A copied deployed install with its own declared sink and a confined TMPDIR."""
    root = _enduring(base)
    project, out_root = _worktree(base, "wt", root)
    cwd = project / "work"
    cwd.mkdir()
    return Lay(base, project, out_root, root, _tmpdir(base), cwd)


def _argv(*, category: str | None = "complete", phase: str | None = "python-coder",
          ticket: str | None = TICKET, tags: str | None = None, extra: tuple[str, ...] = ()) -> list[str]:
    argv: list[str] = []
    if ticket is not None:
        argv += ["--ticket", ticket]
    if phase is not None:
        argv += ["--phase", phase]
    if category is not None:
        argv += ["--category", category]
    argv += ["--note", "probe"]
    if tags:
        argv += ["--tags", tags]
    return argv + list(extra)


def _hook_argv(*, category: str = "process-finding", hook_name: str | None = "check_probe",
               outcome: str | None = "warn") -> list[str]:
    argv = ["--source", "hook", "--phase", "check_probe", "--category", category, "--note", "probe"]
    if hook_name is not None:
        argv += ["--hook-name", hook_name]
    if outcome is not None:
        argv += ["--outcome", outcome]
    return argv


def _run(lay: Lay, argv: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return h.run_py(h.submit_script(lay.out_root), argv, lay.cwd, lay.tmpdir, env_extra=env)


def _reason_lines(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in proc.stderr.splitlines() if line.startswith(PREFIX)]


def _human_lines(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in h.stderr_lines(proc) if not line.startswith(PREFIX)]


def _facts_of_a_write(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in proc.stderr.splitlines() if line.startswith("sidecar:") or line.startswith(SINK_PREFIX)]


def _assert_reason(proc: subprocess.CompletedProcess[str], reason: str, category: str, label: str = "") -> None:
    """The whole stderr/exit contract of one failure exit."""
    where = f"{label}: " if label else ""
    assert proc.returncode != 0, f"{where}a failure must stay non-zero: stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert proc.stdout == "", f"{where}nothing may be printed on stdout (a caller would capture it as the id): {proc.stdout!r}"
    assert _reason_lines(proc) == [f"{PREFIX}{reason}:{category}"], (
        f"{where}expected exactly one line {PREFIX}{reason}:{category}, stderr={proc.stderr!r}")
    assert "Traceback" not in proc.stderr, f"{where}the run ended in a traceback: {proc.stderr!r}"
    assert not _facts_of_a_write(proc), f"{where}a failed run must carry no sidecar/sink line: {proc.stderr!r}"


@dataclass
class Scn:
    """One failure scenario: how to prepare a fresh layout, what to run, and the category part expected."""

    prepare: Callable[[Lay], object] = lambda lay: None
    argv: Callable[[Lay], list[str]] = lambda lay: _argv()
    env: Callable[[Lay], dict[str, str] | None] = lambda lay: None
    category: str = "complete"
    extra: dict = field(default_factory=dict)


def _exec(lay: Lay, scn: Scn) -> tuple[subprocess.CompletedProcess[str], set[str]]:
    """Prepare, snapshot the whole temp tree, run; return the process and the snapshot taken before the run."""
    scn.prepare(lay)
    env = scn.env(lay)
    argv = scn.argv(lay)
    before = h.snapshot(lay.base)
    return _run(lay, argv, env), before


def _block_yaml(lay: Lay) -> dict[str, str]:
    """A ``yaml.py`` that raises ImportError, first on PYTHONPATH: PyYAML 'not installed'."""
    blocker = lay.base / "block_yaml"
    blocker.mkdir(exist_ok=True)
    (blocker / "yaml.py").write_text("raise ImportError('PyYAML blocked for the test')\n", encoding="utf-8")
    return {"PYTHONPATH": str(blocker)}


def _categories_file(lay: Lay) -> Path:
    return lay.out_root / "config" / "feedback_categories.yaml"


def _bad_declaration(case: str, out_root: Path) -> None:
    path = h.declaration_path(out_root)
    if case == "malformed_json":
        path.write_text('{"feedback_sink": "/x/feedback.jsonl", ', encoding="utf-8")
    elif case == "zero_byte_file":
        path.write_text("", encoding="utf-8")
    elif case == "declaration_is_a_directory":
        path.unlink()
        path.mkdir()
    elif case == "not_an_object":
        path.write_text("[]\n", encoding="utf-8")
    elif case == "missing_both_keys":
        h.rewrite_declaration(out_root, feedback_sink=None, operational_log_root=None)
    elif case == "relative_values":
        h.rewrite_declaration(out_root, operational_log_root="debugging/logs",
                              feedback_sink="debugging/logs/feedback.jsonl")
    else:  # pragma: no cover - guards a typo in the table below
        raise AssertionError(case)


def _prep_bad_declaration(case: str) -> Callable[[Lay], object]:
    return lambda lay: _bad_declaration(case, lay.out_root)


def _prep_stale_root(lay: Lay) -> None:
    h.declare(lay.out_root, lay.base / "gone_project" / "debugging" / "logs")


def _prep_sink_outside_root(lay: Lay) -> None:
    elsewhere = lay.base / "elsewhere"
    elsewhere.mkdir()
    h.rewrite_declaration(lay.out_root, feedback_sink=str(elsewhere / "feedback.jsonl"))


def _prep_log_dir_is_a_file(lay: Lay) -> None:
    project = lay.base / "enduring2"
    project.mkdir()
    (project / "logs").write_text("a regular file where the log directory must go\n", encoding="utf-8")
    h.declare(lay.out_root, project / "logs")


def _prep_jsonl_directory(lay: Lay) -> None:
    (lay.base / "a_directory").mkdir()


def _prep_jsonl_parent_file(lay: Lay) -> None:
    (lay.base / "a_file").write_text("not a directory\n", encoding="utf-8")


def _jsonl(path_of: Callable[[Lay], str]) -> Callable[[Lay], list[str]]:
    return lambda lay: _argv(extra=("--jsonl", path_of(lay)))


class _ArgvOptions(TypedDict, total=False):
    """The keyword options ``_argv`` accepts (each may be omitted, so its default applies)."""

    category: str | None
    phase: str | None
    ticket: str | None
    tags: str | None
    extra: tuple[str, ...]


def _kw(**kwargs: Unpack[_ArgvOptions]) -> Callable[[Lay], list[str]]:
    return lambda lay: _argv(**kwargs)


MALFORMED = {
    "unrecognised_category": Scn(argv=_kw(category="zzz-unknown"), category="zzz-unknown"),
    "tag_starts_with_a_digit": Scn(argv=_kw(tags="1abc")),
    "tag_has_an_uppercase_letter": Scn(argv=_kw(tags="Abc")),
    "addressed_by_is_not_json": Scn(argv=_kw(extra=("--addressed-by", "not json"))),
    "addressed_by_is_not_a_list": Scn(argv=_kw(extra=("--addressed-by", '{"type": "ticket", "ref": "x"}'))),
    "addressed_by_holds_a_non_object": Scn(argv=_kw(extra=("--addressed-by", '["x"]'))),
    "addressed_by_has_a_bad_type": Scn(argv=_kw(extra=("--addressed-by", '[{"type": "zzz", "ref": "x"}]'))),
    "addressed_by_has_an_empty_ref": Scn(argv=_kw(extra=("--addressed-by", '[{"type": "ticket", "ref": ""}]'))),
    "parser_missing_phase": Scn(argv=_kw(phase=None)),
    "parser_invalid_severity_choice": Scn(argv=_kw(extra=("--severity", "extreme"))),
    "parser_non_integer_staged_files_count": Scn(argv=_kw(extra=("--staged-files-count", "many"))),
    "agent_source_without_ticket": Scn(argv=_kw(ticket=None)),
    "hook_source_without_hook_name": Scn(argv=lambda lay: _hook_argv(hook_name=None), category="process-finding"),
    "hook_source_without_outcome": Scn(argv=lambda lay: _hook_argv(outcome=None), category="process-finding"),
}

FACILITY = {
    "pyyaml_missing": Scn(env=_block_yaml),
    "categories_file_absent": Scn(prepare=lambda lay: _categories_file(lay).unlink()),
    "categories_file_unparseable": Scn(
        prepare=lambda lay: _categories_file(lay).write_text("key: [unclosed\n  bad: : :\n", encoding="utf-8")),
    "categories_file_empty": Scn(prepare=lambda lay: _categories_file(lay).write_text("", encoding="utf-8")),
}

DESTINATION = {
    "declaration_absent": Scn(prepare=lambda lay: h.declaration_path(lay.out_root).unlink()),
    "declaration_malformed_json": Scn(prepare=_prep_bad_declaration("malformed_json")),
    "declaration_zero_byte": Scn(prepare=_prep_bad_declaration("zero_byte_file")),
    "declaration_is_a_directory": Scn(prepare=_prep_bad_declaration("declaration_is_a_directory")),
    "declaration_not_an_object": Scn(prepare=_prep_bad_declaration("not_an_object")),
    "declaration_keys_missing": Scn(prepare=_prep_bad_declaration("missing_both_keys")),
    "declaration_relative_values": Scn(prepare=_prep_bad_declaration("relative_values")),
    "stale_enduring_root": Scn(prepare=_prep_stale_root),
    "sink_not_directly_under_the_root": Scn(prepare=_prep_sink_outside_root),
    "log_directory_not_creatable": Scn(prepare=_prep_log_dir_is_a_file),
    "jsonl_names_a_directory": Scn(prepare=_prep_jsonl_directory,
                                   argv=_jsonl(lambda lay: str(lay.base / "a_directory"))),
    "jsonl_parent_is_a_regular_file": Scn(prepare=_prep_jsonl_parent_file,
                                          argv=_jsonl(lambda lay: str(lay.base / "a_file" / "x.jsonl"))),
    "jsonl_is_dev_full_append_fails": Scn(argv=_jsonl(lambda lay: _DEV_FULL)),
}


# ---------------------------------------------------------------------------
# the vocabulary file (read from the copied layout, standard library only)
# ---------------------------------------------------------------------------

def _vocab_file(out_root: Path) -> Path:
    return out_root / "scripts" / "feedback" / VOCAB_NAME


def _load_vocab(out_root: Path):
    path = _vocab_file(out_root)
    assert path.is_file(), (
        f"vocabulary file missing: {path} (templates/scripts/feedback/{VOCAB_NAME} must exist so the copied "
        f"layout carries it; a constant in submit_feedback.py does not satisfy this)")
    return json.loads(path.read_text(encoding="utf-8"))


def _reasons(vocab) -> list[dict]:
    candidates = [vocab] if isinstance(vocab, list) else [v for v in vocab.values() if isinstance(v, list)]
    found = [c for c in candidates if c and all(isinstance(x, dict) and "id" in x for x in c)]
    assert len(found) == 1, f"the file must hold exactly one list of reason objects with an 'id': {vocab!r}"
    return found[0]


def _ids(vocab) -> list[str]:
    return [r["id"] for r in _reasons(vocab)]


def _strings(node, skip: list[dict]) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v, skip)]
    if isinstance(node, list):
        if node is skip:
            return []
        return [s for v in node for s in _strings(v, skip)]
    return []


def _the_one(matches: set[str], what: str) -> re.Pattern[str]:
    assert len(matches) == 1, f"the vocabulary must hold exactly one {what} pattern, found {sorted(matches)!r}"
    return re.compile(next(iter(matches)))


def _patterns(vocab) -> dict[str, re.Pattern[str]]:
    """Find the three value patterns by what they accept (so no key name is assumed)."""
    real: set[str] = set()
    reasoned: set[str] = set()
    legacy: set[str] = set()
    for text in set(_strings(vocab, _reasons(vocab))):
        try:
            rx = re.compile(text)
        except re.error:
            continue
        if rx.search(REAL_ID_EXAMPLE) and not rx.search(MARKER_EXAMPLE):
            real.add(text)
        if rx.search(MARKER_EXAMPLE) and not rx.search(BARE):
            reasoned.add(text)
        if rx.search(BARE) and not rx.search(MARKER_EXAMPLE):
            legacy.add(text)
    return {"real": _the_one(real, "real-id"), "reasoned": _the_one(reasoned, "reasoned-marker"),
            "legacy": _the_one(legacy, "legacy-bare")}


def _marker_form(vocab) -> str:
    forms = sorted(s for s in _strings(vocab, _reasons(vocab)) if "<reason>" in s and "<category>" in s)
    assert forms, "the vocabulary must carry the marker form with <reason> and <category> placeholders"
    return next((f for f in forms if f.startswith("feedback-id:")), forms[0])


def _fill_form(form: str, reason: str, category: str) -> str:
    """The comment value (the text after ``feedback-id:``) for ``reason`` and ``category``."""
    return form.replace("<reason>", reason).replace("<category>", category).split("feedback-id:", 1)[-1].strip()


def _reasoned_value(line: str) -> str:
    """The marker value the caller would record from one ``submit-failed:`` stderr line."""
    return f"({line})"


def _holdable(value: str, vocab) -> bool:
    """Holdable only for a reasoned marker whose reason has record_written false -- decided from the flag."""
    match = _patterns(vocab)["reasoned"].search(value)
    if match is None:
        return False  # legacy bare form (reason unknown) or anything else: never holdable
    by_id = {r["id"]: r for r in _reasons(vocab)}
    entry = by_id.get(match.group(1))
    return entry is not None and entry["record_written"] is False


def _caller_reason(stdout: str, stderr: str, recovered_id: str | None) -> str | None:
    """The capture precedence of the signoff instruction (stdout id; recovery-file id; the line; the facts)."""
    if stdout.strip() or recovered_id:
        return None
    lines = stderr.splitlines()
    for line in lines:
        if line.startswith(PREFIX):
            return line.split(":")[1]
    if any(line.startswith("sidecar:") or line.startswith(SINK_PREFIX) for line in lines):
        return "written-uncited"
    return "facility-unavailable"


def _sidecar_file(proc: subprocess.CompletedProcess[str]) -> Path:
    lines = [line for line in proc.stderr.splitlines() if line.startswith("sidecar:")]
    assert len(lines) == 1, f"expected exactly one sidecar line: {proc.stderr!r}"
    return Path(lines[0].split("sidecar:", 1)[1])
