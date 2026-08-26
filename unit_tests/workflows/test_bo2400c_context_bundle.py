"""
MODULE: unit_tests/workflows/test_bo2400c_context_bundle.py
GOAL: RED test stubs for BO-2400c-1, BO-2400c-3, BO-2400c-5.

=== BO-2400c-1-vi call-site audit (2026-08-26) ===

Every call to assemble_context_bundle() in this file originally passed
conventions= and acs=. BO-2400c-1-vi removes both parameters from the
function entirely (not defaulted to None — removed, so no caller can
reintroduce the duplicate), so this file is a declared call site
(BO-2400c-1-vi.yaml's it_requirements constraint list) updated in the SAME
change to the post-change three-layer signature below. Tests whose entire
point was the removed layer (e.g. "conventions sits in the stable prefix",
"acs precedes prior_tests") are rewritten against the surviving three-layer
set rather than deleted, per that AC's own instruction.

Classification (Source-of-Truth Discipline Rule 1): this is TEST DRIFT, not
production drift — assemble_context_bundle() has not changed yet, so every
rewritten call below now omits arguments the CURRENT (unmodified) function
still requires as keyword-only parameters with no default. That raises
TypeError at call time until BO-2400c-1-vi lands — a real, correctly-red
signal, not noise. (classification: test_drift)

=== Interface contract under test (to be implemented by python-coder) ===

Location: scripts/injection_builders.py

    assemble_context_bundle(
        *,
        architecture: str,
        high_level: str,
        prior_tests: str,
        prior_outputs: str | None = None,
        working_diff: str | None = None,
        breakpoint_marker: str = "<!-- CACHE_BREAKPOINT -->",
    ) -> str

  Layer ordering contract (stable-first by change-frequency, per BO-2400c-5,
  as narrowed by BO-2400c-1-vi):

      Position 1 (earliest) — architecture
          The relevant architecture docs.  Changes most rarely.  Always placed
          in the stable prefix (before the breakpoint), never in the variable
          suffix.

      Position 2 — high_level
          The L0/L1 parent ACs describing the big picture.  Changes rarely.
          Always in the stable prefix.

      [breakpoint_marker]
          A single delimiter separating the stable prefix from the variable
          suffix.  Exactly one occurrence in the output.

      Position 3 (first in variable suffix) — prior_tests
          Tests already written for the same area/component.  Moderately
          volatile.  Always after the breakpoint.

      Position 4 — prior_outputs   (optional; None → omitted)
          Prior-phase distilled outputs carried forward (BO-2400c-3).  Variable
          per run.  After the breakpoint only — never in the stable prefix.

      Position 5 (latest) — working_diff   (optional; None → omitted)
          The most volatile layer: the current working diff.  After the
          breakpoint only.

  ``conventions`` and ``acs`` are REMOVED (BO-2400c-1-vi): the receiving agent
  already has the project conventions (the harness that dispatches it injects
  them) and can already open the run's own AC store, so carrying either as a
  bundle layer duplicated content the agent already had — 129,178 of 148,891
  bytes (87%) on the run that failed.

  Cacheable-prefix property (BO-2400c-1):
      Given the same values of (architecture, high_level, breakpoint_marker),
      the substring of the output from position 0 up to and including the
      breakpoint marker must be byte-identical regardless of what
      prior_tests, prior_outputs, or working_diff contain.

  Threading contract (BO-2400c-3):
      When prior_outputs is supplied, it must appear in the variable suffix
      (after the breakpoint), not in the stable prefix.  The stable prefix must
      NOT contain the prior_outputs content.  prior_outputs carries the
      distilled result of a prior phase; the raw inputs that phase already
      processed must NOT be re-included in the stable prefix for re-derivation.

=== Red baseline ===

  All tests in this file are RED again as of BO-2400c-1-vi's call-site audit:
  every call below now omits conventions=/acs=, which the CURRENT
  (unmodified) assemble_context_bundle() still requires as keyword-only
  arguments with no default. The resulting TypeError is the intended red
  state — it confirms the signature has not yet been narrowed.

=== Fixture-authenticity note ===

  These tests exercise a pure string-assembly function.  All inputs are plain
  string arguments (no serialised-file fixtures needed — compliant with the
  MANDATORY fixture-authenticity mandate for pure-logic tests).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as sibling workflow tests
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

# This import will raise ImportError (or AttributeError on the name) until
# python-coder adds assemble_context_bundle to scripts/injection_builders.py.
# That error IS the intended red state — it confirms the production code does
# not yet exist.
from injection_builders import assemble_context_bundle  # noqa: E402

# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

_DEFAULT_BREAKPOINT = "<!-- CACHE_BREAKPOINT -->"

# Unique sentinel strings that cannot accidentally appear in another layer.
# _CONV_SENTINEL and _ACS_SENTINEL are gone (BO-2400c-1-vi): the conventions
# and acs layers no longer exist as parameters or as bundle content.
_ARCH_SENTINEL = "LAYER_ARCH_SENTINEL_A1B2C3"
_HL_SENTINEL = "LAYER_HL_SENTINEL_G7H8I9"
_PTESTS_SENTINEL = "LAYER_PTESTS_SENTINEL_M3N4O5"
_POUTPUTS_SENTINEL = "LAYER_POUTPUTS_SENTINEL_P6Q7R8"
_DIFF_SENTINEL = "LAYER_DIFF_SENTINEL_S9T0U1"


def _full_bundle(
    *,
    breakpoint_marker: str = _DEFAULT_BREAKPOINT,
    prior_outputs: str | None = None,
    working_diff: str | None = None,
) -> str:
    """Call assemble_context_bundle with sentinel-labelled layer strings.

    Returns the assembled string for inspection.

    Args:
        breakpoint_marker: The cache-breakpoint delimiter to embed.
        prior_outputs: Prior-phase distilled outputs, or None to omit.
        working_diff: Working diff (most volatile layer), or None to omit.

    Returns:
        The assembled context bundle string.
    """
    return assemble_context_bundle(
        architecture=_ARCH_SENTINEL,
        high_level=_HL_SENTINEL,
        prior_tests=_PTESTS_SENTINEL,
        prior_outputs=prior_outputs,
        working_diff=working_diff,
        breakpoint_marker=breakpoint_marker,
    )


# ---------------------------------------------------------------------------
# BO-2400c-1 — Static boilerplate before breakpoint; variable content after
# ---------------------------------------------------------------------------


class TestStaticBoilerplateBeforeBreakpoint(unittest.TestCase):
    """BO-2400c-1: Static boilerplate appears strictly before the breakpoint marker;
    all variable content appears strictly after it."""

    def test_ac1_static_boilerplate_before_breakpoint(self) -> None:
        # covers: BO-2400c-1
        """Architecture and high-level picture appear BEFORE the breakpoint.

        BO-2400c-1-vi note: conventions is no longer a layer at all — this
        test no longer checks its position.

        To make this green, assemble_context_bundle must:
        - Place architecture and high_level content before breakpoint_marker
        - Confirm their positions are all strictly less than the breakpoint position
        """
        result = _full_bundle()

        bp_pos = result.index(_DEFAULT_BREAKPOINT)

        arch_pos = result.index(_ARCH_SENTINEL)
        hl_pos = result.index(_HL_SENTINEL)

        self.assertLess(
            arch_pos,
            bp_pos,
            "Architecture layer must appear BEFORE the cache breakpoint marker.",
        )
        self.assertLess(
            hl_pos,
            bp_pos,
            "High-level (L0/L1) layer must appear BEFORE the cache breakpoint marker.",
        )

    def test_ac1_variable_content_after_breakpoint(self) -> None:
        # covers: BO-2400c-1
        """Prior tests and prior-phase outputs appear AFTER the breakpoint marker.

        BO-2400c-1-vi note: acs is no longer a layer at all — this test no
        longer checks its position; prior_tests is now the first volatile
        layer.

        To make this green, assemble_context_bundle must:
        - Place prior_tests and prior_outputs after the breakpoint_marker
        - Their positions in the returned string must be strictly greater than
          the position of the breakpoint_marker + len(breakpoint_marker)
        """
        result = _full_bundle(prior_outputs=_POUTPUTS_SENTINEL)

        bp_end = result.index(_DEFAULT_BREAKPOINT) + len(_DEFAULT_BREAKPOINT)

        ptests_pos = result.index(_PTESTS_SENTINEL)
        poutputs_pos = result.index(_POUTPUTS_SENTINEL)

        self.assertGreater(
            ptests_pos,
            bp_end,
            "Prior tests must appear AFTER the cache breakpoint marker.",
        )
        self.assertGreater(
            poutputs_pos,
            bp_end,
            "Prior-phase outputs must appear AFTER the cache breakpoint marker.",
        )

    def test_ac1_exactly_one_breakpoint_marker(self) -> None:
        # covers: BO-2400c-1
        """The assembled output must contain exactly one cache breakpoint marker.

        To make this green, assemble_context_bundle must emit the
        breakpoint_marker string exactly once — no duplications, no omissions.
        """
        result = _full_bundle(
            prior_outputs=_POUTPUTS_SENTINEL, working_diff=_DIFF_SENTINEL
        )
        count = result.count(_DEFAULT_BREAKPOINT)
        self.assertEqual(
            count,
            1,
            f"Expected exactly 1 cache breakpoint marker; found {count}.",
        )

    def test_ac1_stable_prefix_byte_identical_across_invocations(self) -> None:
        # covers: BO-2400c-1
        """The stable prefix (up to and including the breakpoint) is byte-identical
        when stable inputs are unchanged but volatile inputs differ.

        This confirms the cacheable-prefix property: an LLM KV cache can be
        anchored on the stable prefix because it never varies when the agent
        role/architecture are unchanged. BO-2400c-1-vi note: conventions and
        acs are gone — the stable prefix is architecture + high_level +
        breakpoint_marker only, and the volatile inputs varied below are
        prior_tests/prior_outputs/working_diff.

        To make this green, assemble_context_bundle must:
        - Construct the stable prefix exclusively from architecture,
          high_level, and breakpoint_marker (in that order)
        - NOT mix any prior_tests, prior_outputs, or working_diff content
          into the stable prefix
        """
        stable_kwargs = dict(
            architecture=_ARCH_SENTINEL,
            high_level=_HL_SENTINEL,
            breakpoint_marker=_DEFAULT_BREAKPOINT,
        )

        result1 = assemble_context_bundle(
            **stable_kwargs,
            prior_tests="tests-version-ONE",
            prior_outputs="prior-outputs-ONE",
            working_diff="diff-ONE",
        )
        result2 = assemble_context_bundle(
            **stable_kwargs,
            prior_tests="tests-version-TWO",
            prior_outputs="prior-outputs-TWO",
            working_diff="diff-TWO",
        )

        bp = _DEFAULT_BREAKPOINT
        prefix1 = result1[: result1.index(bp) + len(bp)]
        prefix2 = result2[: result2.index(bp) + len(bp)]

        self.assertEqual(
            prefix1,
            prefix2,
            "Stable prefix (up to and including the breakpoint marker) must be "
            "byte-identical when stable inputs (architecture, conventions, "
            "high_level, breakpoint_marker) are unchanged, regardless of "
            "volatile inputs (acs, prior_tests, prior_outputs, working_diff).",
        )

    def test_ac1_stable_prefix_contains_only_stable_inputs(self) -> None:
        # covers: BO-2400c-1
        """The stable prefix must not contain any volatile-layer content.

        Volatile inputs (prior_tests, prior_outputs, working_diff) must
        NOT appear in the portion of the assembled string that precedes the
        breakpoint marker. BO-2400c-1-vi note: acs is no longer a parameter
        at all, so it is no longer checked here.

        To make this green, assemble_context_bundle must build the stable
        section without ever incorporating per-request variable data.
        """
        result = _full_bundle(
            prior_outputs=_POUTPUTS_SENTINEL, working_diff=_DIFF_SENTINEL
        )

        bp_pos = result.index(_DEFAULT_BREAKPOINT)
        stable_prefix = result[:bp_pos]

        self.assertNotIn(
            _PTESTS_SENTINEL,
            stable_prefix,
            "Prior tests sentinel must NOT appear in the stable prefix.",
        )
        self.assertNotIn(
            _POUTPUTS_SENTINEL,
            stable_prefix,
            "Prior-phase outputs sentinel must NOT appear in the stable prefix.",
        )
        self.assertNotIn(
            _DIFF_SENTINEL,
            stable_prefix,
            "Working diff sentinel must NOT appear in the stable prefix.",
        )

    def test_ac1_custom_breakpoint_marker_used(self) -> None:
        # covers: BO-2400c-1
        """A custom breakpoint_marker argument must be used instead of the default.

        To make this green, assemble_context_bundle must respect the caller's
        breakpoint_marker parameter (not hardcode the default).
        """
        custom_bp = "---CUSTOM-CACHE-SPLIT---"
        result = assemble_context_bundle(
            architecture=_ARCH_SENTINEL,
            high_level=_HL_SENTINEL,
            prior_tests=_PTESTS_SENTINEL,
            breakpoint_marker=custom_bp,
        )
        self.assertIn(
            custom_bp,
            result,
            "Custom breakpoint_marker must appear in the assembled output.",
        )
        # The default marker must NOT appear when a custom one is supplied.
        self.assertNotIn(
            _DEFAULT_BREAKPOINT,
            result,
            "Default breakpoint marker must NOT appear when a custom one is provided.",
        )


# ---------------------------------------------------------------------------
# BO-2400c-3 — Prior-phase distilled outputs in variable suffix only
# ---------------------------------------------------------------------------


class TestPriorPhaseOutputThreading(unittest.TestCase):
    """BO-2400c-3: Prior-phase distilled outputs are threaded into the variable suffix,
    not placed in the stable prefix and not re-derived from raw inputs."""

    def test_ac3_prior_phase_output_in_variable_suffix(self) -> None:
        # covers: BO-2400c-3
        """When prior_outputs is provided, it appears in the variable suffix (after
        the breakpoint marker) in the assembled prompt.

        To make this green, assemble_context_bundle must:
        - Accept a 'prior_outputs' keyword argument
        - Include it in the output at a position after the breakpoint_marker
        """
        result = _full_bundle(prior_outputs=_POUTPUTS_SENTINEL)

        self.assertIn(
            _POUTPUTS_SENTINEL,
            result,
            "prior_outputs content must be present in the assembled bundle.",
        )
        bp_end = result.index(_DEFAULT_BREAKPOINT) + len(_DEFAULT_BREAKPOINT)
        poutputs_pos = result.index(_POUTPUTS_SENTINEL)
        self.assertGreater(
            poutputs_pos,
            bp_end,
            "prior_outputs must appear in the variable suffix, AFTER the breakpoint.",
        )

    def test_ac3_prior_output_absent_from_stable_prefix(self) -> None:
        # covers: BO-2400c-3
        """Prior-phase distilled outputs must NOT appear in the stable prefix.

        Threading prior_outputs into the stable prefix would destroy its
        cacheability (the stable prefix must be byte-identical across
        invocations — BO-2400c-1 cross-constraint).

        To make this green, assemble_context_bundle must never place
        prior_outputs before the cache breakpoint.
        """
        result = _full_bundle(prior_outputs=_POUTPUTS_SENTINEL)

        bp_pos = result.index(_DEFAULT_BREAKPOINT)
        stable_prefix = result[:bp_pos]

        self.assertNotIn(
            _POUTPUTS_SENTINEL,
            stable_prefix,
            "Prior-phase outputs must NOT appear in the stable prefix "
            "(before the breakpoint marker).",
        )

    def test_ac3_prior_outputs_none_omitted_from_bundle(self) -> None:
        # covers: BO-2400c-3
        """When prior_outputs=None the sentinel is absent from the bundle.

        To make this green, assemble_context_bundle must skip any section for
        prior_outputs when that argument is None (or not provided).
        """
        result = _full_bundle(prior_outputs=None)

        self.assertNotIn(
            _POUTPUTS_SENTINEL,
            result,
            "When prior_outputs=None, no prior-outputs content should appear.",
        )

    def test_ac3_prior_outputs_after_prior_tests_in_variable_suffix(self) -> None:
        # covers: BO-2400c-3
        """prior_outputs must appear after prior_tests in the variable suffix.

        BO-2400c-1-vi note: this test's original point was the now-removed
        acs → prior_tests ordering; rewritten against the surviving
        three-layer set per that AC's own instruction. The ordering within
        the variable suffix is now: prior_tests → prior_outputs
        (→ working_diff).  Threading prior_outputs BEFORE prior_tests would
        violate the change-frequency ordering contract.

        To make this green, assemble_context_bundle must emit prior_outputs at
        a later position than prior_tests in the assembled string.
        """
        result = _full_bundle(prior_outputs=_POUTPUTS_SENTINEL)

        ptests_pos = result.index(_PTESTS_SENTINEL)
        poutputs_pos = result.index(_POUTPUTS_SENTINEL)

        self.assertGreater(
            poutputs_pos,
            ptests_pos,
            "prior_outputs must appear AFTER prior_tests in the variable "
            "suffix — distilled outputs from a prior phase follow the "
            "component's prior tests.",
        )

    def test_ac3_stable_prefix_unchanged_regardless_of_prior_outputs(self) -> None:
        # covers: BO-2400c-3
        """The stable prefix must be byte-identical whether prior_outputs is None or set.

        This cross-validates BO-2400c-3 with the BO-2400c-1 cacheability rule:
        threading prior_outputs into the variable suffix must not leak content
        into the stable prefix.

        To make this green, assemble_context_bundle must keep the stable prefix
        free of prior_outputs even when prior_outputs is provided.
        """
        stable_kwargs = dict(
            architecture=_ARCH_SENTINEL,
            high_level=_HL_SENTINEL,
            prior_tests=_PTESTS_SENTINEL,
            breakpoint_marker=_DEFAULT_BREAKPOINT,
        )

        result_no_prior = assemble_context_bundle(**stable_kwargs, prior_outputs=None)
        result_with_prior = assemble_context_bundle(
            **stable_kwargs, prior_outputs=_POUTPUTS_SENTINEL
        )

        bp = _DEFAULT_BREAKPOINT
        prefix_no_prior = result_no_prior[: result_no_prior.index(bp) + len(bp)]
        prefix_with_prior = result_with_prior[: result_with_prior.index(bp) + len(bp)]

        self.assertEqual(
            prefix_no_prior,
            prefix_with_prior,
            "The stable prefix must be byte-identical whether prior_outputs is "
            "None or set — prior_outputs content must be confined to the "
            "variable suffix only.",
        )


# ---------------------------------------------------------------------------
# BO-2400c-5 — Layered context bundle ordered by change-frequency
# ---------------------------------------------------------------------------


class TestLayeredContextBundleOrdering(unittest.TestCase):
    """BO-2400c-5: The context bundle is layered by change-frequency (stable-first):
    architecture/high_level (stable) → prior_tests → prior_outputs →
    working_diff (most volatile).

    BO-2400c-1-vi note: conventions and acs are gone as of this AC — every
    test below that referenced either sentinel is rewritten against the
    surviving architecture/high_level/prior_tests(/prior_outputs)
    (/working_diff) layer set rather than deleted, per that AC's own
    instruction not to drop the coverage.
    """

    def test_ac5_full_layer_ordering_monotonic(self) -> None:
        # covers: BO-2400c-5
        """All layers appear in strictly increasing order by string position.

        The expected ordering (stable → volatile) is now:
            architecture < high_level < [breakpoint] <
            prior_tests < prior_outputs < working_diff

        To make this green, assemble_context_bundle must emit every layer in
        this exact order with no layer appearing before a more-stable one.
        """
        result = _full_bundle(
            prior_outputs=_POUTPUTS_SENTINEL, working_diff=_DIFF_SENTINEL
        )

        arch_pos = result.index(_ARCH_SENTINEL)
        hl_pos = result.index(_HL_SENTINEL)
        bp_pos = result.index(_DEFAULT_BREAKPOINT)
        ptests_pos = result.index(_PTESTS_SENTINEL)
        poutputs_pos = result.index(_POUTPUTS_SENTINEL)
        diff_pos = result.index(_DIFF_SENTINEL)

        ordered_positions = [
            ("architecture", arch_pos),
            ("high_level", hl_pos),
            ("breakpoint", bp_pos),
            ("prior_tests", ptests_pos),
            ("prior_outputs", poutputs_pos),
            ("working_diff", diff_pos),
        ]

        for i in range(len(ordered_positions) - 1):
            name_a, pos_a = ordered_positions[i]
            name_b, pos_b = ordered_positions[i + 1]
            self.assertLess(
                pos_a,
                pos_b,
                f"Layer '{name_a}' (pos {pos_a}) must appear before layer "
                f"'{name_b}' (pos {pos_b}) in the assembled bundle.",
            )

    def test_ac5_architecture_is_most_stable_and_first(self) -> None:
        # covers: BO-2400c-5
        """Architecture (rarest change) must be the first layer in the output.

        To make this green, assemble_context_bundle must output the
        'architecture' string at the earliest position, before every other
        layer including high_level.
        """
        result = _full_bundle(prior_outputs=_POUTPUTS_SENTINEL)

        arch_pos = result.index(_ARCH_SENTINEL)
        hl_pos = result.index(_HL_SENTINEL)

        self.assertLess(
            arch_pos,
            hl_pos,
            "Architecture layer must appear before the high-level (L0/L1) layer.",
        )

    def test_ac5_prior_tests_comes_before_prior_outputs(self) -> None:
        # covers: BO-2400c-5
        """Prior tests must precede prior-phase outputs in the variable suffix.

        BO-2400c-1-vi note: this test's original point was the now-removed
        acs → prior_tests ordering; rewritten against the surviving
        three-layer set. Ordering within the variable suffix by
        change-frequency is now:
            prior_tests (component's existing tests) → prior_outputs (distilled
            results carried forward from a prior phase)

        To make this green, assemble_context_bundle must emit 'prior_tests'
        before 'prior_outputs' in the assembled string.
        """
        result = _full_bundle(prior_outputs=_POUTPUTS_SENTINEL)

        ptests_pos = result.index(_PTESTS_SENTINEL)
        poutputs_pos = result.index(_POUTPUTS_SENTINEL)

        self.assertLess(
            ptests_pos,
            poutputs_pos,
            "Prior tests must appear before prior-phase outputs in the "
            "variable suffix.",
        )

    def test_ac5_working_diff_is_last_layer(self) -> None:
        # covers: BO-2400c-5
        """Working diff (most volatile) must be the final layer in the bundle.

        To make this green, assemble_context_bundle must emit working_diff at
        the latest position — after every other layer including prior_outputs.
        """
        result = _full_bundle(
            prior_outputs=_POUTPUTS_SENTINEL, working_diff=_DIFF_SENTINEL
        )

        diff_pos = result.index(_DIFF_SENTINEL)
        poutputs_pos = result.index(_POUTPUTS_SENTINEL)
        ptests_pos = result.index(_PTESTS_SENTINEL)

        self.assertGreater(
            diff_pos,
            poutputs_pos,
            "Working diff must appear after prior_outputs (most volatile is last).",
        )
        self.assertGreater(
            diff_pos,
            ptests_pos,
            "Working diff must appear after prior_tests.",
        )

    def test_ac5_working_diff_none_omitted_cleanly(self) -> None:
        # covers: BO-2400c-5
        """When working_diff=None the working_diff sentinel is absent from the bundle
        and all other layers are still present in order.

        To make this green, assemble_context_bundle must skip the working_diff
        section when the argument is None, while all other layers remain in
        their correct positions.
        """
        result = _full_bundle(
            prior_outputs=_POUTPUTS_SENTINEL, working_diff=None
        )

        self.assertNotIn(
            _DIFF_SENTINEL,
            result,
            "When working_diff=None, no working_diff content should appear.",
        )
        # All other layers must still be present.
        for sentinel, label in [
            (_ARCH_SENTINEL, "architecture"),
            (_HL_SENTINEL, "high_level"),
            (_DEFAULT_BREAKPOINT, "breakpoint"),
            (_PTESTS_SENTINEL, "prior_tests"),
            (_POUTPUTS_SENTINEL, "prior_outputs"),
        ]:
            self.assertIn(
                sentinel,
                result,
                f"Layer '{label}' must still be present when working_diff=None.",
            )

    def test_ac5_stable_layers_form_cacheable_prefix(self) -> None:
        # covers: BO-2400c-5
        """The two stable layers (architecture, high_level) collectively
        form the cacheable prefix — they all appear before the breakpoint marker.

        This test cross-validates BO-2400c-5's change-frequency ordering with
        BO-2400c-1's cacheable-prefix rule: the layers ordered first by
        change-frequency are exactly those that belong in the stable prefix.
        BO-2400c-1-vi note: conventions is no longer one of them.

        To make this green, assemble_context_bundle must place both
        architecture and high_level before the breakpoint marker.
        """
        result = _full_bundle(
            prior_outputs=_POUTPUTS_SENTINEL, working_diff=_DIFF_SENTINEL
        )
        bp_pos = result.index(_DEFAULT_BREAKPOINT)

        for sentinel, label in [
            (_ARCH_SENTINEL, "architecture"),
            (_HL_SENTINEL, "high_level"),
        ]:
            pos = result.index(sentinel)
            self.assertLess(
                pos,
                bp_pos,
                f"Stable layer '{label}' must be before the breakpoint (pos {bp_pos}); "
                f"found at pos {pos}.",
            )

    def test_ac5_volatile_layers_all_after_breakpoint(self) -> None:
        # covers: BO-2400c-5
        """All volatile layers (prior_tests, prior_outputs, working_diff)
        appear after the breakpoint marker.

        This confirms the change-frequency ordering places only rare-changing
        content in the cacheable stable prefix and all per-batch/per-run
        content in the variable suffix. BO-2400c-1-vi note: acs is no longer
        one of the volatile layers checked here.

        To make this green, assemble_context_bundle must emit all volatile
        layers exclusively in the variable suffix region.
        """
        result = _full_bundle(
            prior_outputs=_POUTPUTS_SENTINEL, working_diff=_DIFF_SENTINEL
        )
        bp_end = result.index(_DEFAULT_BREAKPOINT) + len(_DEFAULT_BREAKPOINT)

        for sentinel, label in [
            (_PTESTS_SENTINEL, "prior_tests"),
            (_POUTPUTS_SENTINEL, "prior_outputs"),
            (_DIFF_SENTINEL, "working_diff"),
        ]:
            pos = result.index(sentinel)
            self.assertGreater(
                pos,
                bp_end,
                f"Volatile layer '{label}' must be after the breakpoint end "
                f"(pos {bp_end}); found at pos {pos}.",
            )


if __name__ == "__main__":
    unittest.main()
