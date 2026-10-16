"""Snapshot the installed hook runtime into an owned worktree without secrets or installs."""

from pathlib import Path
import shlex
import json

import yaml

from .execution_boundary import ExecutorError, PROTECTED_RUNTIME_PATHS

RUNTIME_PATHS = (".leafcutter/scripts", ".leafcutter/config", ".leafcutter/skills/security-scanner/scripts")
PROTECTED_PATHS = PROTECTED_RUNTIME_PATHS


def _safe_path(root, relative):
    path = root / relative
    for entry in (path, *path.parents):
        if entry == root:
            break
        if entry.is_symlink():
            raise ExecutorError("Hook runtime provisioning cannot traverse symlinks")
    return path


def provision_runtime(repo, workspace, invoke):
    """Copy only deployment assets; require ignored destinations and immutable retries."""
    repo, workspace = Path(repo), Path(workspace)
    try:
        config = _safe_path(repo, ".leafcutter/pre-commit-config.yaml")
        if not config.is_file():
            config = _safe_path(repo, ".pre-commit-config.yaml")
        if not config.is_file() or ".leafcutter/" not in config.read_text(encoding="utf-8"):
            return False
        files = {}
        allowed = json.loads(Path(__file__).with_name("hook_assets.json").read_text(encoding="utf-8"))["assets"]
        for relative in allowed:
            if ".." in Path(relative).parts or not relative.startswith(".leafcutter/"):
                raise ExecutorError("Invalid package hook asset manifest")
            source = _safe_path(repo, relative)
            if source.is_file():
                files[relative] = source
        _safe_path(repo, config.relative_to(repo))
        files[".leafcutter/pre-commit-config.yaml"] = config
        if not (workspace / ".pre-commit-config.yaml").exists():
            files[".pre-commit-config.yaml"] = config
        ignored = invoke(
            ["git", "-c", "core.fsmonitor=false", "check-ignore", "--no-index", "-z", "--stdin"],
            cwd=workspace, input_text="\0".join(files) + "\0", timeout=30,
        ).stdout
        if set(ignored.rstrip("\0").split("\0")) != set(files):
            raise ExecutorError("Owned worktree must ignore every deployed hook runtime asset")
        tracked = invoke(["git", "ls-files", "-z", "--", *files], cwd=workspace, timeout=30).stdout
        if tracked:
            raise ExecutorError("Deployed hook runtime assets must not overwrite tracked files")
        for relative, source in files.items():
            destination = _safe_path(workspace, relative)
            content = source.read_bytes()
            if destination.exists():
                if not destination.is_file() or destination.read_bytes() != content:
                    raise ExecutorError("Preserved deployed hook runtime differs; reconciliation required")
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            destination.chmod(source.stat().st_mode & 0o777)
        active = _safe_path(workspace, ".pre-commit-config.yaml")
        document = yaml.safe_load(active.read_text(encoding="utf-8")) or {}
        for repository in document.get("repos", []):
            for hook in repository.get("hooks", []):
                for token in shlex.split(hook.get("entry", "")):
                    if token.startswith(".leafcutter/"):
                        candidate = _safe_path(workspace, token)
                        if not candidate.is_file() or ".." in Path(token).parts:
                            raise ExecutorError("Missing deployed hook entrypoint prerequisite: " + token)
        return True
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ExecutorError("Cannot provision the owned worktree hook runtime") from exc
