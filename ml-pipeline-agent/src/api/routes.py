"""FastAPI route handlers — pipeline control plane."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, PlainTextResponse

from src.api.deps import get_executor
from src.api.schemas import (
    ArtifactListResponse,
    HealthResponse,
    PipelineCreateRequest,
    PipelineCreateResponse,
    PipelineStatusResponse,
)
from src.config.settings import settings
from src.pipeline.executor import PipelineExecutor
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["pipelines"])


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Service health check."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        llm_provider=settings.LLM_PROVIDER,
        sandbox_type=settings.SANDBOX_TYPE,
    )


# ── Pipeline CRUD ─────────────────────────────────────────────────────────────


@router.post("/pipelines", response_model=PipelineCreateResponse, status_code=202)
async def create_pipeline(
    request: PipelineCreateRequest,
    executor: PipelineExecutor = Depends(get_executor),
) -> PipelineCreateResponse:
    """Trigger a new ML pipeline execution.

    The pipeline runs asynchronously in the background.
    Poll GET /pipelines/{pipeline_id} for status.
    """
    logger.info(
        "Pipeline creation requested",
        dataset=request.dataset_path,
        objectives=request.objectives[:100],
    )

    # Validate dataset exists
    from pathlib import Path

    if not request.dataset_path.startswith("s3://"):
        if not Path(request.dataset_path).exists():
            raise HTTPException(
                status_code=400,
                detail=f"Dataset not found: {request.dataset_path}",
            )

    # Generate pipeline_id HERE — pass it to the executor so they match
    pipeline_id = str(uuid.uuid4())

    # Register immediately so status polling works before execution starts
    executor.register_pipeline(pipeline_id, request.objectives, request.dataset_path)

    # Launch pipeline as a background asyncio task
    async def _run_pipeline() -> None:
        try:
            result = await executor.execute(
                dataset_path=request.dataset_path,
                objectives=request.objectives,
                pipeline_id=pipeline_id,
                dataset_format=request.dataset_format,
                max_loops=request.max_loops,
            )
            logger.info(
                "Background pipeline completed",
                pipeline_id=result.pipeline_id,
                status=result.status,
            )
        except Exception as e:
            logger.error("Background pipeline failed", pipeline_id=pipeline_id, error=str(e))

    # Use asyncio.create_task for proper async background execution
    asyncio.create_task(_run_pipeline())

    return PipelineCreateResponse(
        pipeline_id=pipeline_id,
        status="accepted",
        message=f"Pipeline {pipeline_id} started. Poll GET /api/v1/pipelines/{pipeline_id} for status.",
    )


@router.get("/pipelines", response_model=list[dict[str, Any]])
async def list_pipelines(
    executor: PipelineExecutor = Depends(get_executor),
) -> list[dict[str, Any]]:
    """List all known pipelines."""
    return await executor.list_pipelines()


@router.get("/pipelines/{pipeline_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    pipeline_id: str,
    executor: PipelineExecutor = Depends(get_executor),
) -> PipelineStatusResponse:
    """Get pipeline execution status and results."""
    status = await executor.get_status(pipeline_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    return PipelineStatusResponse(**status)


@router.get("/pipelines/{pipeline_id}/artifacts", response_model=ArtifactListResponse)
async def list_pipeline_artifacts(
    pipeline_id: str,
    executor: PipelineExecutor = Depends(get_executor),
) -> ArtifactListResponse:
    """List all artifacts produced by a pipeline."""
    artifacts = await executor.get_artifacts(pipeline_id)
    return ArtifactListResponse(pipeline_id=pipeline_id, artifacts=artifacts)


# ── Graph Visualization ──────────────────────────────────────────────────


@router.get("/graph/mermaid", response_class=PlainTextResponse)
async def get_graph_mermaid() -> str:
    """Return the pipeline graph as a Mermaid flowchart definition."""
    from src.graph.builder import get_mermaid_definition

    return get_mermaid_definition()


@router.get("/graph/png")
async def get_graph_png() -> FileResponse:
    """Render and return the pipeline graph as a PNG image."""
    from pathlib import Path

    from src.graph.builder import save_mermaid_files

    output_dir = Path("/tmp/ml-pipeline/graph")
    files = save_mermaid_files(output_dir)

    if files.get("png") and Path(files["png"]).exists():
        return FileResponse(
            files["png"],
            media_type="image/png",
            filename="pipeline_graph.png",
        )

    # If PNG render isn't available, return the mermaid file with instructions
    raise HTTPException(
        status_code=501,
        detail=(
            "PNG rendering requires mermaid-cli (mmdc). "
            "Use GET /api/v1/graph/mermaid to get the Mermaid definition, "
            "or install @mermaid-js/mermaid-cli in the container. "
            "You can also paste the Mermaid definition into https://mermaid.live"
        ),
    )


@router.get("/graph/html")
async def get_graph_html() -> PlainTextResponse:
    """Return a self-contained HTML page that renders the pipeline graph using Mermaid.js."""
    from src.graph.builder import get_mermaid_definition

    mermaid_def = get_mermaid_definition()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ML Pipeline Graph</title>
    <style>
        body {{
            background: #0f0f23;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 1rem;
            box-sizing: border-box;
        }}
        .mermaid {{
            max-width: 95vw;
            max-height: 95vh;
        }}
        .mermaid svg {{
            max-width: 100%;
            max-height: 95vh;
        }}
    </style>
</head>
<body>
    <div class="mermaid">
{mermaid_def}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
    </script>
</body>
</html>"""

    return PlainTextResponse(content=html, media_type="text/html")


# ── Pipeline Plots ────────────────────────────────────────────────────────────


def _find_plot_dirs(pipeline_id: str, status: dict[str, Any]) -> list["Path"]:
    """Return candidate directories where plot PNGs might live (working_dir first, then artifact store)."""
    from pathlib import Path

    dirs: list[Path] = []
    working_dir = status.get("working_dir")
    if working_dir:
        wd_plots = Path(working_dir) / "plots"
        if wd_plots.exists():
            dirs.append(wd_plots)
    # Artifact store fallback (persisted after completion)
    artifact_plots = Path(settings.ARTIFACT_LOCAL_PATH) / pipeline_id / "plots"
    if artifact_plots.exists():
        dirs.append(artifact_plots)
    return dirs


@router.get("/pipelines/{pipeline_id}/plots")
async def list_pipeline_plots(
    pipeline_id: str,
    executor: PipelineExecutor = Depends(get_executor),
) -> list[dict[str, str]]:
    """List available plot images for a pipeline."""
    status = await executor.get_status(pipeline_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    seen: set[str] = set()
    plots: list[dict[str, str]] = []

    for plot_dir in _find_plot_dirs(pipeline_id, status):
        for p in sorted(plot_dir.glob("*.png")):
            if p.name not in seen:
                seen.add(p.name)
                plots.append({
                    "filename": p.name,
                    "title": p.stem.replace("_", " ").replace("plot ", "").title(),
                    "url": f"/api/v1/pipelines/{pipeline_id}/plots/{p.name}",
                })

    return plots


@router.get("/pipelines/{pipeline_id}/plots/{filename}")
async def get_pipeline_plot(
    pipeline_id: str,
    filename: str,
    executor: PipelineExecutor = Depends(get_executor),
) -> FileResponse:
    """Serve a specific plot image."""
    from pathlib import Path

    # Sanitize filename to prevent directory traversal
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    status = await executor.get_status(pipeline_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    for plot_dir in _find_plot_dirs(pipeline_id, status):
        plot_path = plot_dir / safe_name
        if plot_path.exists():
            return FileResponse(plot_path, media_type="image/png", filename=safe_name)

    raise HTTPException(status_code=404, detail=f"Plot not found: {filename}")


# ── Dataset Upload ────────────────────────────────────────────────────────────


@router.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload a dataset file for pipeline processing."""
    from pathlib import Path

    upload_dir = Path("/tmp/ml-pipeline/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / (file.filename or "dataset.csv")
    content = await file.read()
    file_path.write_bytes(content)

    logger.info("Dataset uploaded", filename=file.filename, size=len(content))

    return {
        "path": str(file_path),
        "filename": file.filename or "dataset.csv",
        "size_bytes": str(len(content)),
    }
