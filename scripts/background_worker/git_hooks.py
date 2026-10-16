"""Route real Git hooks through a Linux namespace without granting ref authority."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

from .execution_boundary import ExecutorError, run_process, safe_output


class GitHookError(ExecutorError):
    """A hook failed; post-commit failures need explicit outcome reconciliation."""

    requires_reconciliation = False


class GitHookSandbox:
    def __init__(
        self, repo, workspace, *, invoke=run_process, runtime_read_paths=(), pre_commit_cache=None
    ):
        self.repo = Path(repo).resolve()
        self.workspace = Path(workspace).resolve()
        self.invoke = invoke
        self.runtime_read_paths = [str(Path(path).resolve()) for path in runtime_read_paths]
        self.pre_commit_cache = str(Path(pre_commit_cache).resolve()) if pre_commit_cache else None

    def original_hooks(self, cwd):
        value = self.invoke(
            ["git", "rev-parse", "--path-format=absolute", "--git-path", "hooks"],
            cwd=cwd,
            timeout=20,
        ).stdout.strip()
        return Path(value).resolve()

    def preflight(self, cwd):
        directory = self.original_hooks(cwd)
        hooks = (
            [
                path
                for path in directory.iterdir()
                if path.is_file() and not path.name.endswith(".sample") and os.access(path, os.X_OK)
            ]
            if directory.is_dir()
            else []
        )
        if hooks and (not sys.platform.startswith("linux") or not shutil.which("bwrap")):
            raise ExecutorError(
                "Git hooks require the Linux bubblewrap coordinator boundary; install bubblewrap in the worker runtime"
            )
        for value in [
            *self.runtime_read_paths,
            *([self.pre_commit_cache] if self.pre_commit_cache else []),
        ]:
            path = Path(value)
            if (
                not path.is_dir()
                or path == Path(path.anchor)
                or path in Path.home().parents
                or path == Path.home()
            ):
                raise ExecutorError(
                    "Hook dependency paths must be existing specific runtime directories, not host/user roots"
                )
        return hooks

    @contextmanager
    def invocation(self, cwd):
        hooks = self.preflight(cwd)
        if not hooks:
            yield []
            return
        try:
            with tempfile.TemporaryDirectory(prefix="leafcutter-git-hooks-") as temporary:
                directory = Path(temporary)
                manifest = directory / "manifest.json"
                outcomes = directory / "outcomes.jsonl"
                manifest.write_text(
                    json.dumps(
                        {
                            "repo": str(self.repo),
                            "workspace": str(self.workspace),
                            "hooks": {path.name: str(path.resolve()) for path in hooks},
                            "outcomes": str(outcomes),
                            "runtime_read_paths": self.runtime_read_paths,
                            "pre_commit_cache": self.pre_commit_cache,
                        }
                    ),
                    encoding="utf-8",
                )
                broker = Path(__file__).with_name("hook_broker.py").resolve()
                for hook in hooks:
                    wrapper = directory / hook.name
                    command = " ".join(
                        shlex.quote(str(value))
                        for value in (sys.executable, broker, manifest, hook.name)
                    )
                    marker = shlex.quote(json.dumps({"hook": hook.name, "started": True}))
                    wrapper.write_text(
                        '#!/bin/sh\nset -e\nprintf "%s\\n" '
                        + marker
                        + " >> "
                        + shlex.quote(str(outcomes))
                        + "\nexec "
                        + command
                        + ' "$@"\n',
                        encoding="utf-8",
                    )
                    wrapper.chmod(0o700)
                try:
                    yield ["-c", f"core.hooksPath={directory}"]
                finally:
                    cause = sys.exc_info()[1]
                    if outcomes.is_file():
                        records = [
                            json.loads(line)
                            for line in outcomes.read_text(encoding="utf-8").splitlines()
                        ]
                        failures = [
                            record
                            for record in records
                            if not record.get("started") and not record["passed"]
                        ]
                        for name in {record["hook"] for record in records}:
                            started = sum(
                                record.get("started", False)
                                for record in records
                                if record["hook"] == name
                            )
                            ended = sum(
                                not record.get("started", False)
                                for record in records
                                if record["hook"] == name
                            )
                            if started != ended:
                                failures.append(
                                    {"hook": name, "reason": "Hook process outcome missing"}
                                )
                        if failures:
                            error = GitHookError(
                                "Sandboxed Git hook failed: "
                                + "; ".join(
                                    record["hook"] + ": " + record["reason"] for record in failures
                                )
                            )
                            error.requires_reconciliation = any(
                                record["hook"] in {"post-commit", "reference-transaction"}
                                for record in failures
                            )
                            inherited = getattr(cause, "evidence", {})
                            error.evidence = {
                                key: safe_output(inherited[key])
                                for key in ("stdout", "stderr") if key in inherited
                            }
                            error.evidence["hook_outcomes"] = [
                                {key: safe_output(record.get(key, ""))
                                 for key in ("hook", "reason")} for record in failures[:32]
                            ]
                            if cause is not None:
                                error.evidence["cause"] = (
                                    safe_output(str(cause)) if isinstance(cause, ExecutorError)
                                    else type(cause).__name__
                                )
                            if isinstance(inherited.get("returncode"), int):
                                error.evidence["returncode"] = inherited["returncode"]
                            raise error from cause
        except OSError as exc:
            raise ExecutorError(
                "Cannot establish the coordinator's trusted hook wrapper directory"
            ) from exc
