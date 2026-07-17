"""
MODULE: test_finalize_howto
GOAL: Verify that docs/how-to/finalize-feature.md accurately describes the
null-baseline targeted-rerun recovery behavior (FIN-100c-10) and no longer
presents the old blanket-halt narrative as the current Step 3 behavior.

Nature: TDD test stubs — MUST be RED until documentation-expert updates
docs/how-to/finalize-feature.md per the FIN-100c-10 acceptance criteria.

All tests here read the how-to doc as text and assert:
  (a) Stale phrases are ABSENT — currently they ARE present, so tests fail.
  (b) New phrases describing the targeted rerun are PRESENT — currently absent.

ACs: FIN-100c-10
TICKET: TICKET-20260715-FinalizeBaselineFallbackTargetedRerun
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOWTO_PATH = _REPO_ROOT / "docs" / "how-to" / "finalize-feature.md"

# Stale phrase in the Step 0 table row (~L32) that must be removed or reframed.
# Currently states the blanket-regression behavior as the CURRENT consequence
# of a failed baseline capture. After the update it should describe the
# targeted rerun as primary and the conservative halt as the fallback.
_STALE_BLANKET_PHRASE = (
    "triage will classify all post-merge failures conservatively as regressions"
)

# Stale troubleshooting advice at ~L91-99 that attributes a false regression
# to a "transient failure" of the baseline capture. After FIN-100c-4..9 the
# targeted rerun handles this automatically — the advice is no longer current.
_STALE_TROUBLESHOOTING_PHRASE = "the triage baseline capture"


def _howto() -> str:
    """Return the full text of docs/how-to/finalize-feature.md."""
    return _HOWTO_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# FIN-100c-10: Step 0 narrative drops the blanket-regression-as-current framing
# ---------------------------------------------------------------------------


def test_howto_step0_drops_blanket_regression_as_current():
    # covers: FIN-100c-10
    """FIN-100c-10: The Step 0 narrative in docs/how-to/finalize-feature.md no
    longer presents an unavailable baseline as causing triage to classify all
    post-merge failures conservatively as regressions as the current behavior.

    The stale phrase (currently at ~L32) must be removed or reframed: an
    unavailable baseline now triggers the targeted per-test rerun (FIN-100c-4/5/6),
    and the conservative all-regressions halt is only the rerun-unavailable
    fallback (FIN-100c-9).

    To make this test green:
      Remove or rewrite the stale Step 0 table row text so the phrase
      '{_STALE_BLANKET_PHRASE}' is no longer present as a description of the
      CURRENT primary behavior.
    """
    text = _howto()
    assert _STALE_BLANKET_PHRASE not in text, (
        "docs/how-to/finalize-feature.md still contains the stale Step 0 phrase:\n"
        f"  '{_STALE_BLANKET_PHRASE}'\n"
        "This narrative must be removed or reframed — the targeted per-test rerun "
        "against main HEAD (FIN-100c-4/5/6) is now the primary path when the Step 0 "
        "baseline is unavailable. The conservative all-regressions halt is only the "
        "narrowed rerun-unavailable fallback (FIN-100c-9)."
    )


# ---------------------------------------------------------------------------
# FIN-100c-10: Step 3 / test_regression section describes the targeted rerun
# ---------------------------------------------------------------------------


def test_howto_step3_describes_targeted_rerun_recovered_baseline():
    # covers: FIN-100c-10
    """FIN-100c-10: The Step 3 row and the test_regression halt section describe
    the targeted per-test rerun against main HEAD that recovers a baseline and
    distinguishes pre_existing from regression when the Step 0 baseline is null.

    Both 'targeted rerun' and 'recovered baseline' must appear in the updated
    guide. Neither is currently present.

    To make this test green:
      Update the Step 3 row (~L35) and the test_regression halt section (~L68-99)
      to describe the targeted rerun of only the failing test IDs against main HEAD
      (after the same build/deploy step), the recovered baseline supplied to triage
      in place of null, and pre_existing-vs-regression classification over that
      recovered baseline.
    """
    text = _howto()
    assert "targeted rerun" in text, (
        "docs/how-to/finalize-feature.md must describe the 'targeted rerun' of "
        "the failing test IDs against main HEAD in the Step 3 / test_regression "
        "section. Currently absent."
    )
    assert "recovered baseline" in text, (
        "docs/how-to/finalize-feature.md must describe the 'recovered baseline' "
        "built from the main-HEAD rerun results (supplied to triage in place of null). "
        "Currently absent."
    )


# ---------------------------------------------------------------------------
# FIN-100c-10: Conservative halt is narrowed to rerun-unavailable fallback,
#              surfacing modified_by_branch for human adjudication
# ---------------------------------------------------------------------------


def test_howto_conservative_halt_narrowed_to_fallback_with_modified_by_branch():
    # covers: FIN-100c-10
    """FIN-100c-10: The guide describes the conservative all-regressions halt as the
    narrowed rerun-unavailable fallback and states it surfaces each failing test's
    modified_by_branch flag for human adjudication.

    'modified_by_branch' must appear in the updated guide. It is currently absent.

    To make this test green:
      Describe the conservative halt as the fallback triggered only when the
      main-HEAD checkout or build/deploy step fails (FIN-100c-9), and state that
      this fallback surfaces each failing test's modified_by_branch flag so a
      human can adjudicate which failures the branch actually touched.
    """
    text = _howto()
    assert "modified_by_branch" in text, (
        "docs/how-to/finalize-feature.md must mention the 'modified_by_branch' "
        "flag surfaced in the conservative (rerun-unavailable) fallback halt message "
        "for human adjudication. Currently absent."
    )


# ---------------------------------------------------------------------------
# FIN-100c-10: No remaining passage presents old null-baseline behavior as current
# ---------------------------------------------------------------------------


def test_howto_has_no_stale_null_baseline_all_regressions_as_current():
    # covers: FIN-100c-10
    """FIN-100c-10: No remaining passage in the guide presents the old
    'null baseline -> all post-merge failures are regressions -> halt' behavior
    as the current Step 3 behavior, including the misclassification-troubleshooting
    text at ~L91-99 that attributes a false regression to a transient baseline failure.

    Both stale phrases must be absent after the documentation update.

    To make this test green:
      (1) Remove/reframe the stale Step 0 table row phrase.
      (2) Remove/rewrite the misclassification-troubleshooting paragraph (~L91-99)
          that advises re-running to get a fresh baseline — the targeted rerun now
          handles this automatically.
    """
    text = _howto()
    assert _STALE_BLANKET_PHRASE not in text, (
        "docs/how-to/finalize-feature.md still contains the stale blanket-regression "
        f"phrase: '{_STALE_BLANKET_PHRASE}' — must be removed."
    )
    assert _STALE_TROUBLESHOOTING_PHRASE not in text, (
        "docs/how-to/finalize-feature.md still contains the stale troubleshooting "
        f"phrase: '{_STALE_TROUBLESHOOTING_PHRASE}' (~L91-99). This guidance is no "
        "longer current — the targeted rerun now automatically handles the "
        "baseline-transient-failure scenario. Remove or rewrite this section."
    )
