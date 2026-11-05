from window_total import window_total


def test_window_total_adds_the_values():
    assert window_total([{"value": 2}, {"value": 3}]) == 5
