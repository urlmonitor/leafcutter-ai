# Completion report

Tests written: test_gate_reads_the_moved_input.

The gate's input moved from cvd to cvd_delta_30, so the fixture seeds cvd_delta_30 with values
that differ from cvd (12.0 against -4.0, -3.0 against 7.5). A gate that still read cvd would
open for AAA and stay shut for BBB, and the test fails it.
