"""
MODULE: unit_tests/build_guards/_bp1500h_driver.py
GOAL: Run the three build steps that read a file-location setting, in the
    build's own order, in ONE fresh process, against a real scratch project.
ARCHITECTURE: Test-only support script (never collected). Invoked as
    ``python _bp1500h_driver.py <package_root> <target_root>``. It uses the
    REAL ``config_loader.load_config`` (merges the shipped defaults under the
    project's real ``.claude/skills_config.json``), then the real
    ``build_config_scaffolds`` phase, the real staleness step
    (``build_helpers._compute_output_mappings``) and the real
    ``check_referential_integrity``. A fresh process per scenario is
    deliberate: BP-1500h-1-ii's "said once" state is process-local, so
    scenarios must not share a process. Prints the steps' own output, then
    one ``__RESULT__{json}`` line.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    """Run the three steps; print their output and a JSON result line."""
    package_root = Path(argv[1]).resolve()
    target_root = Path(argv[2]).resolve()
    sys.path.insert(0, str(package_root / "scripts"))

    from build_config_scaffolds import build_config_scaffolds
    from build_helpers import _compute_output_mappings
    from build_referential_integrity import check_referential_integrity
    from config_loader import load_config

    config = load_config(None, target_root)
    scaffolded = build_config_scaffolds(target_root, config, False, False)
    mappings = _compute_output_mappings(package_root, target_root, config)
    integrity = check_referential_integrity(target_root, config)
    result = {
        "scaffolded": scaffolded,
        "mapping_keys": sorted(mappings),
        "integrity": integrity,
    }
    print("__RESULT__" + json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
