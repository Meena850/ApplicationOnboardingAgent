import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, List

from app.models.discovery import (
    Action, Api, CodeItem, Controller, Dependency, DiscoveryResult,
    EntryPoint, Module, Page, Route,
)

logger = logging.getLogger(__name__)

SKIP_DIRS = {"node_modules", ".git", "bin", "obj", "dist", "build", "__pycache__",
             ".venv", "venv", "lib", ".vs", ".idea"}
HTTP_ATTRS = {"HttpGet": "GET", "HttpPost": "POST", "HttpPut": "PUT",
              "HttpDelete": "DELETE", "HttpPatch": "PATCH"}


def iter_files(root: Path, exts: tuple) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
        for f in filenames:
            if f.lower().endswith(exts):
                yield Path(dirpath) / f


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return ""


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def parts_lower(root: Path, path: Path) -> List[str]:
    return [p.lower() for p in path.relative_to(root).parts[:-1]]


def first_string(args: str | None) -> str | None:
    m = re.search(r'"([^"]*)"', args or "")
    return m.group(1) if m else None


class SourceAnalyzer(ABC):
    """Contributes findings to a DiscoveryResult for a repository root."""

    @abstractmethod
    def analyze(self, root: Path, result: DiscoveryResult) -> None: ...


# ---------------------------------------------------------------- React
class ReactAnalyzer(SourceAnalyzer):
    JSX_ROUTE = re.compile(
        r"<Route\b[^>]*?\bpath=[\"']([^\"']+)[\"'][^>]*?(?:element=\{\s*<(\w+)|component=\{\s*(\w+))")
    OBJ_ROUTE = re.compile(r"path:\s*[\"']([^\"']+)[\"'][^}]*?element:\s*<(\w+)", re.S)
    HOOK_DEF = re.compile(r"(?:function|const)\s+(use[A-Z]\w*)")
    FETCH = re.compile(r"fetch\(\s*[`\"']([^`\"']+)")
    AXIOS = re.compile(r"axios\.(get|post|put|delete|patch)\(\s*[`\"']([^`\"']+)", re.I)
    REQUEST = re.compile(r"\brequest(?:<[^>]*>)?\(\s*[`\"']([^`\"']+)[`\"'](?:\s*,\s*\{[^}]*?method:\s*[\"'](\w+)[\"'])?", re.S)

    def analyze(self, root: Path, result: DiscoveryResult) -> None:
        route_by_component = {}
        files = [f for f in iter_files(root, (".tsx", ".jsx", ".ts", ".js"))
                 if not re.search(r"\.(d|test|spec)\.|\.config\.", f.name)]
        seen_hooks = set()
        for f in files:
            text, rp, parts = read(f), rel(root, f), parts_lower(root, f)
            for m in self.JSX_ROUTE.finditer(text):
                comp = m.group(2) or m.group(3)
                result.routes.append(Route(path=m.group(1), component=comp, file=rp, source="react-router"))
                route_by_component[comp] = m.group(1)
            for m in self.OBJ_ROUTE.finditer(text):
                result.routes.append(Route(path=m.group(1), component=m.group(2), file=rp, source="react-router"))
                route_by_component[m.group(2)] = m.group(1)
            for m in self.HOOK_DEF.finditer(text):
                if (m.group(1), rp) not in seen_hooks:
                    seen_hooks.add((m.group(1), rp))
                    result.hooks.append(CodeItem(name=m.group(1), file=rp, platform="react"))
            for m in self.FETCH.finditer(text):
                result.apis.append(Api(method="GET", route=m.group(1), file=rp, kind="client-call"))
            for m in self.AXIOS.finditer(text):
                result.apis.append(Api(method=m.group(1).upper(), route=m.group(2), file=rp, kind="client-call"))
            for m in self.REQUEST.finditer(text):
                result.apis.append(Api(method=(m.group(2) or "GET").upper(), route=m.group(1), file=rp, kind="client-call"))
            if f.suffix in (".tsx", ".jsx"):
                if "pages" in parts:
                    result.pages.append(Page(name=f.stem, type="react", file=rp))
                elif "components" in parts:
                    result.components.append(CodeItem(name=f.stem, file=rp, platform="react"))
            if "services" in parts and f.stem != "index":
                result.services.append(CodeItem(name=f.stem, file=rp, platform="react"))
        for p in result.pages:
            if p.type == "react" and p.name in route_by_component:
                p.route = route_by_component[p.name]


# ---------------------------------------------------------------- .NET
class DotNetAnalyzer(SourceAnalyzer):
    ATTR = re.compile(r"\[\s*(\w+)(?:\(([^)]*)\))?\s*[,\]]")
    CLASS = re.compile(r"\bclass\s+(\w+)(?:\s*:\s*([\w<>., ]+))?")
    METHOD = re.compile(r"^\s*public\s+(?:virtual\s+|override\s+)?(?:async\s+)?([\w<>\[\],.? ]+?)\s+(\w+)\s*\(")
    MIN_API = re.compile(r"\.Map(Get|Post|Put|Delete|Patch)\(\s*\"([^\"]*)\"")
    REGISTER = re.compile(r"\.Add(?:Scoped|Singleton|Transient|HostedService)<\s*([\w<>.]+)(?:\s*,\s*([\w<>.]+))?\s*>")
    MIDDLEWARE = re.compile(r"\bapp\.(Use\w+|Map\w+)\(")

    def analyze(self, root: Path, result: DiscoveryResult) -> None:
        for f in iter_files(root, (".cs",)):
            text, rp, parts = read(f), rel(root, f), parts_lower(root, f)
            if f.name == "Program.cs":
                self._program(text, rp, result)
            self._classes(text, rp, parts, result)

    def _program(self, text: str, rp: str, result: DiscoveryResult) -> None:
        regs = [m.group(2) or m.group(1) for m in self.REGISTER.finditer(text)]
        mw = list(dict.fromkeys(m.group(1) for m in self.MIDDLEWARE.finditer(text)))
        result.entryPoints.append(EntryPoint(file=rp, registeredServices=regs, middleware=mw))
        for m in self.MIN_API.finditer(text):
            result.apis.append(Api(method=m.group(1).upper(), route=m.group(2), file=rp, kind="endpoint"))
            result.routes.append(Route(path=m.group(2), method=m.group(1).upper(), file=rp, source="minimal-api"))
        for m in re.finditer(r"pattern:\s*\"([^\"]+)\"", text):
            result.routes.append(Route(path="/" + m.group(1), file=rp, source="aspnet-mvc"))

    def _classes(self, text: str, rp: str, parts: List[str], result: DiscoveryResult) -> None:
        pending: List[tuple] = []
        ctrl: Controller | None = None
        ctrl_prefix = ""
        has_route_attr = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("["):
                pending += [(m.group(1), m.group(2)) for m in self.ATTR.finditer(s)]
                continue
            if not s or s.startswith("//") or s.startswith("///"):
                continue
            cm = self.CLASS.search(s)
            if cm and re.match(r"^(?:public |internal |abstract |sealed |static |partial )*class\b", s):
                name, base = cm.group(1), (cm.group(2) or "")
                attrs = dict(pending)
                if name.endswith("Controller"):
                    is_api = "ApiController" in attrs or "ControllerBase" in base
                    tmpl = first_string(attrs.get("Route")) if "Route" in attrs else None
                    has_route_attr = tmpl is not None
                    short = name[: -len("Controller")]
                    ctrl_prefix = (tmpl or "").replace("[controller]", short.lower())
                    ctrl = Controller(name=name, route="/" + ctrl_prefix.strip("/") if tmpl else f"/{short}",
                                      isApi=is_api, file=rp)
                    result.controllers.append(ctrl)
                else:
                    ctrl = None
                    low = name.lower()
                    if "repositor" in low or "repositories" in parts:
                        result.repositories.append(CodeItem(name=name, file=rp, platform="dotnet"))
                    elif low.endswith("service") or "services" in parts:
                        result.services.append(CodeItem(name=name, file=rp, platform="dotnet"))
                pending = []
                continue
            mm = self.METHOD.match(line)
            if mm and ctrl is not None:
                self._action(ctrl, mm.group(2), pending, ctrl_prefix, has_route_attr, rp, result)
            pending = []

    def _action(self, ctrl: Controller, name: str, attrs: List[tuple], prefix: str,
                has_route_attr: bool, rp: str, result: DiscoveryResult) -> None:
        short = ctrl.name[: -len("Controller")]
        d = dict(attrs)
        if "NonAction" in d:
            return
        verb = next((HTTP_ATTRS[a] for a, _ in attrs if a in HTTP_ATTRS), None)
        tmpl = None
        for a, args in attrs:
            if a in HTTP_ATTRS or a == "Route":
                tmpl = first_string(args) or tmpl
        if verb or tmpl is not None or has_route_attr:
            tmpl = (tmpl or "").replace("[action]", name.lower()).replace("[controller]", short.lower())
            if tmpl.startswith(("/", "~/")):
                route = "/" + tmpl.lstrip("~/").strip("/")
            else:
                route = "/" + "/".join(p for p in (prefix.strip("/"), tmpl.strip("/")) if p)
            src = "aspnet-attribute"
        else:
            route = "/" if (short, name) == ("Home", "Index") else f"/{short}/{name}"
            src = "aspnet-mvc"
        method = verb or "GET"
        ctrl.actions.append(Action(name=name, httpMethod=verb, route=route))
        result.routes.append(Route(path=route, method=method, component=f"{ctrl.name}.{name}", file=rp, source=src))
        if ctrl.isApi or src == "aspnet-attribute":
            result.apis.append(Api(method=method, route=route, controller=ctrl.name,
                                   action=name, file=rp, kind="endpoint"))


# ---------------------------------------------------------------- Razor
class RazorAnalyzer(SourceAnalyzer):
    PAGE = re.compile(r"^\s*@page(?:\s+\"([^\"]*)\")?", re.M)

    def analyze(self, root: Path, result: DiscoveryResult) -> None:
        for f in iter_files(root, (".cshtml", ".razor")):
            rp, parts = rel(root, f), parts_lower(root, f)
            text = read(f)
            stem = f.stem
            if stem.lower().startswith("_layout") or "layout" in stem.lower() and "shared" in parts:
                result.layouts.append(CodeItem(name=stem, file=rp, platform="razor"))
            elif stem.startswith("_"):
                continue  # _ViewStart / _ViewImports / partials
            elif "views" in parts:
                result.views.append(CodeItem(name=f"{'/'.join(Path(rp).parts[1:-1])}/{stem}".lstrip("/"),
                                             file=rp, platform="razor"))
            elif self.PAGE.search(text) or "pages" in parts:
                m = self.PAGE.search(text)
                segs = [p for p in Path(rp).with_suffix("").parts]
                if segs and segs[0].lower() == "pages":
                    segs = segs[1:]
                if segs and segs[-1].lower() == "index":
                    segs = segs[:-1]
                route = ("/" + m.group(1).lstrip("/")) if m and m.group(1) else "/" + "/".join(segs)
                result.pages.append(Page(name=stem, type="razor-page", route=route, file=rp))
                result.routes.append(Route(path=route, component=stem, file=rp, source="razor-page"))


# ---------------------------------------------------------------- Deps / modules
class ProjectAnalyzer(SourceAnalyzer):
    def analyze(self, root: Path, result: DiscoveryResult) -> None:
        for f in iter_files(root, (".csproj",)):
            rp = rel(root, f)
            result.modules.append(Module(name=f.stem, type="dotnet", path=rp))
            self._csproj(f, rp, result)
        for f in iter_files(root, ("package.json",)):
            if f.name != "package.json":
                continue
            rp = rel(root, f)
            try:
                data = json.loads(read(f) or "{}")
            except json.JSONDecodeError:
                result.warnings.append(f"Invalid JSON: {rp}")
                continue
            result.modules.append(Module(name=data.get("name") or f.parent.name, type="react", path=rp))
            for scope, key in (("runtime", "dependencies"), ("dev", "devDependencies")):
                for n, v in (data.get(key) or {}).items():
                    result.dependencies.append(Dependency(name=n, version=v, ecosystem="npm", scope=scope, file=rp))
        for d in ("Areas", "areas"):
            area = root / d
            if area.is_dir():
                for sub in sorted(p for p in area.iterdir() if p.is_dir()):
                    result.modules.append(Module(name=sub.name, type="area", path=rel(root, sub)))

    @staticmethod
    def _csproj(f: Path, rp: str, result: DiscoveryResult) -> None:
        try:
            tree = ET.parse(f)
        except ET.ParseError:
            result.warnings.append(f"Invalid XML: {rp}")
            return
        for el in tree.iter():
            tag = el.tag.split("}")[-1]
            if tag == "PackageReference":
                result.dependencies.append(Dependency(
                    name=el.get("Include", ""), version=el.get("Version"), ecosystem="nuget", file=rp))
            elif tag == "ProjectReference":
                inc = el.get("Include", "").replace("\\", "/")
                result.dependencies.append(Dependency(
                    name=Path(inc).stem, ecosystem="project", file=rp))
