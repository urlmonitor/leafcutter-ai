"""
MODULE: _ge120_provoking_fixture_ac_content
GOAL: AC-store file-content builders for the shared GE-120 provoking fixture.
    Split out of `_ge120_provoking_fixture_content.py` purely to keep that
    module's line count under the project's 400-line new-file limit — this
    module has no public contract of its own and is imported only by
    `_ge120_provoking_fixture_content.py`.
BUSINESS CONTEXT: See `_ge120_provoking_fixture.py`'s module docstring for the
    full rationale (SHARED with GE-120b-4; the fixture must provoke a genuine
    violation for every check in hooks_manifest.hooks[]).
ARCHITECTURE: Pure string/dict builders — no I/O, no git calls. `build_ac_files()`
    returns the docs/acceptance-criteria/ge120fixture/ portion of the fixture
    file set.
DECISION HISTORY: 2026-09-08 [python-coder/GE-120b-2-i] — split out of
    _ge120_provoking_fixture_content.py to satisfy the 400-line new-file limit.
"""

from __future__ import annotations

_AC_DIR = "docs/acceptance-criteria/ge120fixture"


def _ac_yaml(ac_id: str, level: str, **extra: object) -> str:
    """Render a minimal AC YAML record for the fixture store.

    Args:
        ac_id: The AC identifier to embed as both `id:` and the criteria text.
        level: The AC level string (e.g. "L0", "L1", "L2").
        **extra: Additional top-level YAML fields, rendered as raw lines. Each
            value is inserted verbatim if it is already a formatted YAML
            fragment (a string), or as a single-item list otherwise.

    Returns:
        A YAML document string for one AC store record.
    """
    lines = [
        f"id: {ac_id}",
        f'title: "GE-120b-2-i fixture record {ac_id}"',
        f"level: {level}",
        "status: active",
        "req_status: draft",
        "readiness: approved",
        "priority: low",
        "origin_agent: BrainCandy",
        "created: 2026-09-08",
        "criteria: |",
        f"  Fixture-only record for the GE-120b-2-i provoking fixture ({ac_id}).",
    ]
    for key, value in extra.items():
        if isinstance(value, str):
            lines.append(f"{key}: {value}")
        elif isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                lines.extend(f"  - {item}" for item in value)
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def build_ac_files() -> dict[str, str]:
    """Build the AC-store portion of the fixture file set.

    Returns:
        Mapping of repo-relative path to file content for every AC YAML
        record the fixture needs.
    """
    files: dict[str, str] = {}

    # L0 parent with NO covered_by entries -> check-ac-parent-covered-by fires
    # for every one of its 8 children below. 8 L1 children -> exceeds the
    # >7-per-L0 hard cap -> check-ac-limits fires too.
    files[f"{_AC_DIR}/GEFX-100.yaml"] = _ac_yaml(
        "GEFX-100", "L0", work_status="todo", covered_by=[],
    )
    for suffix in "abcdefgh":
        child_id = f"GEFX-100{suffix}"
        files[f"{_AC_DIR}/{child_id}.yaml"] = _ac_yaml(
            child_id, "L1", work_status="todo", depends_on=["GEFX-100"],
        )

    # implements_pattern referencing a pattern id that exists nowhere in the
    # store -> check-ac-pattern-refs.
    files[f"{_AC_DIR}/GEFXPAT-100.yaml"] = _ac_yaml(
        "GEFXPAT-100", "L2", work_status="todo",
        implements_pattern="GEFX-NONEXISTENT-PATTERN-999",
    )

    # approved + not done + code + leaf + no test_spec/test_required ->
    # check-ac-schema's validate_test_contract.
    files[f"{_AC_DIR}/GEFXSCHEMA-100.yaml"] = _ac_yaml(
        "GEFXSCHEMA-100", "L2", work_status="todo", change_target="code",
    )

    # Mutual depends_on -> check-ac-circular-deps.
    files[f"{_AC_DIR}/GEFXCYC-100.yaml"] = _ac_yaml(
        "GEFXCYC-100", "L2", work_status="todo", depends_on=["GEFXCYC-200"],
    )
    files[f"{_AC_DIR}/GEFXCYC-200.yaml"] = _ac_yaml(
        "GEFXCYC-200", "L2", work_status="todo", depends_on=["GEFXCYC-100"],
    )

    # work_status: done with no "# covers: GEFXDONE-100" tag anywhere on disk
    # -> check-done-proof.
    files[f"{_AC_DIR}/GEFXDONE-100.yaml"] = _ac_yaml(
        "GEFXDONE-100", "L2", work_status="done",
    )

    # Left at work_status: todo on purpose; a ticket below claims status:done
    # against this id -> check-ticket-ac-status-parity.
    files[f"{_AC_DIR}/GEFXPARITY-100.yaml"] = _ac_yaml(
        "GEFXPARITY-100", "L2", work_status="todo",
    )
    return files
