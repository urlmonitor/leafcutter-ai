"""KM-400f-5: the workflow's end-of-run ``status`` report is given the same capacity/retention flags as ``sync``.

Bug: ``.github/workflows/knowledge-sync.yml`` calls ``python -m knowledge status`` without the six
retention/capacity flags it passes to ``sync``, so the report prints capacity verdict 'unknown' and
reclaimability 'undetermined' although the sync step measured headroom correctly.

Behavioural approach: the real workflow YAML is parsed, the real 'Validate and publish canonical
snapshot' step's ``run`` script is executed under bash with the job's real ``env`` block, and a recording
``python`` shim on PATH captures the argv of every ``python -m knowledge <command>`` invocation. The test
asserts on the argv the ``status`` command actually received.
"""

import json
import os
import stat
import subprocess
from pathlib import Path

import yaml

from tests.knowledge._km_400f_2_support import REPO_ROOT

STEP_NAME = "Validate and publish canonical snapshot"
FLAG_TO_ENV = {
    "--retention-max-generations": "KNOWLEDGE_RETENTION_MAX_GENERATIONS",
    "--retention-min-age-seconds": "KNOWLEDGE_RETENTION_MIN_AGE_SECONDS",
    "--capacity-max-nodes": "KNOWLEDGE_CAPACITY_MAX_NODES",
    "--capacity-max-relationships": "KNOWLEDGE_CAPACITY_MAX_RELATIONSHIPS",
    "--capacity-refuse-percent": "KNOWLEDGE_CAPACITY_REFUSE_PERCENT",
    "--capacity-warn-percent": "KNOWLEDGE_CAPACITY_WARN_PERCENT",
}


def _run_step_and_record(tmp_path):
    """Execute the real workflow step; return {command: argv-after-command} for each knowledge call."""
    workflow = yaml.safe_load((Path(REPO_ROOT) / ".github/workflows/knowledge-sync.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["sync"]
    step = next(s for s in job["steps"] if s.get("name") == STEP_NAME)

    log = tmp_path / "calls.jsonl"
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "python"
    shim.write_text(
        "#!/bin/bash\n"
        'printf \'%s\\n\' "$(\\\n'
        "  /usr/bin/env python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' \"$@\")\" "
        f'>> "{log}"\n',
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)

    env = {k: str(v) for k, v in (job.get("env") or {}).items() if "${{" not in str(v)}
    env.update(
        {
            "PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}",
            "GITHUB_WORKSPACE": str(tmp_path),
            "KNOWLEDGE_REPOSITORY_ID": "leafcutter",
            "SOURCE_REVISION": "0" * 40,
            "TMPDIR": os.environ.get("TMPDIR", str(tmp_path)),
        }
    )
    result = subprocess.run(
        ["bash", "-e", "-c", step["run"]], env=env, capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr

    calls = {}
    for line in log.read_text(encoding="utf-8").splitlines():
        argv = json.loads(line)
        assert argv[:2] == ["-m", "knowledge"], argv
        calls[argv[2]] = argv[3:]
    return calls, env


def _flag_values(argv):
    return {a: argv[i + 1] for i, a in enumerate(argv[:-1]) if a.startswith("--")}


def test_status_receives_the_same_capacity_and_retention_flags_as_sync(tmp_path):
    # covers: KM-400f-5
    # angle: criterion
    """The status call carries all six flags, with the values the job env declares."""
    calls, env = _run_step_and_record(tmp_path)
    assert {"validate", "sync", "status"} <= set(calls), calls

    expected = {flag: env[name] for flag, name in FLAG_TO_ENV.items()}
    # Negative control: sync really receives them, so the expectation is tied to the real values.
    sync_values = _flag_values(calls["sync"])
    assert {f: sync_values.get(f) for f in expected} == expected

    status_values = _flag_values(calls["status"])
    assert {f: status_values.get(f) for f in expected} == expected
