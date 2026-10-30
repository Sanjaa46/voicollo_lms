from fastapi import APIRouter

from app.api.v1 import auth, ingest, logs, services, system

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(system.router)
api_v1_router.include_router(services.router)
api_v1_router.include_router(ingest.router)
# Last: /logs/{log_type}/{log_id} must not shadow /logs/export.
api_v1_router.include_router(logs.router)
