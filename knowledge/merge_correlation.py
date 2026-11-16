"""MODULE: merge_correlation
GOAL: Identify one synchronization job independently of any retrieval request.
BUSINESS CONTEXT: Operators match a merge job's outcome to its repository, commit and generation.
ARCHITECTURE: Pure helper read by cli_sync; carries only identifiers, never credentials.

DECISION HISTORY
========================================
- 2026-11-16 12:00 [python-coder]: Add the merge-job correlation carried on every sync result. (#KM-400e-5)
"""

from __future__ import annotations

from collections.abc import Mapping


def merge_job_correlation(
    environ: Mapping[str, str], repository_id: str, source_sha: str, generation_id: str
) -> dict[str, str | None]:
    """Build the correlation of one merge job from the runner's identifiers.

    Args:
        environ: Process environment; only the runner's run id and attempt are read.
        repository_id: Trusted repository namespace the job published into.
        source_sha: Immutable commit the job validated.
        generation_id: Generation identity derived from that commit.

    Returns:
        Run id, attempt, repository, commit and generation; no retrieval request id.
    """
    return {
        "run_id": environ.get("GITHUB_RUN_ID"),
        "run_attempt": environ.get("GITHUB_RUN_ATTEMPT"),
        "repository_id": repository_id,
        "source_sha": source_sha,
        "generation_id": generation_id,
    }
