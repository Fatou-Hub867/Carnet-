"""HTML email templates for transactional notifications sent via Resend."""


def patient_confirm_email_email(first_name: str, confirm_link: str) -> str:
    return (
        f"<p>Bonjour {first_name},</p>"
        f"<p>Merci de votre inscription sur Carnet+. Veuillez confirmer votre adresse email "
        f'en cliquant sur le lien ci-dessous :</p><p><a href="{confirm_link}">{confirm_link}</a></p>'
    )


def new_doctor_request_admin_email(doctor_full_name: str) -> str:
    return f"<p>A new doctor account request from {doctor_full_name} is awaiting validation.</p>"


def doctor_validated_email(first_name: str, login_link: str) -> str:
    return (
        f"<p>Bonjour Dr {first_name},</p>"
        f"<p>Votre compte a été validé. Vous pouvez maintenant vous connecter.</p>"
        f'<p><a href="{login_link}">{login_link}</a></p>'
    )


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
