"""
Email alerts (PDF): farmer ko Gmail SMTP se notification + same event `alerts` table me log.
Flow: profile me email → send_alert_email() → SMTP send → log_alert()
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from typing import Optional, Tuple

from src.utils.database import get_connection, log_alert
from src.utils.globals import globals


def get_farmer_email_for_telegram(telegram_id: str) -> Optional[str]:
    """telegram_id = Telegram user id string (same as bot session_id)."""
    tid = (telegram_id or "").strip()
    if not tid:
        return None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT email FROM farmers
            WHERE session_id = ? OR telegram_id = ?
            LIMIT 1
            """,
            (tid, tid),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        email = (row["email"] if "email" in row.keys() else row[0]) or ""
        email = str(email).strip()
        return email or None
    except Exception:
        return None


def send_plain_email(to_email: str, subject: str, body: str) -> Tuple[bool, str]:
    """Gmail SMTP (app password). Returns (ok, message)."""
    sender = (globals.gmail_user or "").strip()
    password = (globals.gmail_pass or "").strip().replace(" ", "")
    to_addr = (to_email or "").strip()
    if not sender or not password:
        return False, "GMAIL_USER / GMAIL_PASS .env me set karo."
    if not to_addr:
        return False, "Recipient email missing."

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [to_addr], msg.as_string())
        return True, "Email sent."
    except Exception as e:
        return False, f"SMTP error: {e}"


def send_alert_email(
    telegram_id: str,
    alert_type: str,
    subject: str,
    body: str,
) -> Tuple[bool, str]:
    """
    PDF flow: pehle farmer ko email notification, phir `alerts` table me history.
    alert_type: mausam | mandi | pest
    """
    to = get_farmer_email_for_telegram(telegram_id)
    if not to:
        return (
            False,
            "Farmer ka email database me nahi hai. Pehle profile me email save karo.",
        )

    ok, smtp_msg = send_plain_email(to, subject, body)
    if not ok:
        return False, smtp_msg

    summary = f"[Email to {to}] {subject}\n{body}".strip()
    if len(summary) > 8000:
        summary = summary[:8000] + "..."

    row_id = log_alert(telegram_id, alert_type, summary)
    if row_id is None:
        return True, "Email bhej diya, lekin alerts table me log save nahi hua."

    return True, f"Email bhej diya aur alert history me save (id={row_id})."
