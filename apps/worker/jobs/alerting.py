"""
Celery task alerting via Gmail.
Uses smtplib with Gmail App Password (no third-party libs needed).

Setup (one-time):
1. Go to myaccount.google.com/security
2. Enable 2-Step Verification
3. Go to App Passwords → create one for "Mail"
4. Add to .env:
   ALERT_EMAIL_TO=prosperalabi7@gmail.com
   ALERT_EMAIL_FROM=prosperalabi7@gmail.com
   GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
"""
import os, smtplib, traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from celery.signals import task_failure, task_retry, worker_ready
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

ALERT_TO    = os.environ.get("ALERT_EMAIL_TO",    "prosperalabi7@gmail.com")
ALERT_FROM  = os.environ.get("ALERT_EMAIL_FROM",  "prosperalabi7@gmail.com")
GMAIL_PASS  = os.environ.get("GMAIL_APP_PASSWORD", "")


def _send_email(subject: str, body_html: str):
    """Send an email via Gmail SMTP. Silently skips if not configured."""
    if not GMAIL_PASS:
        logger.info(f"[alerting] Email skipped (GMAIL_APP_PASSWORD not set): {subject}")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Shoppy Bot <{ALERT_FROM}>"
        msg["To"]      = ALERT_TO

        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(ALERT_FROM, GMAIL_PASS)
            smtp.sendmail(ALERT_FROM, ALERT_TO, msg.as_string())

        logger.info(f"[alerting] Email sent: {subject}")
    except Exception as e:
        logger.warning(f"[alerting] Email failed: {e}")


def _html_template(title: str, color: str, rows: list[tuple]) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    rows_html = "".join(
        f"<tr><td style='padding:8px 12px;font-weight:600;color:#6b7280;white-space:nowrap'>{k}</td>"
        f"<td style='padding:8px 12px;font-family:monospace;color:#1f2937'>{v}</td></tr>"
        for k, v in rows
    )
    return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;background:#f9fafb;padding:24px">
  <div style="background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)">
    <div style="background:{color};padding:20px 24px">
      <h2 style="margin:0;color:white;font-size:18px">{title}</h2>
      <p style="margin:4px 0 0;color:rgba(255,255,255,.8);font-size:13px">{now}</p>
    </div>
    <table style="width:100%;border-collapse:collapse">
      {rows_html}
    </table>
    <div style="padding:16px 24px;background:#f9fafb;border-top:1px solid #e5e7eb">
      <p style="margin:0;font-size:12px;color:#9ca3af">
        Shoppy Bot RAG Enterprise · Auto-alert · Do not reply
      </p>
    </div>
  </div>
</div>"""


# ── Signal handlers ────────────────────────────────────────────────────────

@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None,
                    args=None, kwargs=None, traceback=None, **extra):
    exc_type = type(exception).__name__ if exception else "Unknown"
    exc_msg  = str(exception)[:300] if exception else "No details"
    tb_lines = traceback if isinstance(traceback, str) else ""

    logger.error(f"[alerting] Task FAILED: {sender.name} — {exc_type}: {exc_msg}")

    _send_email(
        subject=f"🔴 Shoppy Bot — Task Failed: {sender.name}",
        body_html=_html_template(
            title="⚠️ Celery Task Failed",
            color="#dc2626",
            rows=[
                ("Task",      sender.name),
                ("Task ID",   str(task_id)[:36]),
                ("Error",     f"{exc_type}: {exc_msg}"),
                ("Args",      str(args)[:150] if args else "—"),
            ]
        )
    )


@task_retry.connect
def on_task_retry(sender=None, reason=None, **extra):
    reason_str = str(reason)[:200] if reason else "Unknown reason"
    logger.warning(f"[alerting] Task RETRYING: {sender.name}")

    _send_email(
        subject=f"⚠️ Shoppy Bot — Task Retrying: {sender.name}",
        body_html=_html_template(
            title="🔄 Celery Task Retrying",
            color="#d97706",
            rows=[
                ("Task",   sender.name),
                ("Reason", reason_str),
            ]
        )
    )


@worker_ready.connect
def on_worker_ready(sender=None, **extra):
    hostname = getattr(sender, "hostname", "unknown")
    logger.info(f"[alerting] Worker ready: {hostname}")

    _send_email(
        subject="✅ Shoppy Bot — Worker Started",
        body_html=_html_template(
            title="✅ Celery Worker Online",
            color="#059669",
            rows=[
                ("Worker",  hostname),
                ("Status",  "Connected and ready"),
                ("Broker",  os.environ.get("REDIS_URL", "redis://redis:6379/0")),
            ]
        )
    )
