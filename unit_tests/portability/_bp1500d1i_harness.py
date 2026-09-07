"""
MODULE: _bp1500d1i_harness
AC: BP-1500d-1-i -- "The record describes the producing end truthfully --
    where the package stood, and which of its files the deployment came
    from -- or says plainly that it cannot"

GOAL: Extends the BP-1500d-1 out-of-package harness with the SAME-DIRECTORY
    layout (layout A) this AC's test_spec requires paired, in ONE session,
    against the existing sibling layout (layout B). Reuses
    ``_bp1500d1_harness.build_out_of_package_harness()`` for layout B rather
    than reimplementing it -- this AC's own it_requirements (#6) makes the
    paired two-layout run the contract, and a second, independent sibling
    harness would risk the two builds drifting apart in a way that makes
    "the same session" untrue in substance even if true in wall-clock time.

LAYOUT A -- GENUINELY THE SAME DIRECTORY, MEASURED 2026-09-07 IN THIS
    WORKTREE: ``build.py`` computes ``package_root =
    Path(__file__).resolve().parent.parent`` from the invoked script's own
    path, so running ``<project>/scripts/build.py --target-dir <project>``
    (the SAME ``<project>`` on both sides) makes ``package_root ==
    target_root`` by construction -- not merely "close" or "nested one level
    under", but the identical directory. Verified live: this build records
    ``package_root: ""`` and 174 unprefixed template-account keys (e.g.
    ``"templates/agents/README.md"``), matching
    ``_relative_package_offset``'s documented meaning for that value.

WHY NOT REUSE THE NESTED READING build_out_of_package_harness() REJECTED:
    that harness's own DECISION HISTORY already establishes that a package
    nested one level under the target (``<scratch>/leafcutter-ai/`` under
    ``<scratch>`` as ``--target-dir``) is a THIRD, distinct layout -- not
    "the same directory" and not the genuine out-of-package sibling either.
    Layout A here is neither of those: there is exactly one directory, used
    as both ``package_root`` and ``target_root`` in the same build.

WHAT THIS MODULE DOES NOT DO: like its sibling, it never imports
    ``build_helpers`` or calls ``write_build_manifest`` directly. Every build
    below is the real
    ``python <project>/scripts/build.py --target-dir <project>``
    command line, run as a subprocess -- the only way to prove the ENTRY
    POINT routes the target, not merely that the already-parameterised
    writer function is capable of it (this AC's own test_rationale, and its
    parent's entry 3).

FIXTURE-VISIBILITY CAVEAT (identical to _bp1500d1_harness.py, restated here
    because this module performs its OWN independent ``git archive HEAD``):
    the package copy this harness builds is frozen at the last COMMIT, never
    the working tree. Every test built on this module reads RED against an
    uncommitted production fix in this same worktree, no matter how correct
    that fix is -- see this AC's own it_requirements #9. Do not diagnose that
    as a broken fix; commit first, then re-run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ._bp1500d1_harness import (
    REAL_PACKAGE_ROOT,
    HarnessBuild,
    _scrubbed_env,
    build_out_of_package_harness,
    hash_file,
)

_MANIFEST_NAME = ".build_manifest.json"

# Manifest keys that are NOT part of the "account of the package's own
# files" (Direction A / ``template_hashes``) this AC's criteria govern.
# ``write_build_manifest`` writes ``manifest = dict(template_hashes)`` and
# then adds these five keys directly onto that same top-level dict -- so the
# template account is every OTHER top-level key. Getting this set wrong once
# already produced a false "0 templates" reading during this AC's own
# authoring (see BP-1500d-1-i's own dispatch note); it is centralised here
# so every test in this module counts the account the same way.
MANIFEST_METADATA_KEYS = frozenset(
    {
        "output_mappings",
        "output_mappings_error",
        "output_mappings_skipped_sections",
        "output_mappings_unwritten",
        "package_root",
    }
)


def template_account_keys(manifest: dict) -> frozenset[str]:
    """Return the manifest's Direction A template-account keys.

    Args:
        manifest: A loaded ``.build_manifest.json`` dict.

    Returns:
        Every top-level key that is NOT one of ``MANIFEST_METADATA_KEYS`` --
        i.e. the flat ``template_hashes`` dict ``write_build_manifest``
        merges directly into the manifest root.
    """
    return frozenset(k for k in manifest if k not in MANIFEST_METADATA_KEYS)


@dataclass
class SameDirectoryBuild:
    """Result of standing up the same-directory (layout A) harness build."""

    scratch_root: Path
    project_root: Path  # package copy AND receiving project: the SAME directory
    proc: subprocess.CompletedProcess
    manifest_path: Path
    _tmp: tempfile.TemporaryDirectory = field(repr=False)

    def cleanup(self) -> None:
        self._tmp.cleanup()

    @property
    def manifest_exists(self) -> bool:
        return self.manifest_path.is_file()

    def load_manifest(self) -> dict:
        raw = self.manifest_path.read_text(encoding="utf-8")
        return json.loads(raw)


def build_same_directory_harness(*, timeout: int = 300) -> SameDirectoryBuild:
    """Stand up a REAL install where the producing package and the
    receiving project are genuinely the same directory, built via the REAL
    ``build.py`` command line (subprocess, not an import).

    Layout: ``<scratch>/leafcutter-ai/`` holds a ``git archive HEAD`` copy of
    the producing package AND is itself the build's ``--target-dir`` -- there
    is no separate receiving-project directory, by construction. This is the
    control layout A entry 1 of this AC's test_spec requires.

    Args:
        timeout: Seconds to allow the build subprocess to run.

    Returns:
        A :class:`SameDirectoryBuild` capturing the build result.
    """
    tmp = tempfile.TemporaryDirectory(prefix="bp1500d1i_samedir_")
    scratch_root = Path(tmp.name)
    project_root = scratch_root / "leafcutter-ai"
    project_root.mkdir(parents=True, exist_ok=True)

    archive_path = scratch_root / "_package_archive.tar"
    try:
        subprocess.run(
            ["git", "-C", str(REAL_PACKAGE_ROOT), "archive", "HEAD", "-o", str(archive_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        tmp.cleanup()
        raise RuntimeError(
            f"git archive failed while building same-directory harness: {exc}"
        ) from exc

    try:
        shutil.unpack_archive(str(archive_path), extract_dir=str(project_root), format="tar")
    finally:
        archive_path.unlink(missing_ok=True)

    build_script = project_root / "scripts" / "build.py"
    argv = [sys.executable, str(build_script), "--target-dir", str(project_root)]
    proc = subprocess.run(
        argv,
        cwd=str(project_root),  # cwd IS the receiving project (and the package, here)
        env=_scrubbed_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    manifest_path = project_root / _MANIFEST_NAME
    return SameDirectoryBuild(
        scratch_root=scratch_root,
        project_root=project_root,
        proc=proc,
        manifest_path=manifest_path,
        _tmp=tmp,
    )


@dataclass
class PairedSession:
    """Both layouts, built in ONE test session (this AC's it_requirements #6:
    'the paired two-layout run is the contract, not a convenience, and it
    must stay inside one session')."""

    same_directory: SameDirectoryBuild
    sibling: HarnessBuild

    def cleanup(self) -> None:
        self.same_directory.cleanup()
        self.sibling.cleanup()


def build_paired_session(*, timeout: int = 300) -> PairedSession:
    """Stand up BOTH layouts in one call.

    Args:
        timeout: Seconds to allow each build subprocess to run.

    Returns:
        A :class:`PairedSession` holding both real, independently-built
        layouts, so "records nothing" and "records nothing because it gave
        up" stay distinguishable within a single run.
    """
    same_directory = build_same_directory_harness(timeout=timeout)
    sibling = build_out_of_package_harness(timeout=timeout)
    return PairedSession(same_directory=same_directory, sibling=sibling)


def run_build_drift_reader(target_root: Path, *, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run the REAL, DEPLOYED ``check_build_drift.py`` against a built
    receiving project, as a subprocess -- never an imported function call.

    ``build.py`` deploys the hook to
    ``<target_root>/.leafcutter/scripts/commit_guardian/check_build_drift.py``
    as part of every real build (both layouts in this module deploy it, since
    both run the unmodified ``build.py``). Running it with ``cwd=target_root``
    lets its own ``_resolve_manifest_path`` resolve the manifest the same way
    a real pre-commit invocation would.

    Args:
        target_root: The receiving project's root (``HarnessBuild.target_root``
            or ``SameDirectoryBuild.project_root``).
        timeout: Seconds to allow the reader subprocess to run.

    Returns:
        The completed subprocess (its RESULT line and exit code live on
        ``.stderr`` / ``.returncode``).
    """
    deployed_hook = target_root / ".leafcutter" / "scripts" / "commit_guardian" / "check_build_drift.py"
    return subprocess.run(
        [sys.executable, str(deployed_hook)],
        cwd=str(target_root),
        env=_scrubbed_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def extract_result_line(stderr: str) -> str:
    """Return the ``check-build-drift: RESULT ...`` line from a reader run's
    stderr, or raise if none is present.

    Args:
        stderr: The reader subprocess's captured stderr text.

    Returns:
        The single matching line, stripped.
    """
    for line in stderr.splitlines():
        if "check-build-drift: RESULT" in line:
            return line.strip()
    raise AssertionError(f"no RESULT line found in reader stderr:\n{stderr}")


def parse_result_field(result_line: str, field_name: str) -> int:
    """Parse an integer field (e.g. ``verified``) out of a RESULT line.

    Args:
        result_line: A line of the form
            ``"check-build-drift: RESULT verified=174 uncomparable=0 ..."``.
        field_name: The field to extract, e.g. ``"verified"`` or ``"gaps"``.

    Returns:
        The integer value recorded for ``field_name``.
    """
    for token in result_line.split():
        if token.startswith(f"{field_name}="):
            return int(token.split("=", 1)[1])
    raise AssertionError(f"field {field_name!r} not found in RESULT line: {result_line!r}")


__all__ = [
    "MANIFEST_METADATA_KEYS",
    "PairedSession",
    "SameDirectoryBuild",
    "build_paired_session",
    "build_same_directory_harness",
    "extract_result_line",
    "parse_result_field",
    "run_build_drift_reader",
    "template_account_keys",
    # Re-exported for test convenience (avoids a second import line for
    # every test that also needs the sibling layout's own primitives).
    "REAL_PACKAGE_ROOT",
    "hash_file",
]
