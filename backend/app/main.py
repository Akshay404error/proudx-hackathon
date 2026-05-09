"""PathForge — AI-Powered Learning Roadmap Platform.

Run: uvicorn app.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.database import init_db
from app.api import auth, chat, roadmaps, progress, profile, resources, reports
from app.services.ai_service import ollama_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s : %(message)s",
)
logger = logging.getLogger("pathforge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting PathForge…")
    init_db()
    healthy = await ollama_service.health_check()
    if healthy:
        logger.info(f"Ollama is reachable at {settings.OLLAMA_BASE_URL} (model: {settings.OLLAMA_MODEL})")
    else:
        logger.warning(f"Ollama NOT reachable at {settings.OLLAMA_BASE_URL} — fallback roadmaps will be used")
    yield
    logger.info("Shutting down PathForge.")


app = FastAPI(
    title="PathForge API",
    description="AI-powered, conversational learning roadmap platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health():
    ok = await ollama_service.health_check()
    return {"status": "ok", "ollama": "up" if ok else "down", "model": settings.OLLAMA_MODEL}


# Mount routers under /api
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(roadmaps.router, prefix="/api")
app.include_router(progress.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )