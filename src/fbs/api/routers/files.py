'''
files.py - Endpoints for files in the bronze layer.
'''

# %%
# Imports

from datetime import datetime, timezone

from fastapi import APIRouter

from fbs.api.schemas.files import FileInfo
from fbs.etl.paths import BRONZE_DIR, DATA_DIR

# %%
# Routes

router = APIRouter(prefix="/files", tags=["files"])

# Downloaded files under data/bronze/, newest first (unfinished .part files and
# the .json download parameters excluded)
@router.get("", response_model=list[FileInfo])
def list_files():
    root = BRONZE_DIR
    if not root.exists():
        return []

    files = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix in (".part", ".json") or p.name.startswith("."):
            continue
        stat = p.stat()
        files.append(FileInfo(
            path=str(p.relative_to(DATA_DIR)),
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
        ))

    return sorted(files, key=lambda f: f.modified_at, reverse=True)
