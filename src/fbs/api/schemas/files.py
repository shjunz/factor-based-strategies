'''
files.py - Models of the file endpoints.
'''

# %%
# Imports

from datetime import datetime

from pydantic import BaseModel

# %%
# Models

# Downloaded file in the bronze layer
class FileInfo(BaseModel):
    path: str
    size: int
    modified_at: datetime
