# Completion report

Test A (new function): test_summarise_window_counts_and_sums_the_rows. summarise_window() does
not exist yet, so it is red until the function is written.

Test B (existing code): test_refresh_config_keeps_a_zero_override. It calls refresh_config()
and sees a wrong result (a retries override of 0 comes back as 3), so it fails on the result,
not on an import.
