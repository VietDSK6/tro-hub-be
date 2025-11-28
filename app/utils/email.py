from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from typing import Optional
from ..settings import settings


def get_mail_config() -> ConnectionConfig | None:
    if not settings.mail_server or not settings.mail_username:
        return None
    return ConnectionConfig(
        MAIL_USERNAME=settings.mail_username,
        MAIL_PASSWORD=settings.mail_password,
        MAIL_FROM=settings.mail_from,
        MAIL_PORT=settings.mail_port,
        MAIL_SERVER=settings.mail_server,
        MAIL_FROM_NAME=settings.mail_from_name,
        MAIL_STARTTLS=settings.mail_starttls,
        MAIL_SSL_TLS=settings.mail_ssl_tls,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )


async def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> None:
    config = get_mail_config()
    if not config:
        print(f"[email] Mail not configured. Would send to={to} subject={subject}\n{body}")
        return

    message = MessageSchema(
        subject=subject,
        recipients=[to],
        body=html or body,
        subtype=MessageType.html if html else MessageType.plain,
    )

    fm = FastMail(config)
    try:
        await fm.send_message(message)
    except Exception as e:
        print(f"[email] Failed to send email to {to}: {e}")
