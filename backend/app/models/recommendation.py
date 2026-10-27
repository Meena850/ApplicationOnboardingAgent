from typing import List

from app.models.comparison import RepositorySnapshot  # noqa: F401  (re-exported for API/typing)
from app.models.discovery import CamelModel, DiscoveryRequest


class RecommendedLocation(CamelModel):
    rank: int
    filePath: str  # a file (modify) or a directory ending in "/" (create)
    locationType: str  # file | directory
    action: str  # modify | create
    reason: str
    confidence: int  # 0-100, see RecommendationAgent for how it is derived
    confidenceLabel: str = ""  # e.g. "94%"
    evidence: List[str] = []
    supports: List[str] = []  # "kind:name" components that this location integrates
    suggestedFiles: List[str] = []  # exact files to create (create actions)


class IntegrationRecommendationResult(CamelModel):
    baseApplication: str
    enhancementApplication: str
    recommendations: List[RecommendedLocation] = []
    locationsConsidered: int = 0
    warnings: List[str] = []


class RecommendRequest(CamelModel):
    base: DiscoveryRequest
    enhancement: DiscoveryRequest
