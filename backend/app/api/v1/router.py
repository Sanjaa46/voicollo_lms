# =============================================================================
# purpose:  Aggregates all v1 sub-routers. Auth router added.
# =============================================================================

from fastapi import APIRouter
from app.api.v1 import admin, auth, ingest, query, service

api_v1_router = APIRouter(prefix="/api/v1")

# Order matters: admin (specific paths) before query (wildcard /{type}/{id})
api_v1_router.include_router(auth.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(service.router)
api_v1_router.include_router(ingest.router)
api_v1_router.include_router(query.router)
