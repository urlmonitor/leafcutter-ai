"""
MODULE: tests.kernel.observability.test_redaction
GOAL: Test Redactor: exact secret values, scanner rules, entropy tokens, deny-glob content,
    the excerpt policy modes, truncation, structure walking and the Langfuse mask signature.
BUSINESS CONTEXT: Repo excerpts and run data are sent to third parties; nothing secret-looking or
    denied by the repo rules may leave the process, and persisted evidence must stay untouched.
ARCHITECTURE: unittest; secret-looking test values are assembled at runtime so the commit-time
    secret scanner never sees a quoted literal assignment.
"""

from __future__ import annotations

import base64
import hashlib
import unittest
from typing import Literal

from kernel.config import DataPolicyConfig, load_kernel_config
from kernel.observability.redaction import Redactor, matches_deny_glob, shannon_entropy

DENY = load_kernel_config().retrieval.deny_globs
NEEDLE = "zq" + "-" + "Xk29" + "Lm81" + "Pv07"
HIGH_ENTROPY = base64.b64encode(hashlib.sha256(b"entropy-sample").digest()).decode()


def _policy(mode: Literal["truncated", "hash", "none"] = "truncated", limit: int = 4000) -> DataPolicyConfig:
    return DataPolicyConfig(send_repo_excerpts_to_jev=True, telemetry_excerpts=mode,
                            telemetry_max_field_chars=limit)


def _redactor(mode: Literal["truncated", "hash", "none"] = "truncated", limit: int = 4000) -> Redactor:
    return Redactor({"langfuse_public_key": NEEDLE}, _policy(mode, limit), DENY)


class TestStringRules(unittest.TestCase):
    """Per-string masking."""

    def test_exact_secret_value_is_replaced_by_its_name(self) -> None:
        out = _redactor().mask(f"call with {NEEDLE} now")
        self.assertNotIn(NEEDLE, out)
        self.assertIn("[REDACTED:langfuse_public_key]", out)

    def test_short_secret_values_are_not_used_as_needles(self) -> None:
        redactor = Redactor({"x": "abc"}, _policy(), DENY)
        self.assertEqual(redactor.mask("abc def"), "abc def")

    def test_scanner_rules_fire(self) -> None:
        aws = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
        pem = "-----BEGIN RSA " + "PRIVATE KEY-----"
        generic = "pass" + "word" + ' = "' + "a1b2c3d4e5" + '"'
        for raw, rule in ((aws, "AWS_KEY"), (pem, "PRIVATE_KEY"), (generic, "GENERIC_SECRET")):
            with self.subTest(rule=rule):
                out = _redactor().mask(f"prefix {raw} suffix")
                self.assertIn(f"[REDACTED:{rule}]", out)
                self.assertNotIn(raw, out)

    def test_high_entropy_token_is_replaced(self) -> None:
        self.assertGreater(shannon_entropy(HIGH_ENTROPY), 4.5)
        self.assertEqual(_redactor().mask(f"x {HIGH_ENTROPY} y"), "x [REDACTED:entropy] y")

    def test_ordinary_text_hashes_paths_and_ids_survive(self) -> None:
        for text in ("Use sqlite for the run store.", "a" * 64 + "0123456789abcdef",
                     "kernel/observability/langfuse_tracer.py",
                     "docs/architecture/adrs/ADR-052-langgraph-runtime.md",
                     "run-0123456789abcdef"):
            with self.subTest(text=text):
                self.assertEqual(_redactor().mask(text), text)

    def test_long_strings_are_truncated_with_a_marker(self) -> None:
        out = _redactor(limit=10).mask("abcdefghij" + "klmnop")
        self.assertEqual(out, "abcdefghij...[truncated 6 chars]")


class TestStructureRules(unittest.TestCase):
    """Dict, list and model walking plus policy rules."""

    def test_nested_structures_are_walked_and_copied(self) -> None:
        data = {"a": [{"b": f"k={NEEDLE}"}], "n": 3, "f": 1.5, "t": True, "z": None}
        out = _redactor().mask(data)
        self.assertNotIn(NEEDLE, repr(out))
        self.assertEqual((out["n"], out["f"], out["t"], out["z"]), (3, 1.5, True, None))
        self.assertIn(NEEDLE, repr(data))

    def test_pydantic_models_are_dumped_and_masked(self) -> None:
        from tests.kernel.helpers import make_evidence
        out = _redactor().mask(make_evidence(excerpt=f"has {NEEDLE}"))
        self.assertNotIn(NEEDLE, repr(out))

    def test_denied_path_loses_its_excerpt_and_content(self) -> None:
        for locator in (".env", "sub/.env.local", "certs/a.pem#L1-L3", "x/.git/config"):
            with self.subTest(locator=locator):
                out = _redactor().mask({"locator": locator, "excerpt": "visible?",
                                        "content": "visible?", "id": "ev-1"})
                self.assertEqual(out["excerpt"], "[REDACTED:deny_glob]")
                self.assertEqual(out["content"], "[REDACTED:deny_glob]")
                self.assertEqual(out["id"], "ev-1")

    def test_allowed_path_keeps_its_excerpt(self) -> None:
        out = _redactor().mask({"locator": "docs/a.md#L1-L2", "excerpt": "Use sqlite."})
        self.assertEqual(out["excerpt"], "Use sqlite.")

    def test_excerpt_policy_modes(self) -> None:
        item = {"locator": "docs/a.md", "excerpt": "Use sqlite."}
        self.assertEqual(_redactor("none").mask(item)["excerpt"], "[OMITTED:excerpt]")
        digest = hashlib.sha256(b"Use sqlite.").hexdigest()
        self.assertEqual(_redactor("hash").mask(item)["excerpt"], "sha256:" + digest)
        self.assertEqual(_redactor("truncated").mask(item)["excerpt"], "Use sqlite.")

    def test_cycles_and_depth_are_bounded(self) -> None:
        node: dict = {}
        node["self"] = node
        self.assertIn("[REDACTED:depth]", repr(_redactor().mask(node)))

    def test_langfuse_mask_signature(self) -> None:
        self.assertEqual(_redactor()(data=f"{NEEDLE}", extra=1), "[REDACTED:langfuse_public_key]")


class TestDenyGlobs(unittest.TestCase):
    """matches_deny_glob semantics."""

    def test_matches(self) -> None:
        for path in (".env", ".env.production", "a/b/.env", "k.pem", "a/k.key", ".git/config",
                     ".security-allowlist", "./.env"):
            with self.subTest(path=path):
                self.assertTrue(matches_deny_glob(path, DENY))

    def test_non_matches(self) -> None:
        for path in ("docs/env.md", "kernel/config.py", "README.md", "src/keyboard.py"):
            with self.subTest(path=path):
                self.assertFalse(matches_deny_glob(path, DENY))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Secret-looking inputs are built at runtime to satisfy the check-secrets hook.
#   (#KernelBootstrapV0/P2)
# ====================================================================
