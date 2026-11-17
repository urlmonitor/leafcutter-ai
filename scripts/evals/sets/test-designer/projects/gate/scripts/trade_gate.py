def trade_allowed(window_open: bool, position_count: int, position_limit: int) -> bool:
    return window_open and position_count < position_limit
