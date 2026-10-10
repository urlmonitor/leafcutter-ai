"""A code-repair retest of two original exact cases, preserving blind host bytes."""
import argparse
import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

import public_eval as controller
from report_support.layout import require_unarchived_controller
from kernel.service import KernelService


async def main(output_directory: str) -> None:
    """Run the two predeclared repair cases with identical host response bytes.

    Args:
        output_directory: New one-shot repair evidence directory."""
    require_unarchived_controller()
    base = Path(__file__).resolve().parent
    baseline = base / "public-evaluation"
    controller.OUTPUT = base / output_directory
    out = controller.OUTPUT
    if out.exists():
        raise ValueError("One-shot repair evaluation already exists; do not overwrite or retry")
    cases = controller.read(base / "plan.json")["public_cases"][:2]
    revision = controller.read(baseline / "location.json")["code_revision"]
    plan = {"purpose": "Test the narrow source-field disclosure repair without favorable host regeneration.",
        "baseline": "public-evaluation", "prior_repair": "repair-evaluation" if output_directory == "final-verification" else None,
        "final_verification_reason": "Repeat only to verify final defensive empty-text guard at its actual working-code hash; no favorable-model retries." if output_directory == "final-verification" else None,
        "cases": [case["id"] for case in cases],
        "source_sha": revision, "host_response_policy": "Reuse each exact original blind interpretation byte-for-byte in a new real public wait only when the complete bound request is identical.",
        "generation": "No new host generation; fresh real TypeSafe Jev decisions.",
        "changes_allowed": "Production source-field disclosure only; no question, source data, gold, threshold or prompt changes.",
        "success": "Canonical criteria and authored test_spec delivered with exact field citations; no missing requested facts; final public status completed.",
        "bounds": {"new_public_runs": 2, "new_jev_calls_max": 24, "prior_actual_jev_calls": 11 if output_directory == "final-verification" else 7,
            "approved_total_jev_max": 72, "new_accepted_host_results_max": 6, "prior_accepted_host_results": 10 if output_directory == "final-verification" else 8,
            "approved_total_accepted_host_max": 16, "graph_writes": 0, "catalog_writes": 0, "telemetry_exports": 0}}
    controller.save(out / "pre-execution-plan.json", plan)
    host_root = Path(tempfile.mkdtemp(prefix="leafcutter-public-repair-"))
    controller.save(out / "location.json", {"host_root": str(host_root), "source_mode": "local",
        "code_revision": revision, "host_response_generation": "unchanged baseline bytes reused", "expected_labels_sent": False})
    controller.save(out / "working-source-freeze.json", controller.working_source_fingerprint())
    for case in cases:
        ident = case["id"]
        _, task = controller.config(case, "local", host_root, revision)
        env, tracer = controller.environment(ident, "local")
        try:
            result = await asyncio.wait_for(KernelService(env).start_run(task), timeout=160)
            await controller.receipt(ident, "started", env, tracer, result)
            new_input = controller.read(Path(result.pending_interaction.input_artifact_refs[0]))
        finally:
            await env.aclose()
        original_packet = controller.read(baseline / "host-artifacts" / "packets" / f"{ident}.started.json")
        old_input = controller.read(baseline / "host-artifacts" / "inputs" / Path(original_packet["input_artifact_refs"][0]).name)
        if old_input["request"] != new_input["request"]:
            raise ValueError("Prepared request differs from original blind interpretation binding")
        original = baseline / "host-artifacts" / "responses" / f"{ident}.started.json"
        pending = controller.read(out / f"{ident}.pending-host.json")
        destination = Path(pending["response_destination"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(original.read_bytes())
        controller.save(out / f"{ident}.response-origin.json", {"original": str(original),
            "sha256": hashlib.sha256(original.read_bytes()).hexdigest(), "new_response_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "bound_request_identical": True, "new_host_generation": False})
        await controller.resume(ident, False)
    print(json.dumps({"repair_output": str(out), "baseline_preserved": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", choices=("repair-evaluation", "final-verification"), default="repair-evaluation")
    asyncio.run(main(parser.parse_args().output))
