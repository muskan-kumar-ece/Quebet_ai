from fastapi import APIRouter
from app.api.v1.routes import health, models_list

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(models_list.router)
