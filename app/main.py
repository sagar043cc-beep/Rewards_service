import os
from pathlib import Path

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.routers.root import router
from app.routers.events import router as events_router
from app.routers.badges import router as badges_router
from app.routers.rewards import router as rewards_router
from app.routers.upload import router as upload_router
from app.auth import router as auth_router

app = FastAPI()

# CORS configuration — allow all origins by default (development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for uploaded badge icons
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)
app.include_router(events_router)
app.include_router(badges_router)
app.include_router(rewards_router)
app.include_router(upload_router)
app.include_router(auth_router)
