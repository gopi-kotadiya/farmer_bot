from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional

import json

from src.agentic.bots.kisan import kisan_bot
from src.agentic.tools.kisan_tools.crop_disease import detect_crop_disease, guess_image_mime
from src.utils.daily_alert_job import run_daily_alerts_once
from src.utils.globals import globals
from src.utils.logger import logger

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
            "response": "Send JSON with `message` or `text`. Example: {\"message\":\"hello\"}",
            "session_id": sid or None,
        }
    try:
        logger.user_message(user_msg, session_id=sid)
        response = await kisan_bot.chat(user_msg, session_id=sid)
        text = response if isinstance(response, str) else str(response)
        logger.assistant_message(text, session_id=sid)
        return {"status": "success", "response": text, "session_id": sid or None}
    except Exception as e:
        logger.exception("POST /chat failed")
        return {
            "status": "error",
            "response": f"Server error: {e!s}",
            "session_id": sid or None,
        }


@router.post("/crop-disease")
async def crop_disease_analyze(
    image: UploadFile = File(..., description="Crop photo (JPEG, PNG, WebP, etc.)"),
    caption: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
):
    """
    Image upload → Groq vision (`detect_crop_disease`).
    Any common image type; MIME taken from file + magic-byte fallback.
    """
    sid = (session_id or "").strip()
    raw = await image.read()
    if not raw:
        return {"status": "error", "response": "Koi image data nahi mila.", "session_id": sid or None}

    declared = (image.content_type or "").strip().lower()
    mime = declared if declared.startswith("image/") else guess_image_mime(raw)

    try:
        text = detect_crop_disease(
            raw, user_prompt=caption or "", session_id=sid, mime_type=mime
        )
    except Exception as e:
        logger.error(f"crop-disease endpoint: {e}", session_id=sid)
        return {"status": "error", "response": str(e), "session_id": sid or None}

    return {"status": "success", "response": text, "session_id": sid or None}


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
            logger.user_message(user_msg, session_id=session_id)
            
            # Get response from AI
            response = await kisan_bot.chat(user_msg, session_id=session_id)
            logger.assistant_message(response, session_id=session_id)
            
            # Send response back
            await websocket.send_text(json.dumps({
                "response": response,
                "session_id": session_id
            }))
            
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket Disconnected", session_id=session_id)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}", session_id=session_id)
