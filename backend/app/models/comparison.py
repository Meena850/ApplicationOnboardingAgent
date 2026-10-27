from typing import Dict, List, Optional

from app.models.architecture import ArchitectureResult
from app.models.discovery import CamelModel, DiscoveryRequest, DiscoveryResult


class EntityInfo(CamelModel):
    name: str
    kind: str  # ef-entity | model | sql-table
    table: Optional[str] = None
    properties: Dict[str, str] = {}
    file: str


class RepositorySnapshot(CamelModel):
    """Everything the comparison needs to know about one analyzed application."""
    discovery: DiscoveryResult
    architecture: ArchitectureResult
    entities: List[EntityInfo] = []


class ComponentRef(CamelModel):
    kind: str  # module | route | api | service | entity
    name: str
    file: Optional[str] = None
    details: Dict[str, str] = {}


class ModifiedComponent(CamelModel):
    kind: str
    name: str
    conflicts: List[str] = []  # same identity, incompatible definition
    additions: List[str] = []  # enhancement adds things the base lacks
    base: ComponentRef
    enhancement: ComponentRef


class CategoryComparison(CamelModel):
    base: int = 0
    enhancement: int = 0
    common: int = 0
    onlyInBase: List[ComponentRef] = []
    onlyInEnhancement: List[ComponentRef] = []
    modified: List[ModifiedComponent] = []


class MissingComponent(CamelModel):
    kind: str
    name: str
    missingFrom: str  # base | enhancement
    presentIn: str  # enhancement | base
    file: Optional[str] = None


class IntegrationCandidate(CamelModel):
    order: int
    id: str
    kind: str
    name: str
    action: str  # add | merge
    risk: str  # low | medium | high
    reason: str
    sourceFile: Optional[str] = None
    dependsOn: List[str] = []  # "kind:name" items that should be integrated first
    conflicts: List[str] = []


class ComparisonResult(CamelModel):
    baseApplication: str
    enhancementApplication: str
    summary: Dict[str, int] = {}
    modules: CategoryComparison = CategoryComparison()
    routes: CategoryComparison = CategoryComparison()
    apis: CategoryComparison = CategoryComparison()
    services: CategoryComparison = CategoryComparison()
    entities: CategoryComparison = CategoryComparison()
    missingComponents: List[MissingComponent] = []
    integrationCandidates: List[IntegrationCandidate] = []
    warnings: List[str] = []


class CompareRequest(CamelModel):
    base: DiscoveryRequest
    enhancement: DiscoveryRequest
