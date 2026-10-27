import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agents.diagram_agent import DiagramAgent
from app.api.discovery_routes import resolve_root
from app.core.config import get_settings
from app.models.diagram import DiagramsResult
from app.models.discovery import DiscoveryRequest

router = APIRouter(prefix="/diagrams", tags=["diagrams"])


@router.post("", response_model=DiagramsResult, response_model_by_alias=True)
def generate_diagrams(body: DiscoveryRequest):
    root = resolve_root(body)
    try:
        result = DiagramAgent().run(root)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagram generation failed: {exc}")
    out_dir = Path(get_settings().reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = result.applicationName
    (out_dir / f"diagrams-{name}.json").write_text(
        json.dumps(result.model_dump(by_alias=True), indent=2), encoding="utf-8")
    md = (f"# {name} diagrams\n\n## Module diagram\n\n```mermaid\n{result.moduleDiagram}\n```\n\n"
          f"## Dependency diagram\n\n```mermaid\n{result.dependencyDiagram}\n```\n\n"
          f"## API flow diagram\n\n```mermaid\n{result.apiFlowDiagram}\n```\n")
    (out_dir / f"diagrams-{name}.md").write_text(md, encoding="utf-8")
    return result
