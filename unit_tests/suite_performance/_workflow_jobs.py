"""Shared workflow-job executor for the TQ-600a-13 family.

Built by TQ-600a-13-ii (it_requirements: "THE SHARED TEST HARNESS IS BUILT HERE AND
REUSED BY THE WHOLE FAMILY"), items (1) a fake REST API on 127.0.0.1 and (2) a workflow-step
executor. It is test infrastructure, not a test: its filename starts with an underscore so
pytest does not collect it. The fake API and the artifact store live in ``_workflow_fakes.py``
and the ``if:`` evaluator in ``_workflow_conditions.py``; both are re-exported here, so
importers keep using ``_workflow_jobs`` alone.

The executor loads a workflow file, locates ONE job by its exact id or its exact ``name:``,
and executes that job's ``run:`` steps VERBATIM with ``bash -e`` in a fresh workspace.

Supported, because the family's workflows are required to stay inside this subset:

* ``uses: actions/checkout`` -- EMULATED: the synthetic project is copied into the workspace
  (``with.path`` honoured).
* ``uses: actions/upload-artifact`` / ``actions/download-artifact`` -- EMULATED through an
  :class:`ArtifactStore` shared between the jobs of one :class:`WorkflowRun`; this is the ONLY
  channel between two jobs, exactly as on the hosting service. Which artifacts a job
  downloaded is recorded on its :class:`JobResult`.
* any other ``uses:`` step (setup-python, setup-node, ...) is skipped.
* a ``run:`` step whose text is exactly one of :data:`PREPARATION_STEPS` is skipped (dependency
  install and the build are not what these tests exercise, and no test may start a build).
* ``if:`` grammar and ``${{ }}`` contexts: see ``_workflow_conditions.py``.
* ``${{ }}`` is expanded in ``env:``, ``with:`` and job ``outputs:``.

The executor FAILS (it never guesses) on: a ``run:`` step containing ``${{``, a job with
``strategy.matrix``, an ``if:`` outside the grammar, or an unknown context.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ._workflow_conditions import HarnessError, _Context, _expand, _fail, condition_holds
from ._workflow_fakes import ArtifactStore, FakeGitHub

__all__ = [
    "ArtifactStore",
    "FakeGitHub",
    "HarnessError",
    "JobResult",
    "WorkflowRun",
    "condition_holds",
    "find_job",
    "load_workflow",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
PREPARATION_STEPS = frozenset(
    {
        "pip install -r requirements-dev.txt",
        "python scripts/build.py --target-dir .",
    }
)
STEP_TIMEOUT_SECONDS = 180
DEFAULT_EVENT_ENV = {
    "GITHUB_SHA": "0123456789abcdef0123456789abcdef01234567",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_EVENT_NAME": "push",
    "GITHUB_RUN_ID": "424242",
    "GITHUB_REPOSITORY": "example/leafcutter-ai",
    "GITHUB_SERVER_URL": "https://github.com",
    "GITHUB_ACTIONS": "true",
}


# --------------------------------------------------------------------------- results
@dataclass
class JobResult:
    job: str
    conclusion: str  # success | failure | skipped
    steps: dict = field(default_factory=dict)  # step name -> success | failure | skipped
    outputs: dict = field(default_factory=dict)
    workspace: Path | None = None
    runner: str | None = None
    downloaded: list = field(default_factory=list)  # artifact names this job downloaded
    failed_step: str | None = None
    logs: list = field(default_factory=list)  # (step name, combined output)

    def log_text(self):
        return "\n".join(f"--- {name}\n{text}" for name, text in self.logs)


# --------------------------------------------------------------------------- the executor
def load_workflow(path):
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return _fail(f"cannot read workflow {path}: {exc}", exc)


def find_job(doc, name):
    """Locate a job by its exact id or its exact ``name:``; (id, job) or None."""
    for job_id, job in (doc.get("jobs") or {}).items():
        if job_id == name or (job or {}).get("name") == name:
            return job_id, job
    return None


def _parse_key_value_file(path):
    out = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"cannot read {path}: {exc}", exc)
    i = 0
    while i < len(lines):
        line = lines[i]
        heredoc = re.match(r"^([^=<]+)<<(\S+)$", line)
        if heredoc:
            key, delim, body = heredoc.group(1), heredoc.group(2), []
            i += 1
            while i < len(lines) and lines[i] != delim:
                body.append(lines[i])
                i += 1
            out[key] = "\n".join(body)
        elif "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
        i += 1
    return out


class WorkflowRun:
    """One run of one workflow file: jobs are executed one at a time, each in its OWN fresh directory."""

    def __init__(self, workflow_path, project_dir, scratch, extra_env=None, api_url=None):
        self.doc = load_workflow(workflow_path)
        self.project_dir = Path(project_dir)
        self.scratch = Path(scratch)
        artifact_root = self.scratch / "artifacts"
        try:
            artifact_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _fail(f"cannot create {artifact_root}: {exc}", exc)
        self.artifacts = ArtifactStore(artifact_root)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "GITHUB_", "RUNNER_"))}
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        env["AC_ENFORCE_STRICT"] = "1"
        env.update(DEFAULT_EVENT_ENV)
        if api_url:
            env["GITHUB_API_URL"] = api_url
            env["GITHUB_TOKEN"] = "fake-token"
        env.update(extra_env or {})
        self._base_env = env

    # ---- job-level
    def execute_job(self, name, needs=None):
        found = find_job(self.doc, name)
        if found is None:
            _fail(f"no job with id or name {name!r} in the workflow")
        job_id, job = found
        if (job.get("strategy") or {}).get("matrix") is not None:
            _fail(f"job {name!r} has a strategy.matrix, which the executor does not support")
        declared = job.get("needs") or []
        declared = [declared] if isinstance(declared, str) else list(declared)
        passed = needs or {}
        missing = [n for n in declared if n not in passed]
        if missing:
            _fail(f"job {name!r} needs {missing} but their results were not supplied")
        results = [passed[n].conclusion for n in declared]
        status = "failure" if "failure" in results else ("success" if all(r == "success" for r in results) else "skipped")
        runner = f"runner-{job_id}"
        env = dict(self._base_env)
        env["RUNNER_NAME"] = runner
        ctx = _Context(env=env, needs={n: passed[n] for n in declared}, status=status)
        result = JobResult(job=job_id, conclusion="skipped", runner=runner)
        if not condition_holds(job.get("if"), ctx):
            return result

        workspace = Path(tempfile.mkdtemp(prefix=f"{job_id}-", dir=self.scratch))
        result.workspace = workspace
        env["GITHUB_WORKSPACE"] = str(workspace)
        ctx.status = "success"
        job_env = {k: _expand(v, ctx) for k, v in {**(self.doc.get("env") or {}), **(job.get("env") or {})}.items()}
        env.update(job_env)
        ctx.env = env
        default_shell = ((job.get("defaults") or {}).get("run") or {}).get("shell") or (
            (self.doc.get("defaults") or {}).get("run") or {}
        ).get("shell")
        for index, step in enumerate(job.get("steps") or []):
            self._execute_step(index, step, ctx, result, workspace, default_shell)
        result.conclusion = "failure" if ctx.status == "failure" else "success"
        result.outputs = {k: _expand(v, ctx) for k, v in (job.get("outputs") or {}).items()}
        return result

    # ---- step-level
    def _execute_step(self, index, step, ctx, result, workspace, default_shell):
        name = step.get("name") or step.get("uses") or (step.get("run") or "").strip().splitlines()[0][:60] or f"step-{index}"
        step_id = step.get("id")
        if not condition_holds(step.get("if"), ctx):
            result.steps[name] = "skipped"
            if step_id:
                ctx.steps[step_id] = {"outputs": {}, "outcome": "skipped", "conclusion": "skipped"}
            return
        outputs, outcome, log = {}, "success", ""
        if "uses" in step:
            outcome, log, _unused = self._uses(step, ctx, result, workspace)
        elif "run" in step:
            text = step["run"]
            if text.strip() in PREPARATION_STEPS:
                outcome, log = "skipped", "preparation step skipped by the executor"
            else:
                if "${{" in text:
                    _fail(f"step {name!r} has a run: containing a dollar-brace expression; context must arrive via env:")
                outcome, log, outputs = self._run(step, ctx, workspace, default_shell, index)
        else:
            _fail(f"step {name!r} has neither uses: nor run:")
        result.logs.append((name, log))
        result.steps[name] = outcome
        if step_id:
            ctx.steps[step_id] = {"outputs": outputs, "outcome": outcome, "conclusion": outcome}
        if outcome == "failure" and step.get("continue-on-error") not in (True, "true"):
            ctx.status = "failure"
            if result.failed_step is None:
                result.failed_step = name

    def _run(self, step, ctx, workspace, default_shell, index):
        env = dict(ctx.env)
        env.update({k: _expand(v, ctx) for k, v in (step.get("env") or {}).items()})
        out_file = workspace.parent / f"{workspace.name}-github-output-{index}.txt"
        env_file = workspace.parent / f"{workspace.name}-github-env-{index}.txt"
        for path in (out_file, env_file):
            try:
                path.write_text("", encoding="utf-8")
            except OSError as exc:
                _fail(f"cannot create {path}: {exc}", exc)
        env["GITHUB_OUTPUT"] = str(out_file)
        env["GITHUB_ENV"] = str(env_file)
        shell = step.get("shell") or default_shell
        flags = ["-e", "-o", "pipefail"] if shell == "bash" else ["-e"]
        cwd = workspace / step["working-directory"] if step.get("working-directory") else workspace
        try:
            proc = subprocess.run(
                ["bash", "--noprofile", "--norc", *flags, "-c", step["run"]],
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=STEP_TIMEOUT_SECONDS,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            _fail(f"could not execute step {step.get('name')!r}: {exc}", exc)
        ctx.env.update(_parse_key_value_file(env_file))
        outputs = _parse_key_value_file(out_file)
        return ("success" if proc.returncode == 0 else "failure"), proc.stdout + proc.stderr, outputs

    def _uses(self, step, ctx, result, workspace):
        action = step["uses"].split("@", 1)[0]
        with_ = {k: _expand(v, ctx) for k, v in (step.get("with") or {}).items()}
        try:
            if action == "actions/checkout":
                dest = workspace / with_.get("path", ".")
                shutil.copytree(
                    self.project_dir,
                    dest,
                    symlinks=True,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
                )
                return "success", "checkout emulated from the synthetic project", {}
            if action == "actions/upload-artifact":
                return self._upload(with_, workspace)
            if action == "actions/download-artifact":
                return self._download(with_, workspace, result)
        except (OSError, shutil.Error) as exc:
            return "failure", f"{action} failed: {exc}", {}
        return "skipped", f"{action} skipped by the executor", {}

    def _upload(self, with_, workspace):
        name = with_.get("name", "artifact")
        patterns = [p.strip().removeprefix("./") for p in with_.get("path", "").splitlines() if p.strip()]
        entries = []
        for pattern in patterns:
            for match in sorted(workspace.glob(pattern)):
                if match.is_dir():
                    entries += [(str(f.relative_to(match)), f) for f in sorted(match.rglob("*")) if f.is_file()]
                elif len(patterns) == 1:
                    entries.append((match.name, match))
                else:
                    entries.append((str(match.relative_to(workspace)), match))
        if not entries:
            if with_.get("if-no-files-found") == "error":
                return "failure", f"no files found for artifact {name!r}", {}
            return "success", f"no files found for artifact {name!r}; nothing uploaded", {}
        self.artifacts.upload(name, entries)
        return "success", f"uploaded artifact {name!r}: {[rel for rel, _ in entries]}", {}

    def _download(self, with_, workspace, result):
        wanted = with_.get("name")
        names = [wanted] if wanted else self.artifacts.names()
        dest = workspace / with_.get("path", ".")
        for name in names:
            files = self.artifacts.files(name)
            if not files:
                return "failure", f"artifact {name!r} not found", {}
            target_dir = dest if wanted else dest / name
            for rel, src in files.items():
                target = target_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
            result.downloaded.append(name)
        return "success", f"downloaded {names}", {}
