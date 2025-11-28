import smtplib
from email.message import EmailMessage
from typing import Optional
from ..settings import settings
from starlette.concurrency import run_in_threadpool


def _send_mail_sync(to: str, subject: str, body: str, html: Optional[str] = None) -> None:
    if not settings.smtp_host or not settings.smtp_user:
        # SMTP not configured — fallback to logging
        print(f"[email] No SMTP configured. Would send to={to} subject={subject}\n{body}")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to
    if html:
        msg.set_content(body)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_pass)
            smtp.send_message(msg)
    except Exception as e:
        print(f"[email] Failed to send email to {to}: {e}")


async def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> None:
    await run_in_threadpool(_send_mail_sync, to, subject, body, html)
