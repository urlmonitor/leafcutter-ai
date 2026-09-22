"""
MODULE: build_shim_probe
GOAL: Recompute the shim method a build run can actually use under
    ``shim_strategy: "auto"`` -- a real, disposable symlink probe, never a
    trust of the declared configuration string.
BUSINESS CONTEXT: Split out of ``build_ownership.py`` (BP-1500g-1 second-
    review-round, ADR-041 §1) purely for file-size-ratchet headroom:
    ``build_ownership.py`` was already at its 400-line new-file cap with no
    margin left, and this probe-hardening fix could not fit there without
    either growing past the cap or deleting the explanatory comments the
    ratchet review explicitly forbids trimming for headroom. The function
    has exactly one behavioural caller convention: given the declared
    ``shim_strategy`` string and the target root, return the strategy this
    run will actually use, so every ownership decision (claim-side in
    ``build_helpers.install_shims``, removal-side in ``build.py``'s
    ``main()``) agrees with what the build can really do, per ADR-041's
    "attribution is recomputed, not declared" principle.
ARCHITECTURE: Standalone, no shared state; imported by ``build.py`` and
    ``build_helpers.py``. Neither of those two files, nor this one, is ever
    part of a consumer's deployed install: all three are the build tool
    itself, always run from the source tree (confirmed the same way
    ``build_ownership.py``'s own decision history recorded for that
    module -- no deploy-map entry is needed here either).
"""

from __future__ import annotations

import os
from pathlib import Path

from build_colors import warn as _warn


def resolve_effective_shim_strategy(strategy: str, target_root: Path) -> str:
    """Recompute the shim method THIS run can actually use, per ADR-041 §1 --
    never trust the declared ``shim_strategy`` string for an ownership
    decision. ``"copy"``/``"symlink"`` are explicit opt-ins and already ARE
    the method; only ``"auto"`` is resolved, via the same real, disposable
    symlink probe ``_create_shim`` itself relies on, so a platform where
    symlink creation genuinely fails is attributed ``"copy"`` for every
    ownership decision this run -- not only after ``_create_shim`` already
    silently degraded to it on some earlier path.

    The probe path is keyed on the PID, and PIDs are reused: a leftover
    probe from an earlier killed run at the same PID would make
    ``symlink_to`` raise ``FileExistsError`` -- an ``OSError`` -- which must
    never be mistaken for "this platform cannot create symlinks". The
    leading ``unlink(missing_ok=True)`` clears exactly that leftover (a
    no-op when none exists) before the real probe attempt, so only a
    genuine symlink-creation failure reaches the ``except`` below. A
    failure to remove the probe AFTER a successful symlink is logged
    (never silently dropped, CLAUDE.md Rule 3) but does not fail the
    build -- the capability was already confirmed, and the same leading
    ``unlink`` self-heals the leftover on the next run.

    Args:
        strategy: The declared ``shim_strategy`` (``"symlink"``, ``"copy"``,
            or ``"auto"``).
        target_root: The target project root the disposable probe is
            created inside (and removed from).

    Returns:
        ``strategy`` unchanged for an explicit ``"symlink"``/``"copy"``;
        for ``"auto"``, the recomputed ``"symlink"`` or ``"copy"``.
    """
    if strategy != "auto":
        return strategy
    probe = target_root / f".leafcutter-shim-probe-{os.getpid()}"
    try:
        probe.unlink(missing_ok=True)
        probe.symlink_to(target_root)
    except OSError:
        return "copy"
    try:
        probe.unlink()
    except OSError as exc:
        _warn(f"Could not remove disposable shim probe {probe}: {exc}")
    return "symlink"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/BP-1500g-1 second-review-round, probe
#   hardening]: Created this module by moving resolve_effective_shim_
#   strategy out of build_ownership.py (that file was at its 400-line cap
#   with no margin). Hardened it against two defects: (1) a stale probe
#   left at the same PID by an earlier killed run raised FileExistsError,
#   which was indistinguishable from a genuine symlink-creation failure --
#   fixed with a leading unlink(missing_ok=True); (2) a successful probe
#   whose cleanup unlink() failed leaked the file for the next run to trip
#   over, silently -- now logged (CLAUDE.md Rule 3) and self-healed by the
#   same leading unlink on the next call. Also wired resolve_effective_
#   shim_strategy into build_helpers.install_shims's claim-side strategy
#   resolution, which had been left reading the declared config string
#   directly -- the asymmetry ADR-041 review flagged: the removal side
#   already used the recomputed value, the claim side did not, so the two
#   sides could disagree about what strategy this run actually used.
#   (#BP-1500g-1/adr-041-review/probe-hardening)
# ====================================================================
