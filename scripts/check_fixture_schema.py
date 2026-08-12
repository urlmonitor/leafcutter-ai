#!/usr/bin/env python3
"""
MODULE: check_fixture_schema
GOAL: Drift-guard schema validation for leafcutter-web/fixtures/ — UXP-554 Part 1.
BUSINESS CONTEXT: Ensures the bundled fixture repo can never silently drift from the
    real data shape by validating every fixture artifact against the SAME validators
    and schemas that govern real data.
ARCHITECTURE: Standalone CI script. Invokes validate_ac_schema.py (real validator)
    for AC YAML files; validates product-truth flow/mock/mockup JSON against the real
    schemas from docs/product-truth/schemas/; does shape checks on roadmap.json,
    components.json, and agent_registry.json. Exits non-zero on any violation.

Usage:
    python scripts/check_fixture_schema.py [--fixtures-root PATH]

    --fixtures-root PATH   Path to the fixture repo root.
                           Default: leafcutter-web/fixtures/ relative to the repo root.
                           Can also be set via LEAFCUTTER_FIXTURE_ROOT env var.

Exits:
    0 — all fixtures pass schema validation
    1 — one or more fixtures fail schema validation
    2 — usage/setup error (missing dependency or fixture dir not found)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print(
        "FAIL: jsonschema is required for fixture drift-guard validation but is not installed. "
        "Install it: pip install 'jsonschema>=4.0' or pip install -r requirements-dev.txt",
        file=sys.stderr,
    )
    sys.exit(2)

try:
    import yaml
except ImportError:
    print(
        "FAIL: PyYAML is required but not installed. "
        "Install it: pip install pyyaml or pip install -r requirements-dev.txt",
        file=sys.stderr,
    )
    sys.exit(2)

logger = logging.getLogger("check_fixture_schema")

_REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict | list | None:
    """Load and parse a JSON file.

    Returns None on any error and logs a warning so callers can skip the file
    without try/except boilerplate. Avoids raising so callers stay TRY-rule clean.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error in %s: %s", path, exc)
        return None
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None


def _load_schema(schema_dir: Path, name: str) -> dict | None:
    """Load a product-truth JSON schema by name, returns None on failure."""
    result = _load_json(schema_dir / name)
    if not isinstance(result, dict):
        logger.warning("Schema %s/%s is not a JSON object", schema_dir, name)
        return None
    return result


def _validate_json_schema(instance: dict, schema: dict, label: str) -> list[str]:
    """Validate one JSON instance against a schema, return list of error strings."""
    errors: list[str] = []
    try:
        jsonschema.validate(instance, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"[schema] {label}: {exc.message}")
    return errors


# ---------------------------------------------------------------------------
# Part A: AC YAML validation via the real validate_ac_schema.py
# ---------------------------------------------------------------------------

def check_ac_yamls(fixture_root: Path) -> list[str]:
    """Validate all fixture AC YAML files by invoking validate_ac_schema.py.

    Returns a list of error strings.
    """
    ac_dir = fixture_root / "docs" / "acceptance-criteria"
    if not ac_dir.is_dir():
        logger.info("No docs/acceptance-criteria/ in fixtures — skipping AC validation")
        return []

    yaml_files = [
        p for p in sorted(ac_dir.rglob("*.yaml"))
        if p.name != "index.yaml"
    ]
    if not yaml_files:
        logger.warning("No AC YAML files found in %s — is the fixture tree populated?", ac_dir)
        return []

    validator = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"
    if not validator.is_file():
        return [f"SETUP: validate_ac_schema.py not found at {validator}"]

    cmd = [sys.executable, str(validator)] + [str(p) for p in yaml_files]
    logger.info("Running: %s ... (%d files)", " ".join(cmd[:2]), len(yaml_files))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return [f"SETUP: Failed to invoke validate_ac_schema.py: {exc}"]

    errors: list[str] = []
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        errors.append(
            f"validate_ac_schema.py failed (exit {result.returncode}) "
            f"on {len(yaml_files)} fixture AC files:\n{output}"
        )
    else:
        logger.info("AC YAML validation: OK (%d files)", len(yaml_files))

    return errors


# ---------------------------------------------------------------------------
# Part B: Product-truth JSON schema validation
# ---------------------------------------------------------------------------

def check_product_truth(fixture_root: Path) -> list[str]:
    """Validate fixture flow/mock/mockup JSON against the real product-truth schemas.

    Reads schemas from docs/product-truth/schemas/ (real, not fixture) and validates
    every *.flow.json, *.mock.json, *.mockup.json found under the fixture tree.
    """
    errors: list[str] = []
    schema_dir = _REPO_ROOT / "docs" / "product-truth" / "schemas"
    if not schema_dir.is_dir():
        return [f"SETUP: product-truth schema dir not found at {schema_dir}"]

    flow_schema = _load_schema(schema_dir, "flow.schema.json")
    mock_schema = _load_schema(schema_dir, "mock-data.schema.json")
    mockup_schema = _load_schema(schema_dir, "mockup.schema.json")

    if any(s is None for s in (flow_schema, mock_schema, mockup_schema)):
        return ["SETUP: one or more product-truth schemas failed to load"]

    pt_root = fixture_root / "docs" / "product-truth"

    # Flows
    flow_files = sorted((pt_root / "flows").rglob("*.flow.json")) if (pt_root / "flows").is_dir() else []
    for path in flow_files:
        doc = _load_json(path)
        if doc is None:
            errors.append(f"{path}: failed to load (JSON parse or I/O error — see log above)")
        elif isinstance(doc, dict):
            errors.extend(_validate_json_schema(doc, flow_schema, f"flow {path}"))  # type: ignore[arg-type]
        else:
            errors.append(f"{path}: expected JSON object, got {type(doc).__name__}")

    # Mock data
    mock_files = sorted((pt_root / "mock-data").rglob("*.mock.json")) if (pt_root / "mock-data").is_dir() else []
    for path in mock_files:
        doc = _load_json(path)
        if doc is None:
            errors.append(f"{path}: failed to load (JSON parse or I/O error — see log above)")
        elif isinstance(doc, dict):
            errors.extend(_validate_json_schema(doc, mock_schema, f"mock {path}"))  # type: ignore[arg-type]
        else:
            errors.append(f"{path}: expected JSON object, got {type(doc).__name__}")

    # Mockups
    mockup_files = sorted((pt_root / "mockups").rglob("*.mockup.json")) if (pt_root / "mockups").is_dir() else []
    for path in mockup_files:
        doc = _load_json(path)
        if doc is None:
            errors.append(f"{path}: failed to load (JSON parse or I/O error — see log above)")
        elif isinstance(doc, dict):
            errors.extend(_validate_json_schema(doc, mockup_schema, f"mockup {path}"))  # type: ignore[arg-type]
        else:
            errors.append(f"{path}: expected JSON object, got {type(doc).__name__}")

    total = len(flow_files) + len(mock_files) + len(mockup_files)
    if total == 0:
        logger.warning("No product-truth JSON files found under %s", pt_root)
    else:
        logger.info("Product-truth schema validation: %d files checked", total)

    return errors


# ---------------------------------------------------------------------------
# Part C: Shape checks for roadmap.json, components.json, agent_registry.json
# ---------------------------------------------------------------------------

def check_json_shapes(fixture_root: Path) -> list[str]:
    """Validate the shapes of JSON files loaded by atlas.ts, roadmap.ts, etc.

    Checks required top-level keys and that lists/dicts are non-empty — enough
    to confirm the loaders will not silently return empty results.
    """
    errors: list[str] = []

    # --- docs/roadmap.json (roadmap.ts) ---
    roadmap_path = fixture_root / "docs" / "roadmap.json"
    if not roadmap_path.is_file():
        errors.append(f"MISSING: {roadmap_path} (required for /roadmap view)")
    else:
        doc = _load_json(roadmap_path)
        if doc is None:
            errors.append(f"{roadmap_path}: failed to load")
        elif not isinstance(doc, dict):
            errors.append(f"{roadmap_path}: expected object, got {type(doc).__name__}")
        else:
            if "current_phase" not in doc:
                errors.append(f"{roadmap_path}: missing required key 'current_phase'")
            phases = doc.get("phases")
            if not isinstance(phases, list) or len(phases) == 0:
                errors.append(f"{roadmap_path}: 'phases' must be a non-empty array")
            else:
                for i, phase in enumerate(phases):
                    for key in ("id", "title", "status"):
                        if key not in phase:
                            errors.append(f"{roadmap_path}: phases[{i}] missing required key '{key}'")

    # --- docs/components.json (components.ts) ---
    components_path = fixture_root / "docs" / "components.json"
    if not components_path.is_file():
        errors.append(f"MISSING: {components_path} (required for /architecture view)")
    else:
        doc = _load_json(components_path)
        if doc is None:
            errors.append(f"{components_path}: failed to load")
        elif not isinstance(doc, dict):
            errors.append(f"{components_path}: expected object, got {type(doc).__name__}")
        else:
            components = doc.get("components")
            if not isinstance(components, dict) or len(components) == 0:
                errors.append(f"{components_path}: 'components' must be a non-empty object")
            else:
                for cid, comp in components.items():
                    if not isinstance(comp, dict) or comp.get("id") != cid:
                        errors.append(
                            f"{components_path}: components['{cid}'] missing 'id' or id != key"
                        )

    # --- config/agent_registry.json (agents.ts) ---
    agents_path = fixture_root / "config" / "agent_registry.json"
    if not agents_path.is_file():
        errors.append(f"MISSING: {agents_path} (required for /pipeline view)")
    else:
        doc = _load_json(agents_path)
        if doc is None:
            errors.append(f"{agents_path}: failed to load")
        elif not isinstance(doc, dict):
            errors.append(f"{agents_path}: expected object, got {type(doc).__name__}")
        else:
            agents = doc.get("agents")
            if not isinstance(agents, list) or len(agents) == 0:
                errors.append(f"{agents_path}: 'agents' must be a non-empty array")
            else:
                for i, agent in enumerate(agents):
                    if "id" not in agent:
                        errors.append(f"{agents_path}: agents[{i}] missing required key 'id'")

    return errors


# ---------------------------------------------------------------------------
# Part D: Fixture AC index.yaml shape check
# ---------------------------------------------------------------------------

def check_ac_index(fixture_root: Path) -> list[str]:
    """Validate the fixture AC store index.yaml structure."""
    errors: list[str] = []
    index_path = fixture_root / "docs" / "acceptance-criteria" / "index.yaml"
    if not index_path.is_file():
        errors.append(f"MISSING: {index_path} (required for AC store loader — loadAcComponents())")
        return errors

    try:
        doc = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"{index_path}: YAML parse error — {exc}"]
    except OSError as exc:
        return [f"{index_path}: cannot read file — {exc}"]

    if not isinstance(doc, dict) or "components" not in doc:
        errors.append(f"{index_path}: expected a dict with top-level 'components' key")
        return errors

    components = doc["components"]
    if not isinstance(components, list) or len(components) == 0:
        errors.append(f"{index_path}: 'components' must be a non-empty list")
    else:
        for i, comp in enumerate(components):
            if "id" not in comp or "prefix" not in comp:
                errors.append(f"{index_path}: components[{i}] missing 'id' or 'prefix'")

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Run all schema validation checks and return exit code."""
    parser = argparse.ArgumentParser(
        description="Drift-guard schema validation for leafcutter-web/fixtures/ (UXP-554 Part 1)."
    )
    parser.add_argument(
        "--fixtures-root",
        default=None,
        help=(
            "Path to the fixture repo root. "
            "Default: leafcutter-web/fixtures/ relative to the repo root. "
            "Also reads LEAFCUTTER_FIXTURE_ROOT env var."
        ),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Resolve fixture root
    fixtures_root_raw = (
        args.fixtures_root
        or os.environ.get("LEAFCUTTER_FIXTURE_ROOT")
        or str(_REPO_ROOT / "leafcutter-web" / "fixtures")
    )
    fixture_root = Path(fixtures_root_raw).resolve()

    if not fixture_root.is_dir():
        logger.error("FAIL: fixture root not found: %s", fixture_root)
        return 2

    logger.info("Drift guard — schema validation against: %s", fixture_root)

    all_errors: list[str] = []

    # A. AC YAML validation
    all_errors.extend(check_ac_yamls(fixture_root))

    # B. Product-truth JSON schema validation
    all_errors.extend(check_product_truth(fixture_root))

    # C. JSON shape checks (roadmap, components, agent_registry)
    all_errors.extend(check_json_shapes(fixture_root))

    # D. AC index.yaml structure
    all_errors.extend(check_ac_index(fixture_root))

    # Report
    if all_errors:
        logger.error("")
        logger.error("FAIL: %d drift-guard schema violation(s):", len(all_errors))
        for i, err in enumerate(all_errors, 1):
            logger.error("  [%d] %s", i, err)
        return 1

    logger.info("")
    logger.info("OK: all fixture schema checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
