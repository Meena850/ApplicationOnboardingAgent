from typing import Dict, List, Optional

from app.models.discovery import CamelModel


class ModuleNode(CamelModel):
    name: str
    type: str  # dotnet | react | area
    path: str
    fileCount: int = 0
    layers: Dict[str, List[str]] = {}


class ModuleEdge(CamelModel):
    source: str
    target: str
    kind: str  # project-reference | calls-api


class ModuleMap(CamelModel):
    nodes: List[ModuleNode] = []
    edges: List[ModuleEdge] = []


class RouteEntry(CamelModel):
    path: str
    method: Optional[str] = None
    source: str
    handler: Optional[str] = None
    view: Optional[str] = None
    module: Optional[str] = None
    file: str


class RouteMap(CamelModel):
    routes: List[RouteEntry] = []
    countBySource: Dict[str, int] = {}


class ApiEndpoint(CamelModel):
    method: str
    route: str
    controller: Optional[str] = None
    action: Optional[str] = None
    module: Optional[str] = None
    file: str


class ApiClientCall(CamelModel):
    method: str
    route: str
    module: Optional[str] = None
    file: str
    matchedEndpoint: Optional[str] = None  # "METHOD /route" or None


class ApiMap(CamelModel):
    endpoints: List[ApiEndpoint] = []
    clientCalls: List[ApiClientCall] = []
    unmatchedClientCalls: int = 0
    endpointsWithoutClient: List[str] = []


class PackageRef(CamelModel):
    name: str
    version: Optional[str] = None
    ecosystem: str
    scope: str = "runtime"
    module: Optional[str] = None


class Registration(CamelModel):
    service: str
    implementation: str
    lifetime: str
    file: str


class DependencyEdge(CamelModel):
    source: str
    target: str
    kind: str  # injects | imports
    via: Optional[str] = None  # interface the edge was resolved through


class DependencyMap(CamelModel):
    packages: List[PackageRef] = []
    registrations: List[Registration] = []
    internal: List[DependencyEdge] = []
    packageUsage: Dict[str, int] = {}  # npm package -> number of importing files


class ArchitectureResult(CamelModel):
    applicationName: str
    repositoryPath: str
    summary: Dict[str, int] = {}
    moduleMap: ModuleMap = ModuleMap()
    routeMap: RouteMap = RouteMap()
    apiMap: ApiMap = ApiMap()
    dependencyMap: DependencyMap = DependencyMap()
    warnings: List[str] = []
