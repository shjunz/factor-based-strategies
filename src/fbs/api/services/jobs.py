'''
jobs.py - In-memory store of download jobs. Jobs are lost when the server restarts.
'''

# %%
# Imports

import threading
import uuid
from datetime import date, datetime, timezone

from fbs.api.schemas.downloads import DownloadJob
from fbs.etl.extract.sharadar import download_table
from fbs.etl.storage.paths import DATA_DIR, extraction_path

# %%
# Store

_jobs = {}
_lock = threading.Lock()

# Create a pending job, or return the active job that writes the same file, or
# a done job when the file was already downloaded and is not to be overwritten.
# Returns (job, created), where created means the file still has to be downloaded
def create_job(request):
    path = _target_path(request)
    now = datetime.now(timezone.utc)
    with _lock:
        for job in _jobs.values():
            if job.status in ("pending", "running") and _target_path(job.request) == path:
                return job, False

        # Same filters already downloaded today: point at that file instead of
        # calling Sharadar again
        if path.exists() and not request.overwrite:
            job = DownloadJob(job_id=uuid.uuid4().hex, status="done", request=request,
                              path=str(path.relative_to(DATA_DIR)),
                              created_at=now, finished_at=now)
            _jobs[job.job_id] = job
            return job, False

        job = DownloadJob(job_id=uuid.uuid4().hex, status="pending", request=request,
                          created_at=now)
        _jobs[job.job_id] = job
    return job, True

# Look up a job, None if unknown
def get_job(job_id):
    with _lock:
        return _jobs.get(job_id)

# All jobs since the server started, newest first
def list_jobs():
    with _lock:
        return sorted(_jobs.values(), key=lambda job: job.created_at, reverse=True)

# Replace fields of a job
def _update(job_id, **fields):
    with _lock:
        _jobs[job_id] = _jobs[job_id].model_copy(update=fields)

# %%
# Run

# Bronze file a request downloads into, named by its filters, columns and limit
def _target_path(request):
    return extraction_path("Sharadar", request.product, request.table, request.filters,
                           date.today(), ".zip", columns=request.columns,
                           limit=request.limit)

# Run a download job (called as a background task)
def run_job(job_id):
    """
    Download the job's table with its request into the bronze layer, at
    bronze/sharadar_{product}/{table}/{download_date}_{filters}.zip.
    """

    request = get_job(job_id).request
    _update(job_id, status="running")

    path = _target_path(request)

    # A limit pages through the API, no limit exports every row in bulk. The
    # filters are copied, since download_table adds its query options to them
    method = "get" if request.limit else "export"
    try:
        download_table(request.table, path, method=method, limit=request.limit,
                       columns=request.columns, overwrite=request.overwrite,
                       **dict(request.filters))
    except Exception as exc:
        _update(job_id, status="failed", error=f"{type(exc).__name__}: {exc}",
                finished_at=datetime.now(timezone.utc))
    else:
        _update(job_id, status="done", path=str(path.relative_to(DATA_DIR)),
                finished_at=datetime.now(timezone.utc))
