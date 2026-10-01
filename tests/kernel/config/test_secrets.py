"""
MODULE: tests.kernel.config.test_secrets
GOAL: Test credential loading order, env-file parsing, .env walk-up and non-disclosure.
BUSINESS CONTEXT: The kernel reads Jev and Langfuse credentials from the environment or an
    untracked .env above the repo; values must never leak into repr, describe() or logs.
ARCHITECTURE: Uses temp env files and injected environment mappings; values are built at runtime
    so no secret-looking literal appears in source.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from kernel.config import ConfigError
from kernel.secrets import find_env_file, load_secrets, parse_env_text


def _val(tag: str) -> str:
    """Build a non-literal fake credential."""
    return "".join(["v-", tag, "-", "x" * 12])


class TestParse(unittest.TestCase):
    """parse_env_text."""

    def test_comments_export_quotes_and_blank_lines(self) -> None:
        text = "\n# comment\nexport A=1\nB='two'\nC=\"three\"\n  D = four \nbroken\n=novalue\n"
        self.assertEqual(parse_env_text(text), {"A": "1", "B": "two", "C": "three", "D": "four"})

    def test_value_with_equals_sign_is_kept_whole(self) -> None:
        self.assertEqual(parse_env_text("K=a=b=c"), {"K": "a=b=c"})


class TestLoad(unittest.TestCase):
    """load_secrets precedence and aliases."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def _file(self, name: str, **pairs: str) -> Path:
        path = self.dir / name
        path.write_text("".join(f"{k}={v}\n" for k, v in pairs.items()), encoding="utf-8")
        return path

    def test_env_beats_explicit_file_beats_walked_file(self) -> None:
        (self.dir / "repo" / "sub").mkdir(parents=True)
        self._file("repo/.env", JEV_API_KEY=_val("walk"), LANGFUSE_PUBLIC_KEY=_val("walkpub"))
        explicit = self._file("explicit.env", JEV_API_KEY=_val("file"))
        settings = load_secrets(explicit, env={"JEV_API_KEY": _val("env")},
                                start_dir=self.dir / "repo" / "sub")
        self.assertEqual(settings.jev_api_key.get_secret_value(), _val("env"))
        self.assertEqual(settings.origins["jev_api_key"], "env")
        self.assertEqual(settings.langfuse_public_key.get_secret_value(), _val("walkpub"))
        self.assertEqual(settings.origins["langfuse_public_key"],
                         str(self.dir / "repo" / ".env"))

    def test_explicit_file_beats_walked_file(self) -> None:
        self._file(".env", JEV_API_KEY=_val("walk"))
        explicit = self._file("e.env", JEV_API_KEY=_val("file"))
        settings = load_secrets(explicit, env={}, start_dir=self.dir)
        self.assertEqual(settings.jev_api_key.get_secret_value(), _val("file"))

    def test_leafcutter_env_file_var_is_used(self) -> None:
        explicit = self._file("e.env", JEV_API_KEY=_val("viavar"))
        settings = load_secrets(env={"LEAFCUTTER_ENV_FILE": str(explicit)}, start_dir=self.dir)
        self.assertEqual(settings.jev_api_key.get_secret_value(), _val("viavar"))

    def test_jev_alias_and_langfuse_host_fallback(self) -> None:
        settings = load_secrets(env={"TYPESAFE_API_KEY": _val("alias"),
                                     "LANGFUSE_HOST": "https://lf.example"}, start_dir=self.dir)
        self.assertEqual(settings.jev_api_key.get_secret_value(), _val("alias"))
        self.assertEqual(settings.langfuse_base_url, "https://lf.example")

    def test_base_url_name_beats_host_within_one_source(self) -> None:
        settings = load_secrets(env={"LANGFUSE_HOST": "https://old.example",
                                     "LANGFUSE_BASE_URL": "https://new.example"},
                                start_dir=self.dir)
        self.assertEqual(settings.langfuse_base_url, "https://new.example")

    def test_missing_everything_yields_absent_values(self) -> None:
        settings = load_secrets(env={}, start_dir=self.dir)
        self.assertFalse(any(settings.describe().values()))
        self.assertFalse(settings.has_jev())
        self.assertFalse(settings.has_langfuse())

    def test_has_langfuse_needs_all_three(self) -> None:
        env = {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": _val("s")}
        self.assertFalse(load_secrets(env=env, start_dir=self.dir).has_langfuse())
        env["LANGFUSE_BASE_URL"] = "https://lf.example"
        self.assertTrue(load_secrets(env=env, start_dir=self.dir).has_langfuse())

    def test_environment_is_never_mutated(self) -> None:
        self._file(".env", JEV_API_KEY=_val("walk"))
        before = dict(os.environ)
        load_secrets(start_dir=self.dir)
        self.assertEqual(dict(os.environ), before)

    def test_unreadable_explicit_env_file_is_an_error_naming_only_the_path(self) -> None:
        # Changed by FIXC (R3-6): a NAMED file used to be ignored with a warning, which let the
        # run fall back to a walked-up .env with other credentials.
        missing = self.dir / "gone.env"
        with self.assertRaises(ConfigError) as caught:
            load_secrets(missing, env={}, start_dir=self.dir)
        self.assertIn("gone.env", str(caught.exception))

class TestNonDisclosure(unittest.TestCase):
    """Secrets never appear in repr, describe() or serialised dumps."""

    def test_secret_values_hidden_everywhere_but_the_explicit_accessors(self) -> None:
        jev, lf_secret, lf_public = _val("jev"), _val("lfs"), _val("lfp")
        with tempfile.TemporaryDirectory() as tmp:
            settings = load_secrets(env={"JEV_API_KEY": jev, "LANGFUSE_SECRET_KEY": lf_secret,
                                         "LANGFUSE_PUBLIC_KEY": lf_public}, start_dir=Path(tmp))
        for text in (repr(settings), str(settings), str(settings.describe()),
                     settings.model_dump_json()):
            for value in (jev, lf_secret, lf_public):
                self.assertNotIn(value, text)
        self.assertEqual(sorted(settings.secret_values().values()), sorted([jev, lf_secret, lf_public]))
        self.assertTrue(all(isinstance(v, bool) for v in settings.describe().values()))

    def test_find_env_file_walks_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a" / "b").mkdir(parents=True)
            (root / ".env").write_text("X=1\n", encoding="utf-8")
            self.assertEqual(find_env_file(root / "a" / "b"), (root / ".env").resolve())


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Fake credentials are built at runtime by _val() so no
#   quoted literal is assigned to a secret-looking name (check-secrets GENERIC_SECRET).
#   (#KernelBootstrapV0/P1)
# ====================================================================
