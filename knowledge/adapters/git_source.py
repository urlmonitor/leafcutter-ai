"""MODULE: git_source
GOAL: Read immutable Git source without consulting the dirty worktree.
BUSINESS CONTEXT: Evidence must cite the revision that produced its generation.
ARCHITECTURE: Source adapter shared by projection and disclosure; no kernel imports.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Treat snapshots as data, not executable loaders. (#TICKET-KM-400a-1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from knowledge.contracts import SourceReference

import asyncio
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
from contextlib import contextmanager


def git(root: Path, *arguments: str) -> bytes:
    """Run Git without a shell and return bytes or an explicit source error.

    Args:
        root: Repository directory containing the canonical source data.
        arguments: Git subcommand and arguments passed as separate process values.

    Returns:
        Selected immutable source bytes.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments], capture_output=True, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("Git source process could not complete") from error
    if result.returncode:
        raise ValueError(
            "Git source operation failed: " + result.stderr.decode("utf-8", "replace")[:500]
        )
    return result.stdout


def resolve_revision(root: Path, revision: str) -> str:
    """Resolve a caller-selected ref once to an immutable commit identity.

    Args:
        root: Repository directory containing the canonical source data.
        revision: Git revision resolved once to an immutable commit.

    Returns:
        Resolved canonical text value.
    """
    if not revision or revision.startswith("-"):
        raise ValueError("invalid revision")
    return (
        git(root, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}")
        .decode()
        .strip()
    )


def safe_path(value: str) -> str:
    """Reject absolute, traversal, control-character and platform-specific paths.

    Args:
        value: Value to validate without changing canonical identity.

    Returns:
        Resolved canonical text value.
    """
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or ":" in value
        or "\x00" in value
    ):
        raise ValueError("source path must stay inside the repository")
    return path.as_posix()


@contextmanager
def immutable_checkout(root: Path, sha: str) -> Iterator[Path]:
    """Materialize regular Git files into an isolated temporary data directory.

    Args:
        root: Repository directory containing the canonical source data.
        sha: Immutable source commit SHA.

    Returns:
        Temporary checkout path, removed when the context exits.
    """
    archive = git(root, "archive", "--format=tar", sha)
    with tempfile.TemporaryDirectory(prefix="leafcutter-knowledge-") as directory:
        target = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
            for member in contents:
                if not member.isfile():
                    continue
                destination = target / safe_path(member.name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                stream = contents.extractfile(member)
                if stream is not None:
                    destination.write_bytes(stream.read())
        yield target


class GitSourceResolver:
    """Resolve exact Git source for one configured trusted repository."""

    def __init__(self, root: str | Path, repository_id: str | None = None) -> None:
        """Bind the source root and optional authorized repository identity.

        Args:
            root: Repository directory used for immutable Git object reads.
            repository_id: Optional authorized namespace checked before each read.
        """
        self.root = Path(root).resolve()
        self.repository_id = repository_id

    async def read(self, reference: SourceReference, max_bytes: int) -> str:
        """Read a bounded UTF-8 excerpt from the exact source commit.

        Args:
            reference: Revision-pinned source path, locator and whole-file hash.
            max_bytes: Maximum UTF-8 byte count returned for the selected source excerpt.

        Returns:
            Resolved canonical text value.
        """
        if max_bytes < 0:
            raise ValueError("max_bytes must be nonnegative")
        if self.repository_id is not None and reference.repository_id != self.repository_id:
            raise ValueError("repository scope mismatch")
        path = safe_path(reference.path)
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", reference.source_sha):
            raise ValueError("source SHA must be an immutable commit")
        process = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(self.root),
            "show",
            reference.source_sha + ":" + path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            payload, errors = await asyncio.wait_for(process.communicate(), timeout=10)
        except (asyncio.CancelledError, TimeoutError):
            process.kill()
            await process.wait()
            raise
        if process.returncode:
            raise ValueError(
                "source content unavailable: " + errors.decode("utf-8", "replace")[:200]
            )
        if reference.content_hash and hashlib.sha256(payload).hexdigest() != reference.content_hash:
            raise ValueError("source content hash mismatch")
        from knowledge.adapters.source_excerpt import excerpt

        return excerpt(payload, reference.locator)[:max_bytes].decode("utf-8", "ignore")
