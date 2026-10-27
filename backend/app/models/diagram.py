from typing import List

from app.models.discovery import CamelModel


class DiagramsResult(CamelModel):
    applicationName: str
    moduleDiagram: str
    dependencyDiagram: str
    apiFlowDiagram: str
    warnings: List[str] = []
