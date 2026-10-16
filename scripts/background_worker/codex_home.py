"""Fresh private Codex homes outside OS temporary directories for helper binaries."""

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from .execution_boundary import ExecutorError


def _private_cache():
    home = Path.home()
    root = home / ".cache" / "leafcutter-worker" / "codex-homes"
    temporary = Path(tempfile.gettempdir()).resolve()
    if os.name != "nt" and (root.resolve() == temporary or temporary in root.resolve().parents):
        raise ExecutorError("Private Codex cache must be outside the OS temporary directory")
    for directory in (home, home / ".cache", root.parent, root):
        if directory.is_symlink():
            raise ExecutorError("Private Codex cache cannot traverse symlinks")
        directory.mkdir(mode=0o700, exist_ok=True)
        info = directory.stat()
        if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o022):
            raise ExecutorError("Private Codex cache must be user-owned and not writable by other users")
    return root


@contextmanager
def isolated_codex_home(prefix="call-"):
    """Never copy existing Codex configuration or authentication into the new home."""
    try:
        with tempfile.TemporaryDirectory(prefix=prefix, dir=_private_cache()) as home:
            yield home
    except OSError as exc:
        raise ExecutorError("Cannot establish or clean private Codex runtime home") from exc
