"""Graph builder — constructs the LangGraph StateGraph with all nodes and edges."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from src.graph.edges import route_from_critic
from src.graph.nodes.critic import critic_node
from src.graph.nodes.data_profiler import data_profiler_node
from src.graph.nodes.evaluator import evaluator_node
from src.graph.nodes.feature_engineer import feature_engineer_node
from src.graph.nodes.model_trainer import model_trainer_node
from src.graph.nodes.visualizer import visualizer_node
from src.llm.base import LLMProvider
from src.sandbox.base import ExecutionSandbox
from src.state.schema import PipelineState
from src.utils.logging import get_logger

logger = get_logger(__name__)

# ── Mermaid definition for the pipeline graph ─────────────────────────────────

MERMAID_DEFINITION = """\
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#7c3aed', 'lineColor': '#7c3aed', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e', 'clusterBkg': '#16213e', 'clusterBorder': '#7c3aed'}}}%%
flowchart TD
    START([🚀 START]) --> DP[📊 Data Profiler]
    DP --> FE[🔧 Feature Engineer]
    FE --> VIZ[📈 Visualizer]
    VIZ --> MT[🤖 Model Trainer]
    MT --> EVAL[✅ Evaluator]
    EVAL --> CRITIC{🧐 Critic Review}

    CRITIC -->|finalize| DONE([🏁 END])
    CRITIC -->|refine_features| FE
    CRITIC -->|retrain_model| MT

    style START fill:#7c3aed,stroke:#a78bfa,stroke-width:2px,color:#fff
    style DONE fill:#059669,stroke:#34d399,stroke-width:2px,color:#fff
    style DP fill:#1e40af,stroke:#60a5fa,stroke-width:2px,color:#e0e0e0
    style FE fill:#1e40af,stroke:#60a5fa,stroke-width:2px,color:#e0e0e0
    style VIZ fill:#1e40af,stroke:#60a5fa,stroke-width:2px,color:#e0e0e0
    style MT fill:#1e40af,stroke:#60a5fa,stroke-width:2px,color:#e0e0e0
    style EVAL fill:#1e40af,stroke:#60a5fa,stroke-width:2px,color:#e0e0e0
    style CRITIC fill:#92400e,stroke:#fbbf24,stroke-width:3px,color:#fef3c7
"""


def get_mermaid_definition() -> str:
    """Return the Mermaid flowchart definition for the pipeline graph."""
    return MERMAID_DEFINITION


def save_mermaid_files(output_dir: str | Path) -> dict[str, str]:
    """Save Mermaid definition as .mermaid file and render to PNG.

    Args:
        output_dir: Directory to write files into.

    Returns:
        Dict with paths: {"mermaid": "...", "png": "..."} (png may be None if rendering fails).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Always save the .mermaid text file
    mermaid_path = output_dir / "pipeline_graph.mermaid"
    mermaid_path.write_text(MERMAID_DEFINITION, encoding="utf-8")
    result = {"mermaid": str(mermaid_path), "png": None}

    # Try to render PNG via mermaid-cli (mmdc) if available
    png_path = output_dir / "pipeline_graph.png"
    try:
        import subprocess

        proc = subprocess.run(
            ["mmdc", "-i", str(mermaid_path), "-o", str(png_path),
             "-b", "transparent", "-w", "1200", "-H", "800"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0 and png_path.exists():
            result["png"] = str(png_path)
            logger.info("Pipeline graph PNG rendered", path=str(png_path))
        else:
            logger.warning("mmdc render failed, trying LangGraph draw_mermaid_png", stderr=proc.stderr[:200])
            # Fallback: try LangGraph's built-in draw_mermaid_png
            _try_langgraph_png(png_path)
            if png_path.exists():
                result["png"] = str(png_path)
    except FileNotFoundError:
        logger.info("mmdc not installed, trying LangGraph draw_mermaid_png")
        _try_langgraph_png(png_path)
        if png_path.exists():
            result["png"] = str(png_path)
    except Exception as e:
        logger.warning("PNG render failed", error=str(e))
        _try_langgraph_png(png_path)
        if png_path.exists():
            result["png"] = str(png_path)

    return result


def _try_langgraph_png(png_path: Path) -> None:
    """Attempt to render PNG using LangGraph's draw_mermaid_png (requires pyppeteer or playwright)."""
    try:
        from langgraph.graph.mermaid import draw_mermaid_png

        png_bytes = draw_mermaid_png(MERMAID_DEFINITION)
        if png_bytes:
            png_path.write_bytes(png_bytes)
            logger.info("Pipeline graph PNG rendered via LangGraph", path=str(png_path))
    except ImportError:
        logger.info("LangGraph draw_mermaid_png not available, PNG skipped")
    except Exception as e:
        logger.warning("LangGraph PNG render failed", error=str(e))


def build_pipeline_graph(
    llm_provider: LLMProvider,
    sandbox: ExecutionSandbox,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """Build the ML pipeline supervisor graph.

    Graph topology:
        START → data_profiler → feature_engineer → visualizer → model_trainer → evaluator → critic
                                      ↑                              ↑                         |
                                      └──────────────────────────────┴─── (conditional) ───────┘
                                                                                               |
                                                                                            → END

    The Critic node decides:
        - "finalize"         → END
        - "refine_features"  → back to feature_engineer
        - "retrain_model"    → back to model_trainer

    Args:
        llm_provider: Configured LLM provider (Claude or GPT-4o).
        sandbox: Code execution sandbox.
        checkpointer: Optional checkpointer for durable execution.

    Returns:
        Compiled LangGraph ready for execution.
    """
    graph = StateGraph(PipelineState)

    # ── Register Nodes ────────────────────────────────────────────────────
    graph.add_node("data_profiler", data_profiler_node(llm_provider, sandbox))
    graph.add_node("feature_engineer", feature_engineer_node(llm_provider, sandbox))
    graph.add_node("visualizer", visualizer_node(llm_provider, sandbox))
    graph.add_node("model_trainer", model_trainer_node(llm_provider, sandbox))
    graph.add_node("evaluator", evaluator_node(llm_provider, sandbox))
    graph.add_node("critic", critic_node(llm_provider))

    # ── Linear Edges (forward progression) ────────────────────────────────
    graph.set_entry_point("data_profiler")
    graph.add_edge("data_profiler", "feature_engineer")
    graph.add_edge("feature_engineer", "visualizer")
    graph.add_edge("visualizer", "model_trainer")
    graph.add_edge("model_trainer", "evaluator")
    graph.add_edge("evaluator", "critic")

    # ── Conditional Edge (Critic → loop back or finalize) ─────────────────
    graph.add_conditional_edges(
        "critic",
        route_from_critic,
        {
            "feature_engineer": "feature_engineer",
            "model_trainer": "model_trainer",
            "finalize": END,
        },
    )

    # ── Compile ───────────────────────────────────────────────────────────
    compile_kwargs: dict[str, Any] = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer

    compiled = graph.compile(**compile_kwargs)

    logger.info(
        "Pipeline graph compiled",
        nodes=["data_profiler", "feature_engineer", "visualizer", "model_trainer", "evaluator", "critic"],
        conditional_edges=["critic → feature_engineer | model_trainer | END"],
    )

    return compiled
