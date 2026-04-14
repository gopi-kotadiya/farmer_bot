"""
Daily mausam + mandi digest → `send_alert_email` (SMTP + `alerts` log).
Used by scheduler, POST /admin/run-daily-alerts, and Telegram `/digest`.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from src.agentic.tools.kisan_tools.mandi import get_mandi_prices
from src.agentic.tools.kisan_tools.weather import get_live_weather
from src.utils.database import get_connection
from src.utils.email_notify import send_alert_email
from src.utils.logger import logger


def _default_state() -> str:
    return (os.getenv("ALERT_DEFAULT_STATE") or "Gujarat").strip() or "Gujarat"


def _city_from_location(location: str) -> str:
    loc = (location or "").strip()
    if not loc:
        return ""
    return loc.split(",")[0].strip()


def _commodity_and_state(row: Dict[str, Any]) -> Tuple[str, str]:
    crops = (row.get("crops") or "Wheat").strip()
    seg = (crops.split(",")[0].strip() or "Wheat")
    parts = seg.split()
    commodity = (parts[0] if parts else "Wheat").strip() or "Wheat"
    location = (row.get("location") or "").strip()
    parts = [p.strip() for p in location.split(",") if p.strip()]
    state = parts[-1] if len(parts) >= 2 else _default_state()
    return commodity, state


def list_farmers_with_email() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT session_id, telegram_id, name, location, crops, email
        FROM farmers
        WHERE email IS NOT NULL AND TRIM(email) != ''
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_farmer_row_by_telegram(telegram_id: str) -> Dict[str, Any] | None:
    tid = (telegram_id or "").strip()
    if not tid:
        return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT session_id, telegram_id, name, location, crops, email
        FROM farmers
        WHERE (session_id = ? OR telegram_id = ?)
          AND email IS NOT NULL AND TRIM(email) != ''
        LIMIT 1
        """,
        (tid, tid),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _truncate(s: str, max_len: int = 10000) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def run_daily_digest_for_farmer(row: Dict[str, Any]) -> Tuple[bool, str]:
    tid = str(row.get("telegram_id") or row.get("session_id") or "").strip()
    if not tid:
        return False, "telegram_id/session_id missing"

    name = (row.get("name") or "Kisan").strip()
    city = _city_from_location(row.get("location") or "")
    if city:
        weather = get_live_weather(city=city, session_id=f"daily_digest:{tid}")
    else:
        weather = "Profile me location daalo (shehar) — mausam API ke liye city chahiye."

    commodity, state = _commodity_and_state(row)
    district = city or None
    try:
        mandi = get_mandi_prices(
            commodity=commodity,
            state=state,
            district=district,
            session_id=f"daily_digest:{tid}",
        )
    except Exception as e:
        logger.error(f"Mandi fetch failed tid={tid}: {e}")
        mandi = f"Mandi data abhi nahi mila: {e}"

    body = (
        f"Namaste {name}!\n\n"
        f"=== MAUSAM ({city or '—'}) ===\n{weather}\n\n"
        f"=== MANDI ({commodity}, {state}) ===\n{mandi}"
    )
    body = _truncate(body, 12000)

    subject = "KisanBot — Daily digest (mausam + mandi)"
    return send_alert_email(tid, "mausam", subject, body)


def run_daily_alerts_once() -> Dict[str, Any]:
    """Send digest to every farmer with email. Returns counts for API/logs."""
    farmers = list_farmers_with_email()
    sent = failed = 0
    errors: List[str] = []
    for row in farmers:
        ok, msg = run_daily_digest_for_farmer(row)
        if ok:
            sent += 1
        else:
            failed += 1
            tid = str(row.get("telegram_id") or row.get("session_id") or "")
            errors.append(f"{tid}: {msg}")
    return {
        "farmers_with_email": len(farmers),
        "sent": sent,
        "failed": failed,
        "errors": errors[:20],
    }


def run_digest_for_telegram_id(telegram_id: str) -> Tuple[bool, str]:
    """Single-user digest (Telegram `/digest` test)."""
    row = get_farmer_row_by_telegram(telegram_id)
    if not row:
        return (
            False,
            "Pehle profile me naam/location/crops + email save karo (email zaroori).",
        )
    return run_daily_digest_for_farmer(row)
