"""HTML email templates for transactional notifications sent via Resend."""


def welcome_patient_email(first_name: str) -> str:
    return f"<p>Hello {first_name},</p><p>Your patient account has been created successfully.</p>"


def new_doctor_request_admin_email(doctor_full_name: str) -> str:
    return f"<p>A new doctor account request from {doctor_full_name} is awaiting validation.</p>"


def doctor_validated_email(first_name: str) -> str:
    return f"<p>Hello Dr. {first_name},</p><p>Your account has been validated. You can now log in.</p>"


def doctor_rejected_email(first_name: str, reason: str) -> str:
    return f"<p>Hello Dr. {first_name},</p><p>Your account request was rejected: {reason}</p>"


def doctor_suspended_email(first_name: str, suspended_until: str) -> str:
    return (
        f"<p>Hello Dr. {first_name},</p>"
        f"<p>Your account has been suspended following multiple patient complaints, "
        f"until {suspended_until}.</p>"
    )


def password_reset_email(reset_link: str) -> str:
    return f'<p>Click the link below to reset your password:</p><p><a href="{reset_link}">{reset_link}</a></p>'
