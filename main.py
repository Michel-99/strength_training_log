import os
import uvicorn
import sqlalchemy
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app import routes, db
from app.db import db_manager

# --- App Initialization ---
app = FastAPI(title="Strength Log API")

# Allow local frontend dev servers (Flutter web/JS dev server) to call the API.
_cors_allow_origins = os.environ.get("CORS_ALLOW_ORIGINS")
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        [o.strip() for o in _cors_allow_origins.split(",")]
        if _cors_allow_origins
        else []
    ),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API routes
app.include_router(routes.router)

# --- Frontend Routes (Serving the PWA) ---
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/{full_path:path}")
async def serve_pwa(request: Request, full_path: str):
    """
    Serve the PWA.
    This serves 'index.html' for all non-API routes, allowing client-side
    routing to work.
    """
    # Check if the path is an API route
    if (
        full_path.startswith("auth")
        or full_path.startswith("workouts")
        or full_path.startswith("exercises")
        or full_path.startswith("analysis")
    ):
        # This part should ideally not be hit if routes are defined correctly,
        # but as a fallback, let the 404 handler do its job.
        return FileResponse("frontend/index.html", media_type="text/html")

    # Serve static files like manifest.json, sw.js, etc.
    file_path = os.path.join("frontend", full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # If it looks like a direct asset request, do not silently serve index.html.
    # This prevents missing files (e.g. /sw.js) from returning 200 HTML.
    _, ext = os.path.splitext(full_path)
    if ext:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="File not found")

    # Default to index.html for any other route
    return FileResponse("frontend/index.html", media_type="text/html")


# --- Main Execution (for local running) ---
if __name__ == "__main__":
    DB_manager = db_manager()
    port = int(os.environ.get("PORT", 5004))
    print(f"Serving app on http://127.0.0.1:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
