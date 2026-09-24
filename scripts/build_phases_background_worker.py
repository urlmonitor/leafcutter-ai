"""Deploy the optional local worker without enabling it or starting inference.

ACD-1300b-1: copy the CLI, Python modules, pinned runtime requirements and SDK
bridge manifests into the internal consumer tree; never copy runtime state,
bytecode or node_modules. Dependencies are installed explicitly by the operator.
"""

import logging
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)
# These are also deployed by build_ac_store in a complete build. Naming the
# canonical sources here makes this phase independently runnable and importable.
DEPENDENCIES = ("ac_store/__init__.py", "ac_store/ac_parent_id.py")


def background_worker_sources(package_root):
    """Return this phase's one source declaration, including transitive helpers."""
    source = Path(package_root) / "scripts"
    directory = source / "background_worker"
    return [
        source / "background_worker_cli.py",
        *(source / path for path in DEPENDENCIES),
    ] + sorted(
        path
        for path in directory.rglob("*")
        if path.is_file()
        and not {"node_modules", "__pycache__"}.intersection(path.relative_to(source).parts)
        and path.suffix in {".py", ".json", ".mjs", ".txt"}
    )


def manifest_background_worker(package_root):
    """Source/deploy paths for the build's dependency-closure inventory."""
    root = Path(package_root)
    return {
        path.relative_to(root).as_posix()
        for path in background_worker_sources(root)
        if path.is_file()
    }


def build_background_worker(target_root, config, dry_run, force):
    import build_phases as bp

    source = bp.PACKAGE_ROOT / "scripts"
    directory = source / "background_worker"
    required = [source / "background_worker_cli.py", *(source / path for path in DEPENDENCIES)]
    missing = [path for path in required if not path.is_file()]
    if not directory.is_dir():
        missing.append(directory)
    if missing:
        for path in missing:
            bp.record_deploy_failure("build_background_worker", str(path.relative_to(source)), path)
        return 0
    written = 0
    for src in background_worker_sources(bp.PACKAGE_ROOT):
        rel = src.relative_to(source)
        dst = Path(target_root) / "scripts" / rel
        if not bp._should_overwrite(dst, force):
            continue
        try:
            if dst.exists() and src.read_bytes() == dst.read_bytes():
                continue
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        except OSError:
            logger.exception("Cannot deploy background worker dependency %s to %s", src, dst)
            raise
        written += 1
    return written
