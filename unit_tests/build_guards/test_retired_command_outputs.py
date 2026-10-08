"""
MODULE: test_retired_command_outputs
GOAL: Pin the ownership rules of build_retired_outputs against real files on
    disk: a retired command output is removed only where the previous install's
    own record plus a content-hash match prove the copy is unmodified package
    output; every other copy is kept byte-for-byte and named; files the build
    never recorded, still-shipped commands, and other template families are
    never touched.
BUSINESS CONTEXT: TICKET-20260930-RetireRenamedCommandOutputs. The step deletes
    files in an adopter's installed tree, so its keep-side guarantees (ADR-041:
    non-attribution means keep, kept items are reported) matter as much as the
    removal. test_retired_command_outputs_build.py proves the wiring through
    real build.py subprocesses; this module proves the verdicts cheaply,
    without a build.
ARCHITECTURE: Import-based, against a tmp_path target tree (never the repo
    tree), matching test_ki_bp_010_clean_workflows.py. Record entries use the
    exact output_mappings shape .build_manifest.json carries, and hashes use
    the same CRLF-normalised SHA-256 the build and check_output_drift.py use.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_retired_outputs as bro  # noqa: E402

_CONTENT = b"---\ndescription: a retired command\n---\n\n# /old\n"


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _entry(template: str, raw: bytes = _CONTENT) -> dict[str, str]:
    return {"expected_output_hash": _hash(raw), "template": template}


def _install(target: Path, rel: str, raw: bytes = _CONTENT) -> Path:
    path = target / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


@pytest.fixture
def target(tmp_path: Path) -> Path:
    root = tmp_path / "adopter"
    root.mkdir()
    return root


# What the current sources still produce in the two command directories: one
# still-shipped sibling each, so both directories are ones this run writes into.
_STILL_SHIPPED = {".claude/commands/still-shipped.md", ".gemini/workflows/still-shipped.md"}


def _retire(target: Path, previous: dict, current: set[str] | None = None, dry_run: bool = False):
    keys = _STILL_SHIPPED if current is None else current
    return bro.retire_outputs(target, target / ".leafcutter", previous, keys, dry_run)


def _old_workflow_record() -> dict[str, dict[str, str]]:
    template = "<package>/templates/workflows/old.md"
    return {
        ".claude/commands/old.md": _entry(template),
        ".gemini/workflows/old.md": _entry(template),
    }


_OLD_COPIES = (
    ".claude/commands/old.md",
    ".leafcutter/commands/old.md",
    ".gemini/workflows/old.md",
    ".leafcutter/gemini/workflows/old.md",
)


def test_unmodified_copies_of_a_retired_workflow_are_removed_everywhere(target: Path) -> None:
    for rel in _OLD_COPIES:
        _install(target, rel)

    report = _retire(target, _old_workflow_record())

    assert [rel for rel in _OLD_COPIES if (target / rel).exists()] == []
    assert sorted(report.removed) == sorted(_OLD_COPIES)
    assert report.kept == []


def test_a_retired_copy_changed_after_install_is_kept_byte_for_byte_and_named(target: Path) -> None:
    edited = b"---\ndescription: my own notes now\n---\n"
    _install(target, ".claude/commands/old.md", edited)
    _install(target, ".leafcutter/commands/old.md")

    report = _retire(target, {".claude/commands/old.md": _entry("<package>/templates/commands/old.md")})

    assert (target / ".claude/commands/old.md").read_bytes() == edited
    assert report.kept == [
        (".claude/commands/old.md", bro.ADOPTER_OWNED, "its content changed after the package installed it")
    ]
    assert not (target / ".leafcutter/commands/old.md").exists()
    assert report.removed == [".leafcutter/commands/old.md"]


def test_a_command_file_the_build_never_recorded_is_neither_touched_nor_named(
    target: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    own = _install(target, ".claude/commands/team-notes.md", b"# the adopter's own command\n")
    for rel in _OLD_COPIES:
        _install(target, rel)
    monkeypatch.setattr(bro, "current_command_output_keys", lambda *_args: _STILL_SHIPPED)

    report = bro.run_retired_output_sweep(
        target, target / ".leafcutter", {}, dry_run=False, previous_mappings=_old_workflow_record()
    )

    assert own.read_bytes() == b"# the adopter's own command\n"
    assert "team-notes.md" not in capsys.readouterr().out
    assert all("team-notes" not in shown for shown in report.removed + [k[0] for k in report.kept])


def test_a_command_the_package_still_ships_is_never_removed(target: Path) -> None:
    for rel in _OLD_COPIES:
        _install(target, rel)

    report = _retire(target, _old_workflow_record(), current=_STILL_SHIPPED | {".claude/commands/old.md", ".gemini/workflows/old.md"})

    assert [rel for rel in _OLD_COPIES if not (target / rel).exists()] == []
    assert report.removed == [] and report.kept == []


@pytest.mark.parametrize(
    ("key", "template"),
    [
        (".claude/workflows/build-epic.js", "<package>/templates/workflows-js/build-epic.js"),
        (".claude/agents/old-agent.md", "<package>/templates/agents/old-agent.md"),
        (".claude/hooks/old_hook.py", "<package>/templates/hooks/old_hook.py"),
        (".claude/skills/old/SKILL.md", "<package>/templates/skills/old/SKILL.md"),
    ],
)
def test_recorded_outputs_of_other_template_families_are_never_removed(
    target: Path, key: str, template: str
) -> None:
    installed = _install(target, key)
    # A still-shipped sibling in the SAME directory, so only the template-family
    # rule -- not the directory rule -- can be what keeps this file.
    sibling = key.rsplit("/", 1)[0] + "/still-shipped" + Path(key).suffix

    report = _retire(target, {key: _entry(template)}, current={sibling})

    assert installed.read_bytes() == _CONTENT
    assert report.removed == [] and report.kept == []


def test_a_record_key_pointing_outside_the_target_is_ignored(tmp_path: Path, target: Path) -> None:
    outside = _install(tmp_path, "outside.md")

    report = _retire(target, {"../outside.md": _entry("<package>/templates/workflows/outside.md")})

    assert outside.read_bytes() == _CONTENT
    assert report.removed == [] and report.kept == []


@pytest.mark.parametrize(
    "stale_spelling",
    [".leafcutter/commands/still-shipped.md", ".claude\commands\still-shipped.md"],
)
def test_a_record_in_another_key_spelling_never_makes_a_still_shipped_file_look_retired(
    target: Path, stale_spelling: str
) -> None:
    shipped = _install(target, ".leafcutter/commands/still-shipped.md")
    canonical = _install(target, ".claude/commands/still-shipped.md")

    report = _retire(target, {stale_spelling: _entry("<package>/templates/workflows/still-shipped.md")})

    assert shipped.read_bytes() == _CONTENT and canonical.read_bytes() == _CONTENT
    assert report.removed == [] and report.kept == []


def test_a_crlf_checkout_of_unmodified_output_still_counts_as_package_output(target: Path) -> None:
    crlf = _install(target, ".claude/commands/old.md", _CONTENT.replace(b"\n", b"\r\n"))

    report = _retire(target, {".claude/commands/old.md": _entry("templates/workflows/old.md")})

    assert not crlf.exists()
    assert report.removed == [".claude/commands/old.md"]


def test_dry_run_names_what_it_would_remove_and_removes_nothing(
    target: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for rel in _OLD_COPIES:
        _install(target, rel)
    monkeypatch.setattr(bro, "current_command_output_keys", lambda *_args: _STILL_SHIPPED)

    report = bro.run_retired_output_sweep(
        target, target / ".leafcutter", {}, dry_run=True, previous_mappings=_old_workflow_record()
    )

    out = capsys.readouterr().out
    assert [rel for rel in _OLD_COPIES if not (target / rel).exists()] == []
    assert sorted(report.removed) == sorted(_OLD_COPIES)
    assert all(f"would remove retired: {rel}" in out for rel in _OLD_COPIES)


def test_without_a_previous_install_record_nothing_is_removed_and_the_run_says_so(
    target: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for rel in _OLD_COPIES:
        _install(target, rel)
    monkeypatch.setattr(bro, "current_command_output_keys", lambda *_args: _STILL_SHIPPED)

    report = bro.run_retired_output_sweep(target, target / ".leafcutter", {}, dry_run=False, previous_mappings={})

    assert [rel for rel in _OLD_COPIES if not (target / rel).exists()] == []
    assert report.removed == [] and report.kept == []
    assert "nothing examined" in capsys.readouterr().out


def _symlink_or_skip(link: Path, to: Path, is_dir: bool) -> None:
    try:
        os.symlink(to, link, target_is_directory=is_dir)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable on this host: {exc}")


def test_a_symlink_where_a_retired_file_was_installed_is_kept_and_named(target: Path) -> None:
    real = _install(target, "elsewhere/old.md")
    link = target / ".claude/commands/old.md"
    link.parent.mkdir(parents=True)
    _symlink_or_skip(link, real, is_dir=False)

    report = _retire(target, {".claude/commands/old.md": _entry("templates/workflows/old.md")})

    assert link.is_symlink() and real.read_bytes() == _CONTENT
    assert [(shown, verdict) for shown, verdict, _ in report.kept] == [(".claude/commands/old.md", bro.UNATTRIBUTABLE)]


def test_through_a_symlink_shim_the_one_physical_file_is_removed_once(target: Path) -> None:
    source = _install(target, ".leafcutter/commands/old.md")
    (target / ".claude").mkdir()
    _symlink_or_skip(target / ".claude/commands", source.parent, is_dir=True)

    report = _retire(target, {".claude/commands/old.md": _entry("templates/workflows/old.md")})

    assert not source.exists()
    assert report.removed == [".claude/commands/old.md"]


def test_the_current_set_is_recomputed_from_the_package_sources(target: Path) -> None:
    keys = bro.current_command_output_keys(target, target / ".leafcutter", {})

    assert ".claude/commands/leafcutter-help.md" in keys
    assert ".gemini/workflows/leafcutter-help.md" in keys
    assert ".claude/commands/leafcutter.md" not in keys
    assert not [k for k in keys if k.startswith(".claude/workflows/")]
