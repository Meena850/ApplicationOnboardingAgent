from typing import Annotated, Dict, List

from pydantic import BeforeValidator

from app.models.discovery import CamelModel


def _percent(v) -> int:
    """Accept 92, 92.5, "92%", or 0.92 and return an int in 0..100."""
    if isinstance(v, str):
        v = v.strip().rstrip("%")
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0
    if 0 < f <= 1:
        f *= 100
    return max(0, min(100, round(f)))


Confidence = Annotated[int, BeforeValidator(_percent)]


class BusinessCapability(CamelModel):
    name: str
    description: str = ""
    modules: List[str] = []
    reasoning: str = ""
    confidence: Confidence = 0


class Feature(CamelModel):
    name: str
    summary: str = ""
    modules: List[str] = []
    reasoning: str = ""
    confidence: Confidence = 0


class UserWorkflow(CamelModel):
    name: str
    steps: List[str] = []
    features: List[str] = []
    reasoning: str = ""
    confidence: Confidence = 0


class FunctionalModule(CamelModel):
    name: str
    purpose: str = ""
    components: List[str] = []  # real code artifacts (controllers, pages, services...)
    features: List[str] = []
    confidence: Confidence = 0


class FeatureUnderstandingResult(CamelModel):
    applicationName: str
    summary: str = ""
    businessCapabilities: List[BusinessCapability] = []
    features: List[Feature] = []
    userWorkflows: List[UserWorkflow] = []
    functionalModules: List[FunctionalModule] = []
    overallConfidence: Confidence = 0
    model: str = ""
    warnings: List[str] = []
