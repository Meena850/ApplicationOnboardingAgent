from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Module(CamelModel):
    name: str
    type: str  # dotnet | react | area
    path: str


class Route(CamelModel):
    path: str
    method: Optional[str] = None
    component: Optional[str] = None
    file: str
    source: str  # react-router | aspnet-mvc | aspnet-attribute | minimal-api | razor-page


class Api(CamelModel):
    method: str
    route: str
    controller: Optional[str] = None
    action: Optional[str] = None
    file: str
    kind: str  # endpoint | client-call


class Page(CamelModel):
    name: str
    type: str  # react | razor-page
    route: Optional[str] = None
    file: str


class Action(CamelModel):
    name: str
    httpMethod: Optional[str] = None
    route: str


class Controller(CamelModel):
    name: str
    route: str
    isApi: bool
    actions: List[Action] = []
    file: str


class CodeItem(CamelModel):
    name: str
    file: str
    platform: str  # react | dotnet | razor


class Dependency(CamelModel):
    name: str
    version: Optional[str] = None
    ecosystem: str  # npm | nuget | project
    scope: str = "runtime"
    file: str


class EntryPoint(CamelModel):
    file: str
    registeredServices: List[str] = []
    middleware: List[str] = []


class DiscoveryResult(CamelModel):
    applicationName: str
    modules: List[Module] = []
    routes: List[Route] = []
    apis: List[Api] = []
    dependencies: List[Dependency] = []
    pages: List[Page] = []
    controllers: List[Controller] = []
    services: List[CodeItem] = []
    repositories: List[CodeItem] = []
    components: List[CodeItem] = []
    hooks: List[CodeItem] = []
    views: List[CodeItem] = []
    layouts: List[CodeItem] = []
    entryPoints: List[EntryPoint] = []
    warnings: List[str] = []


class DiscoveryRequest(BaseModel):
    path: Optional[str] = Field(None, description="Local directory to scan")
    repositoryId: Optional[str] = Field(None, description="Id of an ingested repository")
