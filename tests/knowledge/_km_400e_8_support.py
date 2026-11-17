"""Shared harness for the KM-400e-8 tests (no tests live here).

The synchronization job is executed for real, in a fresh subprocess, through the real
``knowledge.__main__.main`` argv parser. Only the Neo4j driver is replaced: a double module is
installed as ``knowledge.adapters.neo4j_backend`` that RECORDS every construction (one record per
connection attempt) to a JSON-lines file and then stops the run with a recognisable marker, or
rejects the database with a message that deliberately does NOT contain the requested name (so a
test that finds the name in the output proves the job added it).

``run_workflow_job`` evaluates the merge workflow's own ``env`` expressions (``vars.*``,
``secrets.*``, ``a || 'literal'``) and runs the workflow's own ``run`` steps in order, so a
substitution that lives in the workflow definition is reached exactly as the merge event reaches it.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/knowledge-sync.yml"
STOP_MARKER = "double-stop-after-connect"
DATABASE_SETTING = "LEAFCUTTER_NEO4J_DATABASE"
USERNAME_SETTING = "LEAFCUTTER_NEO4J_WRITER_USERNAME"
HOSTED_URI = "neo4j+s://abc12345.databases.neo4j.io"
INSTANCE_DB = "abc12345"
INSTANCE_USER = "svc-abc12345"
PASSWORD = "pw-Zq93xLmN7-secret"

_DRIVER = '''\
import json, os, sys

from knowledge.errors import BackendUnavailable

RECORD = os.environ["KNOWLEDGE_DOUBLE_RECORD"]
MODE = os.environ.get("KNOWLEDGE_DOUBLE_MODE", "stop")


class Neo4jBackend:
    def __init__(self, uri, username, password, database="neo4j", query_timeout=3.0):
        with open(RECORD, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"uri": uri, "username": username, "password": password,
                                     "database": database}) + "\\n")
        self.database = database

    async def _run(self, *args, **kwargs):
        return await self.setup()

    async def setup(self):
        if MODE == "reject_database":
            raise BackendUnavailable(
                "backend unavailable: ClientError [Neo.ClientError.Database.DatabaseNotFound]: "
                "Database does not exist."
            )
        raise BackendUnavailable("%s")

    async def close(self):
        return None


import knowledge.adapters.neo4j_backend as real_backend

real_backend.Neo4jBackend = Neo4jBackend  # only the driver-owning class is replaced

from knowledge.__main__ import main

sys.exit(main())
''' % STOP_MARKER


def base_env(scratch, mode="stop"):
    """Minimal environment: no inherited NEO4J_* or LEAFCUTTER_* settings can leak in."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(scratch)),  # keeps the user site-packages importable
        "PYTHONPATH": str(REPO_ROOT),
        "KNOWLEDGE_DOUBLE_RECORD": str(scratch / "connections.jsonl"),
        "KNOWLEDGE_DOUBLE_MODE": mode,
    }
    for name in ("TMPDIR", "TEMP", "TMP"):
        env[name] = os.environ.get(name, str(scratch))
    return env


def write_driver(scratch):
    driver = scratch / "double_driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    return driver


def connections(scratch):
    """Every connection the job attempted, in order."""
    record = scratch / "connections.jsonl"
    if not record.exists():
        return []
    return [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines() if line]


def output_of(result):
    return result.stdout + result.stderr


def prepare_root(scratch, env_file_text=""):
    """A project root whose own .env (also the named env file) is controlled, so nothing is discovered upstream."""
    root = scratch / "project"
    root.mkdir(exist_ok=True)
    env_file = root / ".env"
    env_file.write_text(env_file_text, encoding="utf-8")
    return root, env_file


def run_sync(scratch, settings, mode="stop", env_file_text="", extra_args=()):
    """Run ``python -m knowledge sync`` (via the double driver) with exactly ``settings`` declared."""
    root, env_file = prepare_root(scratch, env_file_text)
    env = base_env(scratch, mode)
    env["LEAFCUTTER_ENV_FILE"] = str(env_file)
    env.update(settings)
    argv = [sys.executable, str(write_driver(scratch)), "sync", "--root", str(root),
            "--repository-id", "leafcutter", "--revision", "HEAD", *extra_args]
    return subprocess.run(argv, env=env, cwd=str(scratch), capture_output=True, text=True, timeout=120)


def declared(database=INSTANCE_DB, username=INSTANCE_USER):
    """Process-environment settings; ``None`` leaves that required setting unset."""
    values = {"LEAFCUTTER_NEO4J_URI": HOSTED_URI, "LEAFCUTTER_NEO4J_WRITER_PASSWORD": PASSWORD}
    if database is not None:
        values[DATABASE_SETTING] = database
    if username is not None:
        values[USERNAME_SETTING] = username
    return values


def _operand(token, context):
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return token[1:-1]
    return context.get(token, "")


def evaluate(text, context):
    """Evaluate the ``${{ ... }}`` expressions this workflow uses: lookups and ``||`` chains."""
    def one(match):
        for token in match.group(1).split("||"):
            value = _operand(token, context)
            if value:
                return value
        return ""

    return re.sub(r"\$\{\{(.*?)\}\}", one, str(text))


def init_origin_repo(root):
    """A real git repo whose HEAD is also origin/main, as the workflow's ancestry check requires."""
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*git, "init", "-q", "-b", "main", str(root)], check=True)
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run([*git, "-C", str(root), "add", "README.md"], check=True)
    subprocess.run([*git, "-C", str(root), "commit", "-q", "-m", "fixture"], check=True)
    sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "-C", str(root), "update-ref", "refs/remotes/origin/main", sha], check=True)
    return sha


def run_workflow_job(scratch, secrets, variables, mode="stop"):
    """Execute the merge workflow's sync job steps as the merge event would, minus network installs.

    Returns (exit_code, output) of the first failing step, or of the last step run.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["sync"]
    workspace = scratch / "workspace"
    workspace.mkdir()
    sha = init_origin_repo(workspace)
    (workspace / ".env").write_text("", encoding="utf-8")
    context = {"github.sha": sha, "github.repository": "o/r"}
    context.update({"vars." + name: value for name, value in variables.items()})
    context.update({"secrets." + name: value for name, value in secrets.items()})
    env = base_env(scratch, mode)
    env["LEAFCUTTER_ENV_FILE"] = str(workspace / ".env")
    env["GITHUB_WORKSPACE"] = str(workspace)
    env.update({name: evaluate(value, context) for name, value in job["env"].items()})
    driver = write_driver(scratch)
    code, combined = 0, ""
    for step in job["steps"]:
        script = step.get("run")
        if not script or "pip install" in script:
            continue
        if "knowledge validate" in script:  # only the sync command is the publication under test
            script = "\n".join(line for line in script.splitlines() if "knowledge sync" in line)
        script = script.replace("python -m knowledge", f"{sys.executable} {driver}")
        script = script.replace("python -", f"{sys.executable} -", 1) if script.lstrip().startswith("python -") else script
        done = subprocess.run(["bash", "-c", script], env=env, cwd=str(workspace),
                              capture_output=True, text=True, timeout=120)
        # Only the deciding step's own output counts: the informational report step prints setting
        # names for every run and must not satisfy "the failure names the unset setting".
        code, combined = done.returncode, done.stdout + done.stderr
        if code != 0:
            break
    return code, combined
