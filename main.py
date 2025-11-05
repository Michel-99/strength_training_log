import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app import routes, db

# --- App Initialization ---
app = FastAPI(title="Strength Log API")

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
    if full_path.startswith("workouts") or \
       full_path.startswith("generate-tip") or \
       full_path.startswith("exercises") or \
       full_path.startswith("analysis"):
        # This part should ideally not be hit if routes are defined correctly,
        # but as a fallback, let the 404 handler do its job.
        return FileResponse('frontend/index.html', media_type='text/html')

    # Serve static files like manifest.json, sw.js, etc.
    file_path = os.path.join("frontend", full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # Default to index.html for any other route
    return FileResponse('frontend/index.html', media_type='text/html')

# --- Main Execution (for local running) ---
if __name__ == "__main__":
    db.init_db_if_needed()
    port = int(os.environ.get("PORT", 5001))
    print(f"Serving app on http://127.0.0.1:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

