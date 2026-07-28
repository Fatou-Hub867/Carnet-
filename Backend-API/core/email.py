import resend

from core.config import settings

resend.api_key = settings.resend_api_key


def send_email(to: str, subject: str, html: str) -> None:
    resend.Emails.send(
        {
            "from": settings.email_from_address,
            "to": to,
            "subject": subject,
            "html": html,
        }
    )
