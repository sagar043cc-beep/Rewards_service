from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers.root import router
from app.routers.events import router as events_router
from app.routers.tenants import router as tenants_router
from app.routers.badges import router as badges_router
from app.routers.rewards import router as rewards_router

app = FastAPI()

# Mount static files for uploaded badge icons
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)
app.include_router(events_router)
app.include_router(tenants_router)
app.include_router(badges_router)
app.include_router(rewards_router)
