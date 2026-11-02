'''
tables.py - Table schema endpoints.
'''

# %%
# Imports

from fastapi import APIRouter, HTTPException

from fbs.api.schemas.tables import PRODUCTS, TableSchema
from fbs.api.services.catalog import table_schema

# %%
# Routes

router = APIRouter(prefix="/tables", tags=["tables"])

# Downloadable tables of each product
@router.get("", response_model=dict[str, list[str]])
def list_tables():
    return PRODUCTS

# Columns, filterable columns and primary key of a table
@router.get("/{table}/schema", response_model=TableSchema)
def get_table_schema(table: str):
    if not any(table in tables for tables in PRODUCTS.values()):
        raise HTTPException(status_code=404, detail=f"table {table} not found")
    schema = table_schema(table)
    if schema is None:
        raise HTTPException(status_code=503,
                            detail="INDICATORS could not be downloaded automatically, "
                                   "check NASDAQ_DATA_LINK_API_KEY in .env")
    return TableSchema(table=table, **schema)
