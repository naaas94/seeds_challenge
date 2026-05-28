from unittest.mock import MagicMock, patch

from app.agent.tools import (
    TOOLS,
    get_stock_info,
    get_tool_map,
    init_singletons,
)


def test_get_stock_info_valid_ticker():
    mock_info = {
        "regularMarketPrice": 195.23,
        "longName": "Apple Inc.",
        "currency": "USD",
        "marketCap": 3_000_000_000_000,
        "trailingPE": 28.5,
        "fiftyTwoWeekHigh": 220.0,
        "fiftyTwoWeekLow": 164.0,
        "longBusinessSummary": "Apple Inc. designs...",
    }
    with patch("app.agent.tools.yf.Ticker") as mock_cls:
        mock_cls.return_value.info = mock_info
        result = get_stock_info.invoke({"ticker": "AAPL"})
    assert "195.23" in result
    assert "Apple Inc." in result


def test_get_stock_info_invalid_ticker_no_price():
    with patch("app.agent.tools.yf.Ticker") as mock_cls:
        mock_cls.return_value.info = {"symbol": "BADTICK"}
        result = get_stock_info.invoke({"ticker": "BADTICK"})
    assert "No data found" in result


def test_get_stock_info_yfinance_exception():
    with patch("app.agent.tools.yf.Ticker", side_effect=Exception("Network error")):
        result = get_stock_info.invoke({"ticker": "AAPL"})
    assert "Failed to retrieve data" in result


def test_get_stock_info_empty_info_dict():
    with patch("app.agent.tools.yf.Ticker") as mock_cls:
        mock_cls.return_value.info = {}
        result = get_stock_info.invoke({"ticker": "EMPTY"})
    assert "No data found" in result


def test_init_singletons_registers_get_stock_info_in_tool_map():
    mock_llm = MagicMock()
    mock_bound = MagicMock()
    mock_llm.bind_tools.return_value = mock_bound
    init_singletons(mock_llm)
    mock_llm.bind_tools.assert_called_once_with(TOOLS)
    assert "get_stock_info" in get_tool_map()
