"""V1 API router aggregation."""
from fastapi import APIRouter

from app.api.v1.endpoints import health, sessions

api_router_v1 = APIRouter()
api_router_v1.include_router(health.router, prefix="/health")
api_router_v1.include_router(sessions.router, prefix="/onboarding")