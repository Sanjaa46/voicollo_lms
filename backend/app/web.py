"""Serve the built React SPA from the same origin as the API."""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

_NO_CACHE = {"Cache-Control": "no-cache"}


def mount_frontend(app: FastAPI, dist_dir: str) -> None:
    dist = Path(dist_dir)
    index = dist / "index.html"
    if not index.is_file():
        logger.warning("Frontend not found at %s; serving API only.", dist)
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", _ImmutableStatic(directory=assets), name="assets")

    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str, request: Request):
        if path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "NOT_FOUND",
                    "message": "Not found",
                    "details": None,
                    "request_id": getattr(request.state, "request_id", ""),
                },
            )
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        # Client-side routes (/logs, /services, ...) all get the app shell.
        return FileResponse(index, headers=_NO_CACHE)

    logger.info("Serving frontend from %s", dist)


class _ImmutableStatic(StaticFiles):
    """Vite emits content-hashed file names, so assets can be cached forever."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
