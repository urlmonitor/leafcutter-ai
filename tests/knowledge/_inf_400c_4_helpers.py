"""
MODULE: _inf_400c_4_helpers
GOAL: Shared fixtures/helpers for the INF-400c-4 test suite, split out of
    test_inf_400c_4.py purely to keep each test file under the
    check-file-size guard's line limit (GE-127a-1) -- nothing here is
    test-specific; every test module in this split imports from here.
AC: INF-400c-4 (source_ac)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_KNOWLEDGE_SRC_DIR = _REPO_ROOT / "scripts" / "knowledge"
_HARVESTER_SRC = _KNOWLEDGE_SRC_DIR / "harvest_learnings.py"
_CHECK_SINK_PARITY = _REPO_ROOT / "scripts" / "ci" / "check_sink_parity.py"

# Required sibling modules harvest_learnings.py loads at import time via
# _load_required_sibling_module (GE-127b-1 file-size fix). A deploy that
# copies harvest_learnings.py without these crashes with ImportError before
# it can do anything -- must be kept in lockstep with build_knowledge_scripts's
# own deploy_scripts list (scripts/build_phases_knowledge.py).
_HARVESTER_REQUIRED_SIBLINGS: tuple[str, ...] = (
    "harvest_result.py",
    "sink_resolution.py",
    "capture_write.py",
    "harvest_cli.py",
    "harvest_status.py",
)

_REAL_SURFACES: tuple[tuple[str, Path, tuple[str, ...]], ...] = (
    ("signoff", _REPO_ROOT / "templates" / "skills" / "signoff" / "SKILL.md",
     ("skills", "signoff", "SKILL.md")),
    ("product-owner", _REPO_ROOT / "templates" / "agents" / "product-owner.md",
     ("agents", "product-owner.md")),
    ("business-analyst", _REPO_ROOT / "templates" / "agents" / "business-analyst.md",
     ("agents", "business-analyst.md")),
    ("it-po", _REPO_ROOT / "templates" / "agents" / "it-po.md",
     ("agents", "it-po.md")),
)

# A minimal, synthetic surface paragraph that resolves via the real
# --print-sink invocation -- deliberately tiny, used only for the
# negative-control tests where independent per-surface control is required.
_SYNTHETIC_INVOCATION_SURFACE = (
    "# Synthetic surface\n\n"
    "Emit one `knowledge_captured` event. Obtain the sink by running "
    "`python3 .leafcutter/scripts/knowledge/harvest_learnings.py --print-sink` "
    "and append the event there.\n"
)

# A minimal, synthetic surface paragraph that self-carries a literal
# destination instead of resolving the declaration -- the pre-AC defective
# shape.
_SYNTHETIC_LITERAL_SURFACE = (
    "# Synthetic surface\n\n"
    "Emit one `knowledge_captured` event by appending it to "
    "`debugging/logs/agent_telemetry.jsonl` directly.\n"
)

_TIMEOUT_SECONDS = 30


def _deploy_harvester(deployed_root: Path) -> Path:
    """Deploy harvest_learnings.py AND its required sibling modules.

    Mirrors what a real ``build.py`` run actually deploys
    (``build_knowledge_scripts`` in ``scripts/build_phases_knowledge.py``) --
    copying only ``harvest_learnings.py`` in isolation would crash every
    caller of this fixture with ``ImportError`` the moment the deployed
    script tries to load its required siblings.
    """
    output_dir = deployed_root / "scripts" / "knowledge"
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "harvest_learnings.py"
    shutil.copy2(_HARVESTER_SRC, dest)
    for sibling_name in _HARVESTER_REQUIRED_SIBLINGS:
        shutil.copy2(_KNOWLEDGE_SRC_DIR / sibling_name, output_dir / sibling_name)
    return dest


def _write_declaration(
    deployed_root: Path,
    *,
    knowledge_emission_sink: str,
    operational_telemetry_stream: str,
) -> Path:
    config_path = deployed_root / "config" / "knowledge_sink.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "knowledge_emission_sink": knowledge_emission_sink,
                "operational_telemetry_stream": operational_telemetry_stream,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path


def _deploy_real_surfaces(deployed_root: Path) -> None:
    """Deploy the four REAL, unmodified template surfaces verbatim."""
    for _surface_id, src, relative_parts in _REAL_SURFACES:
        dest = deployed_root.joinpath(*relative_parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def _deploy_synthetic_surfaces(deployed_root: Path, overrides: dict[str, str]) -> None:
    """Deploy four minimal synthetic surfaces; *overrides* replaces specific ids."""
    for surface_id, _src, relative_parts in _REAL_SURFACES:
        text = overrides.get(surface_id, _SYNTHETIC_INVOCATION_SURFACE)
        dest = deployed_root.joinpath(*relative_parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def _run_check_sink_parity(target_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CHECK_SINK_PARITY), "--target-dir", str(target_dir)],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )


def _run_print_sink(harvester_path: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(harvester_path), "--print-sink"],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
        cwd=str(cwd),
    )


def _run_harvester_default(harvester_path: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(harvester_path)],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
        cwd=str(cwd),
    )
