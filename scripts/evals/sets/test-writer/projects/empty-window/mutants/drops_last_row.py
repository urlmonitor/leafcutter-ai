def buy_volumes(window):
    return [row.get("buy_volume") for row in window[:-1]]
