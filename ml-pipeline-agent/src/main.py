"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config.settings import settings
from src.utils.logging import setup_logging

# Initialize logging
setup_logging(settings.LOG_LEVEL)

# Create app
app = FastAPI(
    title="ML Pipeline Agent",
    description="LangGraph-based autonomous ML pipeline",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — permissive for dev, restrict in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENV == "dev" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router)


@app.on_event("startup")
async def startup() -> None:
    """Application startup tasks."""
    from src.utils.logging import get_logger

    logger = get_logger("startup")
    logger.info(
        "ML Pipeline Agent starting",
        env=settings.ENV,
        llm_provider=settings.LLM_PROVIDER,
        sandbox=settings.SANDBOX_TYPE,
        checkpoint=settings.CHECKPOINT_BACKEND,
    )

    # Set LangSmith env vars if enabled
    if settings.LANGSMITH_ENABLED and settings.LANGSMITH_API_KEY:
        import os

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
        logger.info("LangSmith tracing enabled", project=settings.LANGSMITH_PROJECT)

    # Generate pipeline graph visualization on startup
    try:
        from src.graph.builder import save_mermaid_files

        graph_files = save_mermaid_files("/tmp/ml-pipeline/graph")
        logger.info(
            "Pipeline graph files generated",
            mermaid=graph_files.get("mermaid"),
            png=graph_files.get("png"),
        )
    except Exception as e:
        logger.warning("Graph visualization generation failed (non-critical)", error=str(e))
