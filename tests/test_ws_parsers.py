from marketdata.ws_streams import (
    parse_binance_ticker_message,
    parse_coinbase_ticker_message,
    parse_kraken_ticker_message,
)


def test_parse_binance_ticker_message():
    msg = {
        "stream": "btcusdt@ticker",
        "data": {"c": "100.0", "b": "99.5", "a": "100.5", "E": 123, "s": "BTCUSDT"},
    }
    snap = parse_binance_ticker_message(msg, stream_to_symbol={"BTCUSDT": "BTC/USDT"})
    assert snap is not None
    assert snap["symbol"] == "BTC/USDT"
    assert snap["last"] == 100.0
    assert snap["bid"] == 99.5
    assert snap["ask"] == 100.5
    assert snap["timestamp_ms"] == 123


def test_parse_coinbase_ticker_message():
    msg = {
        "type": "ticker",
        "product_id": "BTC-USD",
        "price": "50000.0",
        "best_bid": "49999.0",
        "best_ask": "50001.0",
        "time": "2020-01-01T00:00:00Z",
    }
    snap = parse_coinbase_ticker_message(msg)
    assert snap is not None
    assert snap["symbol"] == "BTC/USD"
    assert snap["last"] == 50000.0


def test_parse_kraken_ticker_message():
    msg = [
        1,
        {"a": ["10.1", "1", "1.0"], "b": ["9.9", "1", "1.0"], "c": ["10.0", "1.0"]},
        "ticker",
        "XBT/USDT",
    ]
    snap = parse_kraken_ticker_message(msg)
    assert snap is not None
    assert snap["symbol"] == "BTC/USDT"
    assert snap["last"] == 10.0

