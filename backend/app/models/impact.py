from typing import Dict, List, Optional

from app.models.discovery import CamelModel, DiscoveryRequest


class AffectedItem(CamelModel):
    category: str  # components | routes | apis | controllers | services
    name: str
    file: Optional[str] = None
    level: str  # Low | Medium | High
    score: int
    change: str  # added | modified | dependent
    distance: int = 0  # 0 = at an integration point, 1.. = hops through dependencies
    reasons: List[str] = []
    integrationPoints: List[str] = []


class CategoryImpact(CamelModel):
    total: int = 0
    low: int = 0
    medium: int = 0
    high: int = 0
    items: List[AffectedItem] = []


class IntegrationPointImpact(CamelModel):
    filePath: str
    action: str  # create | modify
    level: str
    score: int
    summary: str
    affectedCount: int = 0


class ImpactAnalysisResult(CamelModel):
    baseApplication: str
    enhancementApplication: str
    overallLevel: str
    overallScore: int
    summary: str
    components: CategoryImpact = CategoryImpact()
    routes: CategoryImpact = CategoryImpact()
    apis: CategoryImpact = CategoryImpact()
    controllers: CategoryImpact = CategoryImpact()
    services: CategoryImpact = CategoryImpact()
    integrationPoints: List[IntegrationPointImpact] = []
    summaryReport: str = ""  # Markdown
    warnings: List[str] = []


class ImpactRequest(CamelModel):
    base: DiscoveryRequest
    enhancement: DiscoveryRequest
    topN: Optional[int] = None  # limit analysis to the N best integration points (default: all)
