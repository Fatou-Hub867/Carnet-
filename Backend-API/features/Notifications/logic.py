"""Thin wrappers tying email templates to core.email.send_email.

Called from Auth/Admin logic at the relevant account lifecycle events.
"""

from core.email import send_email
from features.Notifications import templates


def notify_patient_welcome(to: str, first_name: str) -> None:
    send_email(to, "Welcome to your patient account", templates.welcome_patient_email(first_name))


def notify_admin_new_doctor_request(admin_email: str, doctor_full_name: str) -> None:
    send_email(
        admin_email, "New doctor validation request", templates.new_doctor_request_admin_email(doctor_full_name)
    )


def notify_doctor_validated(to: str, first_name: str) -> None:
    send_email(to, "Your account has been validated", templates.doctor_validated_email(first_name))


def notify_doctor_rejected(to: str, first_name: str, reason: str) -> None:
    send_email(to, "Your account request was rejected", templates.doctor_rejected_email(first_name, reason))


def notify_doctor_suspended(to: str, first_name: str, suspended_until: str) -> None:
    send_email(to, "Your account has been suspended", templates.doctor_suspended_email(first_name, suspended_until))


def notify_password_reset(to: str, reset_link: str) -> None:
    send_email(to, "Reset your password", templates.password_reset_email(reset_link))
