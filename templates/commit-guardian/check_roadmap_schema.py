"""
MODULE: check_roadmap_schema.py
GOAL: Pre-commit hook that validates docs/roadmap.json against its JSON Schema.
    Exits non-zero (blocks commit) when validation fails.
BUSINESS CONTEXT: docs/roadmap.json is the machine-readable plan-of-record for the project.
    Ensuring schema compliance at commit time prevents invalid roadmap content from landing
    on any branch, protecting downstream tooling (roadmap_query.py, ticket_frontmatter_guard.py)
    that reads the file at runtime.
ARCHITECTURE: Reads the schema from leafcutter/config/roadmap.schema.json.
    Fail-open: exits 0 with a warning when the schema file is absent, git is unavailable,
    or any unexpected error occurs. Only fires when docs/roadmap.json is staged.
    Decision rationale: ADR-034-roadmap-json-format-and-schema-design.md.

Pre-commit hook contract:
- Exit 0 = pass (commit proceeds).
- Exit 1 = fail (commit blocked); descriptive error printed to stderr.
- Fail-open on any script error (exits 0 with warning).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCHEMA_RELATIVE = "leafcutter/config/roadmap.schema.json"
try:
    from scripts.commit_guardian.config import DOC_FM_DOCS_DIR as _DOCS_DIR
except ImportError:
    _DOCS_DIR = "docs"
ROADMAP_RELATIVE = f"{_DOCS_DIR}/roadmap.json"


def _is_roadmap_staged() -> bool:
    """Return True iff roadmap.json is in the staged diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        staged = result.stdout.splitlines()
        return any(p.endswith("/roadmap.json") or p == ROADMAP_RELATIVE for p in staged)
    except Exception:
        return False


def _find_root() -> Path | None:
    """Return the git worktree root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def main() -> None:
    """Validate staged docs/roadmap.json against its JSON Schema."""
    try:
        if not _is_roadmap_staged():
            sys.exit(0)

        root = _find_root()
        if root is None:
            print("check_roadmap_schema: advisory — could not locate git root; skipping.", file=sys.stderr)
            sys.exit(0)

        schema_path = root / SCHEMA_RELATIVE
        roadmap_path = root / ROADMAP_RELATIVE

        if not schema_path.exists():
            print(
                f"check_roadmap_schema: advisory — schema not found at {schema_path}; skipping.",
                file=sys.stderr,
            )
            sys.exit(0)

        if not roadmap_path.exists():
            print(
                f"check_roadmap_schema: advisory — roadmap not found at {roadmap_path}; skipping.",
                file=sys.stderr,
            )
            sys.exit(0)

        try:
            with open(schema_path, encoding="utf-8") as f:
                schema = json.load(f)
            with open(roadmap_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"check_roadmap_schema: ERROR — JSON parse failure: {exc}", file=sys.stderr)
            sys.exit(1)

        # Validate using jsonschema if available; manual checks as fallback.
        try:
            import jsonschema  # type: ignore[import]
            try:
                jsonschema.validate(data, schema)
                sys.exit(0)
            except jsonschema.ValidationError as exc:
                print(
                    f"check_roadmap_schema: FAIL — docs/roadmap.json violates schema.\n"
                    f"  Issue: {exc.message}\n"
                    f"  Path:  {' -> '.join(str(p) for p in exc.absolute_path) or '(root)'}\n"
                    f"  Fix the roadmap and re-stage before committing.",
                    file=sys.stderr,
                )
                sys.exit(1)
        except ImportError:
            _manual_validate_or_exit(data)

    except Exception as exc:
        # Fail-open.
        print(f"check_roadmap_schema: advisory — unexpected error ({exc}); skipping.", file=sys.stderr)
        sys.exit(0)


def _manual_validate_or_exit(data: dict) -> None:
    """Minimal validation when jsonschema is unavailable.

    Args:
        data: Parsed contents of docs/roadmap.json to validate.
    """
    required_top = ["phases", "current_phase", "current_outcome"]
    for field in required_top:
        if field not in data:
            print(
                f"check_roadmap_schema: FAIL — docs/roadmap.json missing required field: '{field}'.",
                file=sys.stderr,
            )
            sys.exit(1)

    if not isinstance(data["phases"], list) or len(data["phases"]) == 0:
        print("check_roadmap_schema: FAIL — 'phases' must be a non-empty array.", file=sys.stderr)
        sys.exit(1)

    phase_ids = []
    for phase in data["phases"]:
        for req in ["id", "title", "exit_criteria", "tickets_advancing_outcome"]:
            if req not in phase:
                print(f"check_roadmap_schema: FAIL — phase entry missing '{req}'.", file=sys.stderr)
                sys.exit(1)
        phase_ids.append(phase["id"])

    if data["current_phase"] not in phase_ids:
        print(
            f"check_roadmap_schema: FAIL — 'current_phase' value '{data['current_phase']}' "
            f"not found in phases[*].id: {phase_ids}.",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-18 10:25 [python-coder]: Initial creation. Blocking pre-commit (#TICKETLESS reason=standalone-agent-note)
#   hook that validates docs/roadmap.json against roadmap.schema.json when
#   that file is staged. Exits 1 on schema failure; exits 0 (fail-open) on
#   all error paths (absent schema, git unavailable, unexpected exceptions).
#   Registered in leafcutter/scripts/commit_guardian/commit_guardian.json
#   hooks_manifest under id "check-roadmap-schema".
#   ADR: docs/architecture/adrs/ADR-034-roadmap-json-format-and-schema-design.md
# ====================================================================
