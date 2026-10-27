import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agents.recommendation_agent import IntegrationRecommendationAgent
from app.api.discovery_routes import resolve_root
from app.core.config import get_settings
from app.models.recommendation import IntegrationRecommendationResult, RecommendRequest

router = APIRouter(prefix="/recommendation", tags=["recommendation"])


@router.post("", response_model=IntegrationRecommendationResult, response_model_by_alias=True)
def recommend_integration(body: RecommendRequest):
    base_root, enh_root = resolve_root(body.base), resolve_root(body.enhancement)
    try:
        result = IntegrationRecommendationAgent().analyze_and_recommend(base_root, enh_root)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {exc}")
    out_dir = Path(get_settings().reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"recommendation-{result.baseApplication}-vs-{result.enhancementApplication}.json"
    (out_dir / name).write_text(json.dumps(result.model_dump(by_alias=True), indent=2), encoding="utf-8")
    return result
