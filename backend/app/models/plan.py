from typing import List, Optional

from app.models.discovery import CamelModel
from app.models.impact import ImpactRequest  # noqa: F401  (same request shape: base, enhancement, topN)


class PlanTask(CamelModel):
    id: str  # T1, T2, ... (global, in execution order)
    phase: int
    category: str  # data | service | wiring | controller | ui | routing | verify
    title: str
    description: str
    files: List[str] = []  # files involved (existing files to edit or new files to create)
    dependsOn: List[str] = []  # task ids that must be finished first
    validation: List[str] = []
    level: str = "Low"  # risk, from the impact analysis: Low | Medium | High
    effort: str = "S"  # S | M | L


class PlanPhase(CamelModel):
    number: int
    name: str
    goal: str
    tasks: List[PlanTask] = []
    exitCriteria: List[str] = []


class ImplementationPlan(CamelModel):
    baseApplication: str
    enhancementApplication: str
    overallImpact: str
    overallScore: int
    summary: str
    phases: List[PlanPhase] = []
    taskCount: int = 0
    planMarkdown: str = ""
    warnings: List[str] = []
