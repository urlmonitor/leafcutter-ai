def live_values(symbols, feed):
    return {symbol: feed.get(symbol) for symbol in symbols}
