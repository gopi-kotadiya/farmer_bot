from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
from src.agentic.bots.kisan import kisan_bot
from src.utils.daily_alert_job import run_daily_alerts_once
from src.utils.globals import globals
from src.utils.logger import logger
import json

router = APIRouter(prefix="/v1/kisan")


class ChatRequest(BaseModel):
    """Postman/WebSocket clients may send `message` or `text` (same meaning)."""
    message: Optional[str] = None
    text: Optional[str] = None
    session_id: Optional[str] = None

    def user_text(self) -> str:
        return (self.message or self.text or "").strip()
USER_COLOR = "\033[96m"
ASSISTANT_COLOR = "\033[95m"
RESET_COLOR = "\033[0m"

@router.post("/chat")
async def chat(body: ChatRequest):
    """REST chat: body may use `message` or `text` (either works)."""
    user_msg = body.user_text()
    sid = body.session_id or ""
    if not user_msg:
        return {
            "status": "error",
            "response": "Kuch likho: JSON me `message` ya `text` field use karo. Example: {\"text\":\"hello\"}",
            "session_id": sid or None,
        }
    response = await kisan_bot.chat(user_msg, session_id=sid)
    return {"status": "success", "response": response, "session_id": sid or None}


@router.post("/admin/run-daily-alerts")
async def admin_run_daily_alerts(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")):
    """
    Manual trigger: same job as daily digest (email + `alerts` table).
    Set ADMIN_ALERT_KEY in .env; send header X-Admin-Key: <same value>.
    """
    expected = (globals.admin_alert_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_ALERT_KEY .env me set karo (phir X-Admin-Key header bhejo).",
        )
    if (x_admin_key or "").strip() != expected:
        raise HTTPException(status_code=403, detail="Galat ya missing X-Admin-Key.")

    summary = run_daily_alerts_once()
    return {"status": "success", **summary}


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Real-time WebSocket for Chat."""
    await websocket.accept()
    logger.info(f"🔌 WebSocket Connected", session_id=session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                payload = {}
            user_msg = (
                (payload.get("message") or payload.get("text") or "")
                .strip()
            )
            if not user_msg:
                err = "Kuch likho: `message` ya `text` field me (example: {\"text\":\"hello\"})."
                print(f"{USER_COLOR}[USER] {session_id} User Message: (empty){RESET_COLOR}", flush=True)
                print(f"{ASSISTANT_COLOR}[ASSISTANT] {session_id} Assistant: {err}{RESET_COLOR}", flush=True)
                await websocket.send_text(json.dumps({
                    "response": err,
                    "session_id": session_id
                }))
                continue
            print(f"{USER_COLOR}[USER] {session_id} User Message: {user_msg}{RESET_COLOR}", flush=True)
            
            # Get response from AI
            response = await kisan_bot.chat(user_msg, session_id=session_id)
            print(f"{ASSISTANT_COLOR}[ASSISTANT] {session_id} Assistant: {response}{RESET_COLOR}", flush=True)
            
            # Send response back
            await websocket.send_text(json.dumps({
                "response": response,
                "session_id": session_id
            }))
            
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket Disconnected", session_id=session_id)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}", session_id=session_id)
