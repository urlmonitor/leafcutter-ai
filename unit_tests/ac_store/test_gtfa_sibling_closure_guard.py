"""
MODULE: unit_tests/ac_store/test_gtfa_sibling_closure_guard.py
GOAL: Prove that scripts/ac_store/generate_ticket_from_ac.py's derived
    intra-package dependency closure still reaches every ``_gtfa_*`` sibling it
    is split across, so the deploy-manifest guard can see them.

WHY THIS EXISTS
    generate_ticket_from_ac.py was 4035 lines until it was split into a 386-line
    shell over 22 ``_gtfa_*`` sibling modules. The shell resolves those siblings
    through ``importlib.import_module`` with a name COMPUTED from ``__name__``,
    because the prefix differs between the two layouts the module is imported
    under (package-qualified ``scripts.ac_store.generate_ticket_from_ac``, and
    bare ``generate_ticket_from_ac`` after a ``sys.path`` push).

    A computed module name is undecidable statically. So
    scripts/build_referential_integrity.py's closure analyser — the thing
    build.py's deploy-manifest guard depends on — sees NO dependency from the
    shell to any sibling, and the guard goes blind to the entire generator. An
    unlisted sibling then ships a generator that is dead at import in the
    deployed layout, while every source-importing unit test stays green,
    because the source tree has every module by construction.

    The shell carries an ``if TYPE_CHECKING:`` block of relative imports that
    exists for exactly one reason: to restore that closure. It is never
    executed. Measured during the split, removing it drops the shell's closure
    from 27 entries to ZERO.

    That block therefore looks like dead code, and is kept alive only by
    ``# noqa: F401`` plus prose. Ruff selects ``F``. A single "remove unused
    imports" autofix — or a well-meaning manual tidy — silently returns the
    closure to zero and re-arms the precise BP-900g-8 failure mode, with no
    test anywhere noticing. This file is that missing test.

ARCHITECTURE
    One behavioural assertion, derived rather than hand-listed: enumerate the
    ``_gtfa_*.py`` files actually on disk, compute the shell's closure via the
    same ``compute_intra_package_closure`` the build guard uses, and require
    the closure to contain every one of them. Deriving the expected set means a
    sibling added tomorrow is covered with no list to edit here — the same
    binding-direction rule BP-900g-8 established for the deploy_map itself.

    Asserting containment of a DERIVED set, rather than merely
    ``len(closure) > 0``, is deliberate: a closure that resolved only
    ``_component_migration_map.py`` would satisfy a non-empty check while the
    22 siblings that matter stayed invisible.

DECISION HISTORY
    - 2026-09-14: Created alongside the generate_ticket_from_ac.py split. The
      IT-PO wiring audit of that split verified the closure behaviourally
      (negative-controlled by removing manifest entries one at a time) and
      found the mechanism sound, but flagged that NOTHING guards it going
      forward. Filed as the MEDIUM finding of that audit.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_referential_integrity as _bri  # noqa: E402 -- after sys.path setup

_AC_STORE_DIR = _SCRIPTS_DIR / "ac_store"
_SHELL = _AC_STORE_DIR / "generate_ticket_from_ac.py"


def test_generator_shell_closure_reaches_every_gtfa_sibling() -> None:
    """The shell's derived closure must contain every `_gtfa_*` sibling on disk.

    Fails if the ``if TYPE_CHECKING:`` declaration block in the shell is
    removed or trimmed, which is what an `F401` autofix would do.
    """
    on_disk = {
        f"scripts/ac_store/{path.name}"
        for path in sorted(_AC_STORE_DIR.glob("_gtfa_*.py"))
    }
    assert on_disk, (
        "No _gtfa_*.py siblings found in scripts/ac_store/. Either the split "
        "was reverted or this test's glob is wrong; both need a human."
    )

    closure = _bri.compute_intra_package_closure(_SHELL, _REPO_ROOT)
    missing = sorted(on_disk - closure)

    assert not missing, (
        "generate_ticket_from_ac.py's derived dependency closure no longer "
        f"reaches {len(missing)} of its {len(on_disk)} _gtfa_* siblings: "
        f"{missing}.\n\n"
        "The shell imports siblings via importlib with a COMPUTED name, which "
        "is invisible to static analysis. The `if TYPE_CHECKING:` block of "
        "relative imports near the top of the shell is what makes them "
        "visible to build_referential_integrity's analyser, and it is the "
        "only thing that does. If it was removed as 'unused imports', restore "
        "it -- without it build.py's deploy-manifest guard cannot see the "
        "generator's dependencies at all, and an unshipped sibling produces a "
        "generator that is dead at import in the deployed layout while every "
        "source-tree test stays green."
    )
