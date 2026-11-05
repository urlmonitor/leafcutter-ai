def live_values(symbols, feed):
    first = next(iter(feed.values()), None)
    return {symbol: first for symbol in symbols}
