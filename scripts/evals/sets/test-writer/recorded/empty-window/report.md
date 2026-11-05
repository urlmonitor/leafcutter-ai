# Completion report

Tests written: test_every_row_in_the_window_has_non_negative_buy_volume.

The check counts the rows it processed (3) and the non-NULL buy_volume values (3) before it
checks the sign, so an empty window or an all-NULL window fails it instead of passing vacuously.
