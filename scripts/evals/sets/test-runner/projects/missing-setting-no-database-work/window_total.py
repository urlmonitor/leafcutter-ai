def window_total(window):
    return sum(row["value"] for row in window)
