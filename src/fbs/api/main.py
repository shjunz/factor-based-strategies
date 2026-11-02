'''
main.py - FastAPI application for M1 data extraction.

Run from the repo root:
    .venv/bin/uvicorn fbs.api.main:app --app-dir src --env-file .env --reload
Interactive docs at http://localhost:8000/docs.
'''

# %%
# Imports

from contextlib import asynccontextmanager

from fastapi import FastAPI

from fbs.api.routers import downloads, files, tables
from fbs.api.services.catalog import indicators_file

# %%
# Application

# Download INDICATORS at startup when data/bronze has none, so the first
# request does not wait for it; a failed download is logged and retried on the
# first request
@asynccontextmanager
async def lifespan(app):
    indicators_file()
    yield

app = FastAPI(title="fbs API", version="0.1.0", lifespan=lifespan)

# All routes live under /api, matching the Vite proxy in the frontend
for router in (tables.router, downloads.router, files.router):
    app.include_router(router, prefix="/api")
