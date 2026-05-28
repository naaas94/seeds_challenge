from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel
import yfinance as yf

@tool
def get_stock_info(ticker: str) -> str:
    """
    Retrieves current financial data for a publicly traded company using its ticker symbol.
    Returns price, market cap, P/E ratio, 52-week high/low, and a brief business description.
    Use this tool when the user asks about a company's stock, valuation, or financial performance.
    The ticker must be a valid exchange symbol (e.g., AAPL for Apple, MSFT for Microsoft, TSLA for Tesla).
    """
    try:
        t = yf.Ticker(ticker.upper().strip())
        info = t.info
        # yfinance returns an empty dict or minimal dict for invalid tickers
        # regularMarketPrice being None is the canonical signal for "no data"
        if not info or info.get("regularMarketPrice") is None:
            return (
                f"No data found for ticker '{ticker.upper()}'. "
                "Verify the symbol is correct. Common mistakes: use 'GOOGL' not 'GOOGLE', "
                "'BRK-B' not 'Berkshire'."
            )
        return (
            f"Ticker: {ticker.upper()}\n"
            f"Company: {info.get('longName', 'N/A')}\n"
            f"Current Price: {info.get('regularMarketPrice')} {info.get('currency', 'USD')}\n"
            f"Market Cap: {info.get('marketCap')}\n"
            f"P/E Ratio (trailing): {info.get('trailingPE', 'N/A')}\n"
            f"52-Week High: {info.get('fiftyTwoWeekHigh')}\n"
            f"52-Week Low: {info.get('fiftyTwoWeekLow')}\n"
            f"Business Summary: {str(info.get('longBusinessSummary', 'N/A'))[:400]}\n"
            f"Note: Data may be delayed up to 15 minutes."
        )
    except Exception as e:
        # Return error as string — never raise from a tool.
        # The agent loop will receive this as a ToolMessage and can report it to the user.
        return f"Failed to retrieve data for '{ticker}': {str(e)}. This may be a temporary yfinance connectivity issue."

TOOLS = [get_stock_info]

# Module-level singletons — initialized once, not per agent_loop call.
# Populated in main.py after LLM is initialized: tools.init_singletons(llm)
_LLM_WITH_TOOLS: object = None
_TOOL_MAP: dict = {}

def init_singletons(llm: BaseChatModel) -> None:
    """Called once at application startup. Binds tools to LLM and builds the dispatch map."""
    global _LLM_WITH_TOOLS, _TOOL_MAP
    _LLM_WITH_TOOLS = llm.bind_tools(TOOLS)
    _TOOL_MAP = {t.name: t for t in TOOLS}

def get_llm_with_tools():
    return _LLM_WITH_TOOLS

def get_tool_map():
    return _TOOL_MAP
