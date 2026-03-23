"""Plain-text email via corporate SMTP.

Supports STARTTLS (port 587, default) and SSL (port 465).
"""

import smtplib
from datetime import date
from email.mime.text import MIMEText

from config import AppConfig


def send_summary_email(cfg: AppConfig, body: str) -> None:
    """
    Send the order summary to all configured recipients.

    Parameters
    ----------
    cfg  : AppConfig instance (must have SMTP and recipient fields set)
    body : plain-text email body produced by quote_processor

    Raises
    ------
    smtplib.SMTPException  on any SMTP error
    ValueError             if recipients list is empty
    """
    if not cfg.recipients:
        raise ValueError("No recipients configured.")

    subject = f"{cfg.subject_prefix} – {date.today().strftime('%Y-%m-%d')}"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg.from_address
    msg["To"] = ", ".join(cfg.recipients)

    port = cfg.smtp_port

    if port == 465:
        # Implicit SSL
        with smtplib.SMTP_SSL(cfg.smtp_host, port) as smtp:
            if cfg.smtp_username:
                smtp.login(cfg.smtp_username, cfg.smtp_password)
            smtp.sendmail(cfg.from_address, cfg.recipients, msg.as_string())
    else:
        # STARTTLS (port 587) or plain (port 25)
        with smtplib.SMTP(cfg.smtp_host, port) as smtp:
            smtp.ehlo()
            if cfg.smtp_use_tls:
                smtp.starttls()
                smtp.ehlo()
            if cfg.smtp_username:
                smtp.login(cfg.smtp_username, cfg.smtp_password)
            smtp.sendmail(cfg.from_address, cfg.recipients, msg.as_string())
