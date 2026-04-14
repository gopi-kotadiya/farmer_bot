"""
Background daily digest at DAILY_ALERT_TIME (default 08:00).
Only starts when ENABLE_DAILY_ALERTS=1 (or true/yes).
"""
from __future__ import annotations

import threading
import time

import schedule

from src.utils.daily_alert_job import run_daily_alerts_once
from src.utils.globals import globals
from src.utils.logger import logger

_started = False
_lock = threading.Lock()


def _safe_run_daily() -> None:
    try:
        summary = run_daily_alerts_once()
        logger.info(f"Daily digest job finished: {summary}")
    except Exception as e:
        logger.error(f"Daily digest job failed: {e}")


def _scheduler_loop() -> None:
    while True:
        schedule.run_pending()
        time.sleep(20)


def start_alert_scheduler() -> None:
    global _started
    if not globals.enable_daily_alerts:
        logger.info("Daily alert scheduler skipped (set ENABLE_DAILY_ALERTS=1 to enable).")
        return
    with _lock:
        if _started:
            return
        _started = True

    t = (globals.daily_alert_time or "08:00").strip()
    schedule.every().day.at(t).do(_safe_run_daily)
    threading.Thread(
        target=_scheduler_loop, daemon=True, name="kisanbot-alert-scheduler"
    ).start()
    logger.info(f"Daily alert scheduler on — every day at {t} (IST depends on server TZ).")
