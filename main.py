import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.agentic.bots.telegram_bot import run_telegram_bot
from src.controller.agent_ws import router as kisan_router
from src.utils.alert_scheduler import start_alert_scheduler
from src.utils.database import init_db
from src.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_alert_scheduler()
    yield


app = FastAPI(title="Farmer Bot System", lifespan=lifespan)
app.include_router(kisan_router)

def run_api_server():
    logger.info("🌐 API Server starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "telegram":
            run_telegram_bot()
        elif mode == "api":
            run_api_server()
        else:
            print("Usage: python main.py [telegram|api]")
    else:
        # For debugging: Run ONLY API by default or ask user
        logger.info("Starting API Server Only (Fast Debug Mode)...")
        run_api_server()
