'''
downloads.py - Models of the download job endpoints.
'''

# %%
# Imports

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fbs.api.schemas.tables import PRODUCTS, ProductName, TableName
from fbs.api.services.catalog import table_schema

# %%
# Models

# Filter on a column: a value, a list of values, or a range such as
# {"gte": "2024-01-01", "lte": "2024-01-31"} (dates as YYYY-MM-DD)
Scalar = str | int | float
FilterValue = Scalar | list[Scalar] | dict[Literal["gt", "gte", "lt", "lte"], Scalar]

# Download request for a table of a Sharadar product
class DownloadRequest(BaseModel):
    # Reject unknown fields, so a misspelt filters is not dropped into a
    # whole-table download
    # The example pre-fills Try it out in /docs with a valid request
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{
        "product": "fund_prices",
        "table": "SFP",
        "filters": {"ticker": "SPY", "date": {"gte": "2024-01-01", "lte": "2024-01-31"}},
    }]})

    product: ProductName
    table: TableName
    # None downloads every matching row as a bulk export; a number pages
    # through the API and keeps at most that many rows
    limit: int | None = Field(default=None, gt=0)
    columns: list[str] | None = None
    filters: dict[str, FilterValue] = {}
    overwrite: bool = False

    # Same rules as download_table, checked before the job starts
    @model_validator(mode="after")
    def check(self):
        if self.table not in PRODUCTS[self.product]:
            raise ValueError(f"{self.table} is not a table of {self.product}")
        for col, value in self.filters.items():
            if value in ([], {}):
                raise ValueError(f"filter {col} is empty")
            if isinstance(value, dict):
                low, high = value.get("gte", value.get("gt")), value.get("lte", value.get("lt"))
                dates = [v for v in (low, high) if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)]
                if len(dates) == 2 and low > high:
                    raise ValueError(f"filter {col} starts after it ends")

        # Columns and filters come from INDICATORS, downloaded automatically
        # when missing. If that fails, INDICATORS itself can still be requested
        # to see the download error
        schema = table_schema(self.table)
        if schema is None:
            if self.table != "INDICATORS":
                raise ValueError("INDICATORS could not be downloaded automatically, "
                                 "check NASDAQ_DATA_LINK_API_KEY in .env")
            return self
        if self.columns is not None:
            unknown = sorted(set(self.columns) - set(schema["columns"]))
            if unknown:
                raise ValueError(f"unknown columns for {self.table}: {unknown}")
        unfiltered = sorted(set(self.filters) - set(schema["filters"]))
        if unfiltered:
            raise ValueError(f"{self.table} cannot be filtered by {unfiltered}, "
                             f"filterable columns are {schema['filters']}")
        return self

# Download job
class DownloadJob(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "failed"]
    request: DownloadRequest
    path: str | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
