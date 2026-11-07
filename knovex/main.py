"""
Knovex AI - Main FastAPI Application
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from knovex.api import router as api_router
from knovex.config import get_settings
from knovex.database import Base, async_engine
from knovex.observability import RequestTracingMiddleware, init_langsmith, setup_logging
from knovex.rag import get_dense_embeddings, get_sparse_embeddings, get_cross_encoder

# Standard structured logging
setup_logging(level="INFO")
logger = logging.getLogger("knovex")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist and directories are ready
    logger.info("Initializing Knovex AI application...")
    init_langsmith(
        tracing_enabled=settings.LANGCHAIN_TRACING_V2,
        api_key=settings.LANGCHAIN_API_KEY,
        project=settings.LANGCHAIN_PROJECT,
        endpoint=settings.LANGCHAIN_ENDPOINT,
    )
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Path("./data/qdrant_local").mkdir(parents=True, exist_ok=True)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema verified.")

    # Preload and warm AI models at startup before accepting traffic
    logger.info("Preloading AI models (Dense, BM25, CrossEncoder)...")
    try:
        await asyncio.to_thread(get_dense_embeddings)
        await asyncio.to_thread(get_sparse_embeddings)
        if settings.ENABLE_RERANKER:
            encoder = await asyncio.to_thread(get_cross_encoder)
            # Warm-up inference so PyTorch memory & execution graph are primed
            await asyncio.to_thread(encoder.predict, [["warmup", "warmup text"]], show_progress_bar=False)
        from knovex.rag import get_vector_store
        await asyncio.to_thread(get_vector_store)
        logger.info("All AI models preloaded, warmed, and ready.")
    except Exception as e:
        logger.warning(f"Model preloading warning: {e}")

    yield
    # Shutdown
    logger.info("Shutting down Knovex AI...")
    await async_engine.dispose()




app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Multi-Tenant RAG Document Intelligence Platform with Hybrid Search & LangGraph",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Standard Request Tracing & Timing Middleware (assigns and logs X-Request-ID and execution time)
app.add_middleware(RequestTracingMiddleware)

# Mount REST API
app.include_router(api_router)

# Mount Frontend Static Files (checks built frontend/dist, then fallback to knovex/static)
static_dir = Path(__file__).parent / "static"
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
target_static = frontend_dist if frontend_dist.exists() else static_dir

if target_static.exists():
    app.mount("/", StaticFiles(directory=str(target_static), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("knovex.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
