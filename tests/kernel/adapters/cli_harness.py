"""
MODULE: tests.kernel.adapters.cli_harness
GOAL: Run the REAL `kernel.adapters.cli.main` in a child process over the test rig (scripted
    executors, a scripted Jev, real file stores and the real sqlite checkpointer), so CLI tests
    exercise argument parsing, exit codes and the one-JSON-document contract without the network.
BUSINESS CONTEXT: `python -m kernel` composes live Jev and Langfuse; tests must prove the same
    CLI code path offline, including a process killed at a precise point around a handoff.
ARCHITECTURE: Configured by environment variables (KERNEL_TEST_ROOT, KERNEL_TEST_KIND host|human,
    KERNEL_TEST_CRASH before_ledger|after_ledger|mid_flight, KERNEL_TEST_NOJEV) and invoked as
    `python -m tests.kernel.adapters.cli_harness <cli arguments>`; it exits with the CLI's code
    (or the injected crash code).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from kernel.adapters.cli import main
from kernel.bootstrap import KernelEnvironment
from tests.kernel.adapters.support import rig_environment
from tests.kernel.interaction.support import host_rig, human_rig


def environment(*, config_path: Path | None = None, env_file: Path | None = None
                ) -> KernelEnvironment:
    """Build the rig-backed environment the harness process runs against."""
    kind = os.environ.get("KERNEL_TEST_KIND", "host")
    rig = host_rig() if kind == "host" else human_rig()
    return rig_environment(Path(os.environ["KERNEL_TEST_ROOT"]), rig,
                           crash=os.environ.get("KERNEL_TEST_CRASH") or None,
                           with_jev=os.environ.get("KERNEL_TEST_NOJEV") != "1")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], environment=environment))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 13:10 [python-coder]: The harness swaps only the environment factory, so the
#   parser, exit-code mapping and output handling under test are the shipped ones.
#   (#KernelBootstrapV0/P7)
# ====================================================================
