from fastapi import APIRouter, Body, WebSocket, WebSocketDisconnect
from src.agentic.bots.kisan import kisan_bot
from src.utils.logger import logger
import json

router = APIRouter(prefix="/v1/kisan")

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
            user_msg = json.loads(data).get("message")
            
            # Get response from AI
            response = await kisan_bot.chat(user_msg, session_id=session_id)
            
            # Send response back
            print(f"[WS DEBUG] -> Sending response to client...", flush=True)
            await websocket.send_text(json.dumps({
                "response": response,
                "session_id": session_id
            }))
            print(f"[WS DEBUG] -> Response Sent Successfully.", flush=True)
            
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket Disconnected", session_id=session_id)
    except Exception as e:
        print(f"[WS ERROR] -> {e}", flush=True)
        logger.error(f"WebSocket Error: {e}", session_id=session_id)
