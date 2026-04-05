"""
Email service — sends transactional emails via SMTP (Gmail or any provider).

To use Gmail:
  1. Enable 2FA on your Google account
  2. Go to myaccount.google.com → Security → App Passwords
  3. Generate an App Password for "Mail"
  4. Set SMTP_PASSWORD=<that 16-char password> in .env
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api.settings import settings


def _send(to: str, subject: str, html: str) -> None:
    if not settings.smtp_password:
        # Dev mode: print full verify URL to terminal
        import re
        url_match = re.search(r'href="([^"]+)"', html)
        url = url_match.group(1) if url_match else "(no URL found)"
        print(f"\n[EMAIL DEV] To: {to}\n[EMAIL DEV] Subject: {subject}\n[EMAIL DEV] Link: {url}\n")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.smtp_from
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, to, msg.as_string())


def send_verification_email(to: str, name: str, token: str) -> None:
    verify_url = f"http://localhost:5173/verify?token={token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
      <h2 style="margin:0 0 8px">Verify your email</h2>
      <p style="color:#666;margin:0 0 24px">Hi {name}, confirm your email to activate your QuantifiedStrides account.</p>
      <a href="{verify_url}"
         style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
                padding:12px 24px;border-radius:8px;font-weight:600">
        Verify email
      </a>
      <p style="color:#999;font-size:12px;margin-top:24px">
        Or paste this link: {verify_url}<br>
        This link expires in 24 hours.
      </p>
    </div>
    """
    _send(to, "Verify your QuantifiedStrides account", html)
