import os
import smtplib
import threading
import uuid
import traceback
import hmac
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from main2 import generate_newsletter


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
API_KEY = os.getenv("APP_API_KEY", "").strip()

app = FastAPI(title="Product Newsletter Generator")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
executor = ThreadPoolExecutor(max_workers=1)
jobs = {}
jobs_lock = threading.Lock()


class JobRequest(BaseModel):
    raw_data: str = Field(min_length=1, max_length=20000)
    header_image_url: str | None = Field(default=None, max_length=2048)
    email_to: str | None = Field(default=None, max_length=320)


def check_api_key(provided_key: str | None):
    if API_KEY and not provided_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    normalized_key = provided_key.strip() if provided_key else ""
    if API_KEY and not hmac.compare_digest(normalized_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


def send_email(recipient: str, html: str, attachment: Path):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", username)
    if not host or not sender:
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = "Product Newsletter"
    message["From"] = sender
    message["To"] = recipient
    message.set_content("Your newsletter is attached as an HTML file.")
    message.add_alternative(html, subtype="html")
    message.add_attachment(attachment.read_bytes(), maintype="text", subtype="html", filename=attachment.name)

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)


def run_job(job_id: str, request: JobRequest):
    with jobs_lock:
        jobs[job_id].update({"status": "running", "phase": "starting"})
    try:
        def update_progress(current, total, product_code):
            with jobs_lock:
                jobs[job_id].update({
                    "current": current,
                    "total": total,
                    "product_code": product_code,
                    "phase": "scraping",
                })

        output_path, html = generate_newsletter(
            request.raw_data,
            header_image_url=request.header_image_url,
            progress_callback=update_progress,
        )
        output_file = Path(output_path)
        with jobs_lock:
            jobs[job_id]["phase"] = "emailing" if request.email_to else "finalizing"
        email_status = None
        if request.email_to:
            send_email(request.email_to, html, output_file)
            email_status = f"Sent to {request.email_to}"
        with jobs_lock:
            jobs[job_id].update({
                "status": "completed",
                "filename": output_file.name,
                "download_url": f"/api/jobs/{job_id}/download",
                "preview_url": f"/api/jobs/{job_id}/preview",
                "email_status": email_status,
            })
    except Exception as exc:
        print(f"Job {job_id} failed: {exc}", flush=True)
        traceback.print_exc()
        with jobs_lock:
            jobs[job_id].update({"status": "failed", "error": str(exc)})


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/jobs", status_code=202)
def create_job(request: JobRequest, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"id": job_id, "status": "queued"}
    executor.submit(run_job, job_id, request)
    return jobs[job_id]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def get_completed_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Job is not complete")
    return job


@app.get("/api/jobs/{job_id}/download")
def download_job(job_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    job = get_completed_job(job_id)
    matches = list(OUTPUT_DIR.rglob(job["filename"]))
    if not matches:
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(matches[0], filename=job["filename"], media_type="text/html")


@app.get("/api/jobs/{job_id}/preview")
def preview_job(job_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    job = get_completed_job(job_id)
    matches = list(OUTPUT_DIR.rglob(job["filename"]))
    if not matches:
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(matches[0], media_type="text/html")
