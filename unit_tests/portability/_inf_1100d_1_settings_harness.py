"""
MODULE: _inf_1100d_1_settings_harness
AC: INF-1100d-1 -- "A fresh install carries no test database address"
    INF-1100d-1-i -- "Upgrading keeps a project's own database setting and
    never writes a shipped default back"
GOAL: Shared, test-only fixture builders and path constants for the two ACs'
    real production surfaces: ``config_loader.load_config()`` (the settings
    resolver ``build.py`` uses) and ``build.py``'s own in-process
    ``_migrate_skills_config()`` settings-migration step. Centralises
    project-fixture construction and the ``scripts/`` sys.path push so
    ``test_inf_1100d_1.py`` and ``test_inf_1100d_1_i.py`` cannot drift from
    each other on how a project fixture is built or how the real modules
    are imported.
BUSINESS CONTEXT: CLAUDE.md "Tests must not spawn their own build.py"
    forbids a subprocess ``build.py`` run here; both ACs' own
    it_requirements instead name the in-process steps
    (``config_loader.load_config``, ``build.py``'s
    ``_migrate_skills_config``) as the surfaces to exercise directly. This
    harness performs the one sys.path push both test files need to import
    ``build`` and ``config_loader`` as real modules (mirroring the existing
    ``from build_phases import build_commit_guardian`` sys.path precedent
    in ``unit_tests/portability/test_ge_120e_1.py``) and exposes real
    on-disk project fixtures written via ``json.dump`` (never a hand-typed
    literal -- ``unit_tests/README.md`` #4, the Fixture Authenticity Rule).
NOTE: The literal legacy shipped address (the one currently in
    ``config/skills_config.default.json`` and
    ``config/skills_config.schema.json``) never appears anywhere in this
    harness or either test file it backs -- both this AC pair's tests and
    the future INF-1100d-4 shipped-path scanner treat that string as
    forbidden. Every fixture below instead uses ``PROJECT_OWNED_ADDRESS``,
    the AC's own worked example of a *project-owned* setting.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEFAULTS_PATH = REPO_ROOT / "config" / "skills_config.default.json"
SCHEMA_PATH = REPO_ROOT / "config" / "skills_config.schema.json"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build  # noqa: E402 -- the real settings-migration step (build.py)
import config_loader  # noqa: E402 -- the real settings resolver build.py uses

# The AC's own example address (INF-1100d-1 criteria text, verbatim) -- a
# project-OWNED setting, never the shipped legacy default this AC pair
# removes / must not leak back in.
PROJECT_OWNED_ADDRESS = "postgresql://app:app@db.internal:5432/app_test"


def make_tmp_dir(prefix: str) -> Path:
    """Fresh temp directory (never a project subdirectory --
    ``unit_tests/README.md`` output rules)."""
    return Path(tempfile.mkdtemp(prefix=prefix))


def write_bare_project(prefix: str) -> Path:
    """A genuinely fresh install: a temp project root with NO
    ``.claude/skills_config.json`` at all -- the strongest form of "whose
    own settings do not mention a test database" (INF-1100d-1's own
    criteria text and title: "a fresh install carries no test database
    address")."""
    return make_tmp_dir(prefix)


def write_project_config(prefix: str, config: dict[str, Any]) -> tuple[Path, Path]:
    """Write a REAL ``.claude/skills_config.json`` (via ``json.dump``,
    never a hand-typed literal) for a temp 'adopter project' and return
    ``(project_root, config_file_path)``.
    """
    project_root = make_tmp_dir(prefix)
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    config_path = claude_dir / "skills_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return project_root, config_path


def resolved_db_setting(target_root: Path) -> Any:
    """Call the REAL settings resolver (``config_loader.load_config``) and
    return the resolved ``testing_context.db_connection_test`` value
    (whatever shape it takes -- a missing key resolves to ``None`` via
    ``.get()``)."""
    resolved = config_loader.load_config(None, target_root)
    return resolved.get("testing_context.db_connection_test")


def run_settings_migration(config_path: Path | None, target_root: Path) -> None:
    """Call the REAL upgrade settings-migration step
    (``build.py``'s ``_migrate_skills_config``) in-process -- never a
    ``build.py`` subprocess spawn (CLAUDE.md "Tests must not spawn their
    own build.py"; both ACs' it_requirements name this exact in-process
    call)."""
    build._migrate_skills_config(config_path, target_root, False)
