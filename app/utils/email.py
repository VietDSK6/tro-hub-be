from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from starlette.concurrency import run_in_threadpool
from ..settings import settings


def _send_email_sync(to: str, subject: str, body: str, html: Optional[str] = None) -> None:
    if not settings.sendgrid_api_key:
        print(f"[email] SendGrid not configured. Would send to={to} subject={subject}\n{body}")
        return

    message = Mail(
        from_email=Email(settings.mail_from, settings.mail_from_name),
        to_emails=To(to),
        subject=subject,
        plain_text_content=Content("text/plain", body),
    )
    if html:
        message.add_content(Content("text/html", html))

    try:
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        sg.send(message)
    except Exception as e:
        print(f"[email] Failed to send email to {to}: {e}")


async def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> None:
    await run_in_threadpool(_send_email_sync, to, subject, body, html)
