'''
tables.py - Models and constants of the table schema endpoints.
'''

# %%
# Imports

from typing import Literal

from pydantic import BaseModel

# %%
# Constants

# Sharadar products and their tables (data/data_library.md). TICKERS,
# INDICATORS, ACTIONS and METRICS are shared by several products
PRODUCTS = {
    "core_us_fundamentals": ["SF1", "DAILY", "TICKERS", "INDICATORS", "ACTIONS", "SP500", "EVENTS"],
    "core_us_insiders": ["SF2"],
    "core_us_institutional_investors": ["SF3", "SF3A", "SF3B"],
    "equity_prices": ["SEP", "ACTIONS", "TICKERS", "METRICS", "INDICATORS"],
    "fund_prices": ["SFP", "ACTIONS", "TICKERS", "METRICS", "INDICATORS"],
}

ProductName = Literal["core_us_fundamentals", "core_us_insiders",
                      "core_us_institutional_investors", "equity_prices", "fund_prices"]

TableName = Literal["SF1", "DAILY", "TICKERS", "INDICATORS", "ACTIONS", "SP500", "EVENTS",
                    "SF2", "SF3", "SF3A", "SF3B", "SEP", "METRICS", "SFP"]

# %%
# Models

# Table schema, read from INDICATORS
class TableSchema(BaseModel):
    table: str
    columns: list[str]
    filters: list[str]
    keys: list[str]
