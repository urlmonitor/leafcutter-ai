"""
MODULE: tests.kernel.config.test_config
GOAL: Test kernel configuration loading, merging, validation and the committed JSON Schema.
BUSINESS CONTEXT: Every threshold and limit lives in config/kernel_config.default.json; a typo or
    an out-of-range override must fail loudly, and the schema file clients read must match the
    model.
ARCHITECTURE: Real default file; overrides are written to a temp dir as JSON.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from kernel.config import (
    ConfigError,
    KernelConfig,
    deep_merge,
    default_config_path,
    kernel_config_schema,
    load_kernel_config,
)
from kernel.contracts.enums import EvidenceCategory

REPO = Path(__file__).resolve().parents[3]


class TestDefaults(unittest.TestCase):
    """The committed defaults."""

    def test_default_values_match_design(self) -> None:
        cfg = load_kernel_config(env={})
        self.assertEqual((cfg.limits.max_work_items, cfg.limits.max_depth,
                          cfg.limits.max_concurrent_host), (32, 4, 1))
        self.assertEqual(cfg.routing.min_selected_probability, 0.8)
        self.assertIsNone(cfg.limits.max_cost_usd)
        self.assertEqual(cfg.paths.run_root, ".leafcutter/kernel")
        self.assertEqual(cfg.jev.model, "jev-latest")

    def test_every_category_described_and_sources_unique(self) -> None:
        cfg = load_kernel_config(env={})
        self.assertEqual(set(cfg.research.category_descriptions), set(EvidenceCategory))
        ids = [s.id for s in cfg.sources]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("host.research", ids)

    def test_models_carry_no_defaults_so_json_is_the_only_source(self) -> None:
        for name, section in KernelConfig.model_fields.items():
            model = section.annotation
            if not hasattr(model, "model_fields") or name == "sources":
                continue
            for field, info in model.model_fields.items():
                with self.subTest(section=name, field=field):
                    self.assertTrue(info.is_required(), f"{name}.{field} has a code default")

    def test_committed_schema_matches_model_and_validates_default(self) -> None:
        committed = json.loads((REPO / "config" / "kernel_config.schema.json")
                               .read_text(encoding="utf-8"))
        self.assertEqual(committed, kernel_config_schema())
        default = json.loads(default_config_path().read_text(encoding="utf-8"))
        default.pop("$schema")
        Draft202012Validator(committed).validate(default)


class TestOverride(unittest.TestCase):
    """Override merging and validation."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def _write(self, data: object, name: str = "override.json") -> Path:
        path = self.dir / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_deep_merge_replaces_leaves_and_keeps_siblings(self) -> None:
        cfg = load_kernel_config(self._write({"limits": {"max_depth": 9}}), env={})
        self.assertEqual(cfg.limits.max_depth, 9)
        self.assertEqual(cfg.limits.max_work_items, 32)

    def test_env_var_selects_override(self) -> None:
        path = self._write({"routing": {"min_confidence": 0.6}})
        cfg = load_kernel_config(env={"LEAFCUTTER_KERNEL_CONFIG": str(path)})
        self.assertEqual(cfg.routing.min_confidence, 0.6)

    def test_explicit_override_beats_env(self) -> None:
        env_file = self._write({"limits": {"max_depth": 2}}, "env.json")
        arg_file = self._write({"limits": {"max_depth": 3}}, "arg.json")
        cfg = load_kernel_config(arg_file, env={"LEAFCUTTER_KERNEL_CONFIG": str(env_file)})
        self.assertEqual(cfg.limits.max_depth, 3)

    def test_invalid_overrides_raise_config_error(self) -> None:
        for bad in ({"routing": {"min_confidence": 1.5}}, {"limits": {"max_depth": 0}},
                    {"limits": {"unknown_key": 1}}, {"surprise": 1},
                    {"data_policy": {"telemetry_excerpts": "all"}}):
            with self.subTest(override=bad), self.assertRaises(ConfigError):
                load_kernel_config(self._write(bad), env={})

    def test_thresholds_must_be_ordered(self) -> None:
        bad = {"research": {"need_supporting_threshold": 0.9, "need_required_threshold": 0.5}}
        with self.assertRaises(ConfigError):
            load_kernel_config(self._write(bad), env={})

    def test_missing_or_malformed_override(self) -> None:
        with self.assertRaises(ConfigError):
            load_kernel_config(self.dir / "absent.json", env={})
        broken = self.dir / "broken.json"
        broken.write_text("{oops", encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_kernel_config(broken, env={})

    def test_config_is_frozen(self) -> None:
        cfg = load_kernel_config(env={})
        with self.assertRaises(ValueError):
            cfg.limits.max_depth = 1

    def test_deep_merge_does_not_mutate_inputs(self) -> None:
        base = {"a": {"b": 1}}
        merged = deep_merge(base, {"a": {"c": 2}})
        self.assertEqual((base, merged), ({"a": {"b": 1}}, {"a": {"b": 1, "c": 2}}))


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: test_models_carry_no_defaults guards the rule that no
#   numeric threshold has a code-level default. (#KernelBootstrapV0/P1)
# ====================================================================
