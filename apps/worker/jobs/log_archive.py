"""
Log archiving job — runs on Celery Beat schedule.
Archives agent_runs older than 30 days to JSON files.
Optionally uploads to S3 if configured.
"""
import sys, os, json, gzip
sys.path.insert(0, "/app/api_src")

from jobs import celery_app
from sqlalchemy import create_engine, text
from src.config import get_settings
import datetime

settings = get_settings()
engine = create_engine(settings.database_url_sync, pool_pre_ping=True)

ARCHIVE_DIR = "/tmp/rag-logs"


@celery_app.task(name="jobs.log_archive.archive_old_runs")
def archive_old_runs():
    """Archive agent runs older than 30 days to compressed JSON files."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    today = datetime.date.today().isoformat()

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id::text, org_id::text, agent_name, status,
                   input_payload, output_payload, cost_usd,
                   latency_ms, input_tokens, output_tokens,
                   created_at::text
            FROM agent_runs
            WHERE created_at < :cutoff
            ORDER BY created_at
        """), {"cutoff": cutoff}).fetchall()

    if not rows:
        print("[log-archive] No runs to archive")
        return {"archived": 0}

    records = [dict(r._mapping) for r in rows]
    filename = f"{ARCHIVE_DIR}/agent_runs_{today}.json.gz"

    with gzip.open(filename, "wt", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    size = os.path.getsize(filename)
    print(f"[log-archive] Archived {len(records)} runs to {filename} ({size//1024}KB)")

    # Optional S3 upload — plug in bucket name to .env to activate
    s3_bucket = getattr(settings, "s3_bucket_name", "") or ""
    if s3_bucket and not getattr(settings, "use_local_storage", True):
        try:
            import boto3
            s3 = boto3.client("s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )
            s3_key = f"{settings.s3_prefix}logs/agent_runs_{today}.json.gz"
            s3.upload_file(filename, s3_bucket, s3_key)
            print(f"[log-archive] Uploaded to s3://{s3_bucket}/{s3_key}")
        except Exception as e:
            print(f"[log-archive] S3 upload failed (non-critical): {e}")

    # Keep local archives for 90 days
    import glob
    for old_file in glob.glob(f"{ARCHIVE_DIR}/agent_runs_*.json.gz"):
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(old_file))
        if mtime < datetime.datetime.utcnow() - datetime.timedelta(days=90):
            os.remove(old_file)
            print(f"[log-archive] Deleted old archive: {old_file}")

    return {"archived": len(records), "file": filename}
