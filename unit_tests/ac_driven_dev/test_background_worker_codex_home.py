"""Isolated helper homes and opt-in real sandbox smoke without model inference."""

import os
from pathlib import Path
import sys

import pytest

from scripts.background_worker import codex_home
from scripts.background_worker.execution_boundary import ExecutorError


@pytest.fixture
def private_home(tmp_path, monkeypatch):
    home = tmp_path / "user"
    home.mkdir()
    monkeypatch.setattr(codex_home.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(codex_home.tempfile, "gettempdir", lambda: str(tmp_path / "system-temp"))
    return home


def test_isolated_home_uses_private_cache_without_inheriting_profile(private_home):
    # covers: ACD-1300g-1, ACD-1300b-1
    original = private_home / ".codex"
    original.mkdir()
    (original / "auth.json").write_text("private-auth")
    (original / "config.toml").write_text("host-profile")
    with codex_home.isolated_codex_home() as value:
        path = Path(value)
        assert path.parent == private_home / ".cache/leafcutter-worker/codex-homes"
        assert list(path.iterdir()) == []
        if os.name != "nt":
            assert path.stat().st_mode & 0o077 == 0
        (path / "config.toml").write_text("temporary")
    assert not path.exists()
    assert (original / "auth.json").read_text() == "private-auth"


def test_isolated_home_cleans_up_after_failed_call(private_home):
    # covers: ACD-1300g-1-i
    with pytest.raises(RuntimeError, match="call failed"):
        with codex_home.isolated_codex_home() as value:
            path = Path(value)
            raise RuntimeError("call failed")
    assert not path.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX ownership/mode contract")
def test_writable_by_others_cache_is_rejected(private_home):
    # covers: ACD-1300b-1-i
    cache = private_home / ".cache"
    cache.mkdir(mode=0o777)
    cache.chmod(0o777)
    with pytest.raises(ExecutorError, match="not writable by other"):
        with codex_home.isolated_codex_home():
            pytest.fail("Unsafe cache admitted")


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink contract")
def test_symlink_cache_is_rejected(private_home, tmp_path):
    # covers: ACD-1300b-1-i
    target = tmp_path / "other-cache"
    target.mkdir()
    (private_home / ".cache").symlink_to(target, target_is_directory=True)
    with pytest.raises(ExecutorError, match="symlinks"):
        with codex_home.isolated_codex_home():
            pytest.fail("Redirected cache admitted")
    assert not list(target.iterdir())


@pytest.mark.skipif(os.environ.get("LEAFCUTTER_TEST_REAL_SANDBOX") != "1" or not sys.platform.startswith("linux"),
                    reason="Explicit non-inference Linux sandbox probe opt-in required")
@pytest.mark.parametrize("with_runtime", [False, True])
def test_real_cache_home_keeps_sandbox_and_removes_helper_warning(tmp_path, with_runtime):
    # covers: ACD-1300b-1, ACD-1300g-1
    from scripts.background_worker.executors import LocalCodexExecutor

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("sentinel")
    runtime = workspace / ".leafcutter/scripts"
    if with_runtime:
        runtime.mkdir(parents=True)
        (runtime / "guard.py").write_text("trusted")
    probe = """from pathlib import Path
p=Path.cwd()
(p/'inside').write_text('allowed')
if (p/'.leafcutter/scripts/guard.py').exists():
    try: (p/'.leafcutter/scripts/guard.py').write_text('changed')
    except OSError: pass
    else: raise RuntimeError('trusted runtime write permitted')
try: (p.parent/'outside').read_text()
except (PermissionError, FileNotFoundError): pass
else: raise RuntimeError('outside read permitted')
for name in ('outside','escaped'):
    try: (p.parent/name).write_text('forbidden')
    except OSError: pass
"""
    result = LocalCodexExecutor({"model": "not-invoked"}).check(
        workspace, [sys.executable, "-c", probe], timeout=30)
    assert "Refusing to create helper binaries" not in result.stderr
    assert outside.read_text() == "sentinel" and not (tmp_path / "escaped").exists()
    assert (workspace / "inside").read_text() == "allowed"
    if with_runtime:
        assert (runtime / "guard.py").read_text() == "trusted"
