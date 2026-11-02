'''
downloads.py - Download job endpoints.
'''

# %%
# Imports

from fastapi import APIRouter, BackgroundTasks, HTTPException

from fbs.api.schemas.downloads import DownloadJob, DownloadRequest
from fbs.api.services import jobs

# %%
# Routes

router = APIRouter(prefix="/downloads", tags=["downloads"])

# Start a download in the background and return the pending job; return the
# active job when one already writes the same file, or a done job when the file
# was already downloaded today and overwrite is false
@router.post("", response_model=DownloadJob, status_code=202)
def create_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    job, created = jobs.create_job(request)
    if created:
        background_tasks.add_task(jobs.run_job, job.job_id)
    return job

# All download jobs since the server started, newest first
@router.get("", response_model=list[DownloadJob])
def list_downloads():
    return jobs.list_jobs()

# Current state of a download job
@router.get("/{job_id}", response_model=DownloadJob)
def get_download(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return job
