"""
Behavioral regression for GAP 1 (new-entity admission to entity_registry).

The product-truth validator gates every flow/mock/mockup entity on
index.json's authoritative `entity_registry` and HARD-ERRORS on any entity
missing from it (validate_product_truth.py:442-447). mock-data-author.md now
tells the agent to ADMIT a genuinely-new entity to that array itself. The
prompt itself cannot be harness-driven, but its load-bearing MECHANISM can:
an unregistered entity must fail validation, and admitting it to
`entity_registry` must clear that specific error.

Real-artifact: runs the ACTUAL validator against a copy of the REAL store
(per the repo's real-artifact spot-check policy), not a hand-built fixture.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STORE_SRC = _REPO_ROOT / "docs" / "product-truth"
_NEW_ENTITY = "WidgetXyz"
_FLOW_REL = ("flows", "fern-and-fig", "customer-buys-a-plant.flow.json")
_EXPECTED_ERR = (
    f"entity '{_NEW_ENTITY}' (in fern-and-fig/customer-buys-a-plant) "
    "missing from entity_registry"
)


class TestEntityRegistryAdmissionMechanism(unittest.TestCase):
    def _run_validator(self, store: Path) -> str:
        proc = subprocess.run(
            [sys.executable, str(store / "scripts" / "validate_product_truth.py")],
            capture_output=True,
            text=True,
            timeout=90,
        )
        return proc.stdout + proc.stderr

    def test_unregistered_entity_errors_then_registry_admission_clears_it(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = Path(td) / "product-truth"
            shutil.copytree(_STORE_SRC, store)

            # Inject a genuinely-new entity into a real flow's `entities` list.
            flow_path = store.joinpath(*_FLOW_REL)
            flow = json.loads(flow_path.read_text(encoding="utf-8"))
            self.assertIsInstance(flow.get("entities"), list)
            self.assertNotIn(_NEW_ENTITY, flow["entities"])
            flow["entities"].append(_NEW_ENTITY)
            flow_path.write_text(json.dumps(flow, indent=2), encoding="utf-8")

            # 1) Before admission: the validator flags the unregistered entity.
            before = self._run_validator(store)
            self.assertIn(
                _EXPECTED_ERR,
                before,
                "validator must hard-error on an entity absent from entity_registry",
            )

            # 2) Admit the entity to the authoritative registry — the exact edit
            #    mock-data-author.md now instructs the agent to make.
            index_path = store / "index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertIn("entity_registry", index)
            self.assertNotIn(_NEW_ENTITY, index["entity_registry"])
            index["entity_registry"].append(_NEW_ENTITY)
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

            # 3) After admission: that specific error is gone.
            after = self._run_validator(store)
            self.assertNotIn(
                _EXPECTED_ERR,
                after,
                "admitting the entity to entity_registry must clear the error",
            )


if __name__ == "__main__":
    unittest.main()
