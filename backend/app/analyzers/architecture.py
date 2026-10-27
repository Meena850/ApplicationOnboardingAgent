"""Deterministic architecture map builders (no AI): regex/XML/JSON parsing only."""
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.analyzers.discovery import iter_files, read, rel
from app.models.architecture import (
    ApiClientCall, ApiEndpoint, ApiMap, DependencyEdge, DependencyMap, ModuleEdge,
    ModuleMap, ModuleNode, PackageRef, Registration, RouteEntry, RouteMap,
)
from app.models.discovery import DiscoveryResult, Module

CODE_EXTS = (".cs", ".cshtml", ".razor", ".ts", ".tsx", ".js", ".jsx")
JS_EXTS = (".ts", ".tsx", ".js", ".jsx")


# ------------------------------------------------------------ module lookup
def _module_dir(m: Module) -> str:
    if m.type == "area":
        return m.path
    p = Path(m.path).parent.as_posix()
    return "" if p == "." else p


class ModuleIndex:
    def __init__(self, modules: List[Module]) -> None:
        self.modules = modules
        self._ordered = sorted(modules, key=lambda m: len(_module_dir(m)), reverse=True)

    def of(self, file: str) -> Optional[str]:
        for m in self._ordered:
            d = _module_dir(m)
            if d == "" or file == d or file.startswith(d + "/"):
                return m.name
        return None


# ------------------------------------------------------------ module map
def build_module_map(root: Path, d: DiscoveryResult, idx: ModuleIndex, api: ApiMap) -> ModuleMap:
    layer_sources = {
        "controllers": d.controllers, "services": d.services, "repositories": d.repositories,
        "pages": d.pages, "components": d.components, "hooks": d.hooks,
        "views": d.views, "layouts": d.layouts,
    }
    nodes: Dict[str, ModuleNode] = {
        m.name: ModuleNode(name=m.name, type=m.type, path=m.path) for m in d.modules
    }
    for layer, items in layer_sources.items():
        for it in items:
            mod = idx.of(it.file)
            if mod in nodes:
                nodes[mod].layers.setdefault(layer, []).append(it.name)
    for f in iter_files(root, CODE_EXTS):
        mod = idx.of(rel(root, f))
        if mod in nodes:
            nodes[mod].fileCount += 1

    edges: List[ModuleEdge] = []
    names = set(nodes)
    for dep in d.dependencies:
        if dep.ecosystem == "project" and dep.name in names:
            src = idx.of(dep.file)
            if src and src != dep.name:
                edges.append(ModuleEdge(source=src, target=dep.name, kind="project-reference"))
    seen = set()
    for call in api.clientCalls:
        if call.matchedEndpoint and call.module:
            ep = next((e for e in api.endpoints
                       if f"{e.method} {e.route}" == call.matchedEndpoint), None)
            if ep and ep.module and ep.module != call.module and (call.module, ep.module) not in seen:
                seen.add((call.module, ep.module))
                edges.append(ModuleEdge(source=call.module, target=ep.module, kind="calls-api"))
    return ModuleMap(nodes=list(nodes.values()), edges=edges)


# ------------------------------------------------------------ route map
def build_route_map(d: DiscoveryResult, idx: ModuleIndex) -> RouteMap:
    views = {v.file.lower(): v.file for v in d.views}
    entries: List[RouteEntry] = []
    for r in d.routes:
        view = None
        if r.source == "aspnet-mvc" and r.component and "." in r.component:
            ctrl, action = r.component.split(".", 1)
            short = ctrl[: -len("Controller")] if ctrl.endswith("Controller") else ctrl
            view = next((orig for low, orig in views.items()
                         if low.endswith(f"views/{short.lower()}/{action.lower()}.cshtml")), None)
        elif r.source == "razor-page":
            view = r.file
        entries.append(RouteEntry(path=r.path, method=r.method, source=r.source, handler=r.component,
                                  view=view, module=idx.of(r.file), file=r.file))
    entries.sort(key=lambda e: (e.source, e.path))
    counts: Dict[str, int] = {}
    for e in entries:
        counts[e.source] = counts.get(e.source, 0) + 1
    return RouteMap(routes=entries, countBySource=counts)


# ------------------------------------------------------------ api map
def _norm(route: str) -> str:
    r = route.split("?")[0].lower()
    r = re.sub(r"\$\{[^}]*\}", "{}", r)
    r = re.sub(r"\{[^}]*\}", "{}", r)
    r = re.sub(r"/:[\w]+", "/{}", r)
    r = re.sub(r"(https?://[^/]+)", "", r)
    return "/" + r.strip("/")


def _matches(client: str, server: str) -> bool:
    c, s = _norm(client), _norm(server)
    if c.replace("{}", "").strip("/") == "":
        return False  # nothing literal to compare (e.g. a bare ${BASE}${path})
    return s == c or s.endswith(c) or c.endswith(s) and s != "/"


def build_api_map(d: DiscoveryResult, idx: ModuleIndex) -> ApiMap:
    endpoints = [ApiEndpoint(method=a.method, route=a.route, controller=a.controller, action=a.action,
                             module=idx.of(a.file), file=a.file)
                 for a in d.apis if a.kind == "endpoint"]
    calls: List[ApiClientCall] = []
    used = set()
    for a in d.apis:
        if a.kind != "client-call":
            continue
        matched = next((e for e in endpoints if _matches(a.route, e.route)
                        and (e.method == a.method or a.method == "GET")), None)
        key = f"{matched.method} {matched.route}" if matched else None
        if key:
            used.add(key)
        calls.append(ApiClientCall(method=a.method, route=a.route, module=idx.of(a.file),
                                   file=a.file, matchedEndpoint=key))
    unused = [f"{e.method} {e.route}" for e in endpoints if f"{e.method} {e.route}" not in used]
    return ApiMap(endpoints=endpoints, clientCalls=calls,
                  unmatchedClientCalls=sum(1 for c in calls if not c.matchedEndpoint),
                  endpointsWithoutClient=unused if calls else [])


# ------------------------------------------------------------ dependency map
REGISTER = re.compile(r"\.Add(Scoped|Singleton|Transient)<\s*([\w.]+)(?:\s*,\s*([\w.]+))?\s*>")
TYPE_DECL = re.compile(r"\b(?:class|interface|record|struct)\s+(\w+)")
IMPORT = re.compile(r"""(?:import|export)\s+(?:[^'"]*?\s+from\s+)?["']([^"']+)["']""")
REQUIRE = re.compile(r"""require\(\s*["']([^"']+)["']\s*\)""")


def _split_params(s: str) -> List[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _param_type(p: str) -> Optional[str]:
    p = re.sub(r"\[[^\]]*\]", "", p).split("=")[0].strip()
    m = re.match(r"^(?:this\s+|params\s+|in\s+|ref\s+)?([\w.<>?,\[\] ]+?)\s+\w+$", p)
    if not m:
        return None
    t = m.group(1).strip().rstrip("?")
    inner = re.match(r"^\w+<([\w.]+)>$", t)  # ILogger<X> -> keep outer only
    t = t.split("<")[0] if inner else t
    return t.split(".")[-1]


def _dotnet_graph(root: Path, idx: ModuleIndex) -> Tuple[List[Registration], List[DependencyEdge]]:
    files = [(f, read(f)) for f in iter_files(root, (".cs",))]
    declared = {m.group(1) for _, t in files for m in TYPE_DECL.finditer(t)}
    regs: List[Registration] = []
    for f, text in files:
        for m in REGISTER.finditer(text):
            svc = m.group(2).split(".")[-1]
            impl = (m.group(3) or m.group(2)).split(".")[-1]
            regs.append(Registration(service=svc, implementation=impl, lifetime=m.group(1), file=rel(root, f)))
    impl_of = {r.service: r.implementation for r in regs}
    edges: List[DependencyEdge] = []
    for f, text in files:
        for cm in re.finditer(r"\bclass\s+(\w+)", text):
            cls = cm.group(1)
            ctor = re.search(rf"\bpublic\s+{re.escape(cls)}\s*\(([^)]*)\)", text)
            if not ctor:
                continue
            for p in _split_params(ctor.group(1)):
                t = _param_type(p)
                if not t or t not in declared:
                    continue
                if t in impl_of and impl_of[t] != t:
                    edges.append(DependencyEdge(source=cls, target=impl_of[t], kind="injects", via=t))
                else:
                    edges.append(DependencyEdge(source=cls, target=t, kind="injects"))
    return regs, edges


def _resolve_import(root: Path, src: Path, spec: str) -> Optional[str]:
    base = (src.parent / spec).resolve()
    candidates = [base] + [base.with_name(base.name + e) for e in JS_EXTS] + [base / f"index{e}" for e in JS_EXTS]
    for c in candidates:
        if c.is_file():
            try:
                return c.relative_to(root.resolve()).as_posix()
            except ValueError:
                return None
    return None


def _js_graph(root: Path) -> Tuple[List[DependencyEdge], Dict[str, int]]:
    edges: List[DependencyEdge] = []
    usage: Dict[str, int] = {}
    for f in iter_files(root, JS_EXTS):
        if re.search(r"\.(d|test|spec)\.", f.name):
            continue
        text = read(f)
        specs = {m.group(1) for m in IMPORT.finditer(text)} | {m.group(1) for m in REQUIRE.finditer(text)}
        for spec in sorted(specs):
            if spec.startswith("."):
                target = _resolve_import(root, f, spec)
                if target:
                    edges.append(DependencyEdge(source=rel(root, f), target=target, kind="imports"))
            else:
                parts = spec.split("/")
                pkg = "/".join(parts[:2]) if spec.startswith("@") else parts[0]
                usage[pkg] = usage.get(pkg, 0) + 1
    return edges, dict(sorted(usage.items()))


def build_dependency_map(root: Path, d: DiscoveryResult, idx: ModuleIndex) -> DependencyMap:
    packages = [PackageRef(name=p.name, version=p.version, ecosystem=p.ecosystem, scope=p.scope,
                           module=idx.of(p.file))
                for p in d.dependencies if p.ecosystem != "project"]
    regs, net_edges = _dotnet_graph(root, idx)
    js_edges, usage = _js_graph(root)
    regs = list({(r.service, r.implementation, r.lifetime): r for r in regs}.values())
    edges = list({(e.source, e.target, e.kind, e.via): e for e in net_edges + js_edges}.values())
    return DependencyMap(packages=packages, registrations=regs, internal=edges,
                         packageUsage=usage)
