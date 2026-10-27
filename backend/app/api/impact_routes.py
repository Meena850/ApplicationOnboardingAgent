import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agents.impact_agent import ImpactAnalysisAgent
from app.api.discovery_routes import resolve_root
from app.core.config import get_settings
from app.models.impact import ImpactAnalysisResult, ImpactRequest

router = APIRouter(prefix="/impact", tags=["impact"])


@router.post("", response_model=ImpactAnalysisResult, response_model_by_alias=True)
def analyze_impact(body: ImpactRequest):
    base_root, enh_root = resolve_root(body.base), resolve_root(body.enhancement)
    try:
        result = ImpactAnalysisAgent().analyze_and_assess(base_root, enh_root, top_n=body.topN)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Impact analysis failed: {exc}")
    out_dir = Path(get_settings().reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"impact-{result.baseApplication}-vs-{result.enhancementApplication}"
    (out_dir / f"{stem}.json").write_text(json.dumps(result.model_dump(by_alias=True), indent=2), encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(result.summaryReport, encoding="utf-8")
    return result
