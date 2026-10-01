"""
MODULE: tests.kernel.live.live_support
GOAL: Shared helpers of the live suite: the LEAFCUTTER_KERNEL_LIVE guard, a scratch run root and
    config override, a CLI runner, clearly labelled synthetic host and human answers, and a
    Langfuse reader that fetches a run's observations through the observations API.
BUSINESS CONTEXT: The live tests prove what offline doubles cannot (the real provider, the real
    CLI process, the real trace backend). They must never put run data or credentials in the
    repository, and any answer they invent must say plainly that it is synthetic.
ARCHITECTURE: Pure helpers plus two IO wrappers (`run_cli`, `fetch_observations`). The CLI is run
    as `python -m kernel` in a subprocess with a `--config` override whose only entry is the run
    root. The legacy get-trace endpoint returns 410 for this organisation, so traces are read with
    `api.observations.get_many`. Credentials come from kernel.secrets and are never printed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from kernel.config import repo_root
from kernel.observability.correlation import deterministic_trace_id
from kernel.secrets import SecretSettings, load_secrets

LIVE = os.environ.get("LEAFCUTTER_KERNEL_LIVE") == "1"
SKIP_REASON = "live suite: set LEAFCUTTER_KERNEL_LIVE=1 (uses the real Jev and Langfuse)"
SYNTHETIC = "SYNTHETIC LIVE-TEST ANSWER (not a real host or human)"
RELAYED_BY = "kernel-live-test (synthetic answer)"
CLI_TIMEOUT_SECONDS = 600
TRACE_WAIT_SECONDS = 150
TRACE_POLL_SECONDS = 15


NO_RUN = "the kernel CLI did not run"
NOT_JSON = "stdout was not one JSON document"


class LiveRunError(AssertionError):
    """The kernel CLI could not be run or did not print one JSON document."""

    def __init__(self, what: str, detail: str = "") -> None:
        """Build the message from what failed and a short detail."""
        super().__init__(f"{what}: {detail}" if detail else what)


def scratch_dir(name: str) -> Path:
    """Return a fresh scratch directory (LEAFCUTTER_LIVE_SCRATCH if set, else the OS temp dir)."""
    base = os.environ.get("LEAFCUTTER_LIVE_SCRATCH")
    parent = Path(base) if base else Path(tempfile.gettempdir())
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"kernel-live-{name}-", dir=parent))


def write_config_override(scratch: Path, **extra: Any) -> Path:
    """Write a config override that moves the run root into `scratch`; return its path."""
    body: dict[str, Any] = {"paths": {"run_root": str(scratch / "run_root")}, **extra}
    path = scratch / "kernel_config.override.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def run_cli(args: list[str], *, config: Path, scratch: Path, document: dict | None = None
            ) -> tuple[int, dict[str, Any]]:
    """Run `python -m kernel <args> --json --config ...` and return (exit code, JSON document).

    Args:
        args: Command and flags (for example ["run"], ["resume", "--run-id", "run-x"]).
        config: Config override file.
        scratch: Directory for the input document.
        document: JSON to pass through `--input-file` (written to scratch), if any.

    Returns:
        tuple[int, dict]: The exit code and the one JSON document printed on stdout.
    """
    command = [sys.executable, "-m", "kernel", *args, "--json", "--config", str(config)]
    if document is not None:
        path = scratch / f"input-{time.time_ns()}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        command += ["--input-file", str(path)]
    env = {**os.environ, "PYTHONUTF8": "1"}
    try:
        done = subprocess.run(command, cwd=repo_root(), capture_output=True, text=True,
                              encoding="utf-8", timeout=CLI_TIMEOUT_SECONDS, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LiveRunError(NO_RUN, type(exc).__name__) from exc
    try:
        return done.returncode, json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        tail = f"exit {done.returncode}; stderr tail: {done.stderr[-600:]}"
        raise LiveRunError(NOT_JSON, tail) from exc


def task_document(goal: str, *, payload: dict | None = None, read_roots: list[str] | None = None
                  ) -> dict[str, Any]:
    """Return a TaskInput document for `goal` over this repository (optionally with a payload)."""
    scope: dict[str, Any] = {"workspace_id": "leafcutter-live",
                             "repository_root": str(repo_root())}
    if read_roots:
        scope["read_roots"] = read_roots
    doc: dict[str, Any] = {"goal": goal, "caller": {"id": "kernel-live-test", "kind": "host"},
                           "scope": scope}
    if payload is not None:
        doc.update(input_payload_schema="leafcutter.decision_request.v1", input_payload=payload)
    return doc


def synthetic_submission(envelope: dict[str, Any]) -> dict[str, Any]:
    """Build a clearly labelled synthetic answer to the envelope's pending interaction."""
    packet = envelope["pending_interaction"]
    base = {"run_id": envelope["run_id"], "interaction_id": packet["id"],
            "expected_state_revision": packet["state_revision"], "relayed_by": RELAYED_BY}
    if "choices" in packet:  # a human question
        ids = [c["id"] for c in packet["choices"]]
        if "approve" in ids:
            response: dict[str, Any] = {"choice_id": "approve"}
        elif ids:
            response = {"choice_id": ids[0]}
        else:
            response = {"free_text": f"{SYNTHETIC}: no preference; decide on the evidence."}
        return {**base, "actor": {"id": "human:live-test-synthetic", "kind": "human"},
                "response_schema_id": "leafcutter.human_answer.v1", "response": response}
    schema = packet["output_schema_id"]
    return {**base, "actor": {"id": "host:live-test-synthetic", "kind": "host"},
            "response_schema_id": schema, "response": _host_response(schema, packet)}


def _host_response(schema: str, packet: dict[str, Any]) -> dict[str, Any]:
    """Return a synthetic host response valid for the output schema.

    Options cite the evidence the packet carries, as a cooperating host must (grounding).
    """
    cited = list(packet.get("input_evidence_ids") or [])
    proposed = {"proposal_status": "proposed", "approval_status": "proposed",
                "proposed_by": "host:live-test-synthetic"}
    if schema == "leafcutter.options.v1":
        options = [{"id": "opt.csv", "title": "Write CSV", "description":
                    f"One row per record. [{SYNTHETIC}]", "source_refs": cited, **proposed},
                   {"id": "opt.jsonl", "title": "Write JSON Lines", "description":
                    f"One JSON object per line. [{SYNTHETIC}]", "source_refs": cited, **proposed}]
        criteria = [{"id": "crit.typed", "question": "Does the option preserve nested and typed "
                     "values without lossy flattening?", "priority": "required", **proposed},
                    {"id": "crit.simple", "question": "Is the option simple to produce and read "
                     "with standard tools?", "priority": "required", **proposed}]
        return {"options": options, "proposed_criteria": criteria, "unresolved_feasibility": []}
    if schema == "leafcutter.findings.v1":
        return {"findings": [], "unknowns": [f"{SYNTHETIC}: no synthesis performed."]}
    return {"evidence": [], "findings": [], "evidence_ids": []}


def observations_api(secrets: SecretSettings | None = None) -> Any:
    """Return a read-only Langfuse REST client built from the loaded credentials.

    It deliberately avoids the `Langfuse` SDK client: the SDK caches one instance per public key,
    so a read client created (and shut down) here would silently replace the tracer's exporter
    in the same process.
    """
    from langfuse.api import LangfuseAPI

    found = secrets or load_secrets()
    assert found.has_langfuse(), "Langfuse credentials are not available"
    return LangfuseAPI(base_url=found.langfuse_base_url,
                       username=found.langfuse_public_key.get_secret_value(),
                       password=found.langfuse_secret_key.get_secret_value())


def _field(obj: Any, *names: str) -> Any:
    """Return the first non-None attribute among `names` (the SDK mixes snake and camel case)."""
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def _fetch_once(api: Any, trace_id: str) -> list[Any]:
    """Return every observation of the trace through the observations API (paged)."""
    rows: list[Any] = []
    cursor = None
    while True:
        page = api.observations.get_many(trace_id=trace_id, limit=1000, cursor=cursor,
                                                fields="core,basic,model,usage,metadata")
        rows += list(page.data)
        cursor = getattr(getattr(page, "meta", None), "cursor", None)
        if not cursor or not page.data:
            return rows


def fetch_observations(run_id: str, *, expect_names: set[str]) -> list[Any]:
    """Poll the observations API until the trace is stable and holds `expect_names`.

    Returns:
        list: Observations (whatever arrived before the deadline).
    """
    api = observations_api()
    trace_id = deterministic_trace_id(run_id)
    deadline, rows, last = time.time() + TRACE_WAIT_SECONDS, [], -1
    while True:
        rows = _fetch_once(api, trace_id)
        names = {_field(o, "name") for o in rows}
        if rows and len(rows) == last and expect_names <= names:
            return rows
        last = len(rows)
        if time.time() > deadline:
            return rows
        time.sleep(TRACE_POLL_SECONDS)


def summarize(rows: list[Any]) -> dict[str, Any]:
    """Return the facts the tests assert on: segments, generations with usage, event names."""
    kinds = Counter(str(_field(o, "type")) for o in rows)
    segments = sorted(_field(o, "name") for o in rows
                      if str(_field(o, "name")).startswith("leafcutter.run"))
    generations = [o for o in rows if str(_field(o, "type")) == "GENERATION"]
    with_usage = [o for o in generations if _field(o, "usage_details", "usageDetails")]
    events = Counter(_field(o, "name") for o in rows if str(_field(o, "type")) == "EVENT")
    spans = Counter(_field(o, "name") for o in rows if str(_field(o, "type")) != "EVENT")
    return {"observations": len(rows), "types": dict(kinds), "segments": segments,
            "generations": len(generations), "generations_with_usage": len(with_usage),
            "models": sorted({str(_field(o, "model", "provided_model_name", "providedModelName")) for o in generations}),
            "events": dict(events), "spans": dict(spans)}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 17:00 [python-coder]: Synthetic answers carry a SYNTHETIC label in their text,
#   their actor id and relayed_by so a reader of the ledger or the trace can never mistake them
#   for a real host or human. (#KernelBootstrapV0/P10)
# ====================================================================
