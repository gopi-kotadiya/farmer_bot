from fastapi import APIRouter, Body, WebSocket, WebSocketDisconnect
from src.agentic.bots.kisan import kisan_bot
from src.utils.logger import logger
import json

router = APIRouter(prefix="/v1/kisan")
USER_COLOR = "\033[96m"
ASSISTANT_COLOR = "\033[95m"
RESET_COLOR = "\033[0m"

@router.post("/chat")
async def chat(message: str = Body(..., embed=True), session_id: str = Body(None, embed=True)):
    """Standard REST API for Postman."""
    response = await kisan_bot.chat(message, session_id=session_id)
    return {"status": "success", "response": response}

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Real-time WebSocket for Chat."""
    await websocket.accept()
    logger.info(f"🔌 WebSocket Connected", session_id=session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            user_msg = json.loads(data).get("message", "")
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
