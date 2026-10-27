"""Generates Mermaid diagrams (module, dependency, API flow) from an ArchitectureResult."""
import re
from pathlib import Path
from typing import Dict, List

from app.agents.architecture_agent import ArchitectureAnalysisAgent
from app.models.architecture import ArchitectureResult
from app.models.diagram import DiagramsResult

MAX_EDGES = 120
MAX_API = 60


class _Ids:
    """Stable, Mermaid-safe node ids for arbitrary labels."""

    def __init__(self, prefix: str = "n"):
        self.prefix, self.map = prefix, {}

    def __call__(self, key: str) -> str:
        if key not in self.map:
            self.map[key] = f"{self.prefix}{len(self.map) + 1}"
        return self.map[key]


def _q(text: object) -> str:
    """Quote a label for Mermaid."""
    s = re.sub(r'["\r\n]+', " ", str(text)).strip()
    return f'"{s}"'


class DiagramAgent:
    def run(self, root: Path) -> DiagramsResult:
        return self.from_architecture(ArchitectureAnalysisAgent().run(root))

    def from_architecture(self, a: ArchitectureResult) -> DiagramsResult:
        warnings: List[str] = []
        return DiagramsResult(
            applicationName=a.applicationName,
            moduleDiagram=self._module(a, warnings),
            dependencyDiagram=self._dependency(a, warnings),
            apiFlowDiagram=self._api_flow(a, warnings),
            warnings=warnings + list(a.warnings),
        )

    # ------------------------------------------------------------------ module
    def _module(self, a: ArchitectureResult, warnings: List[str]) -> str:
        nodes = a.moduleMap.nodes
        if not nodes:
            warnings.append("No modules found; module diagram is empty.")
            return 'flowchart LR\n  empty["No modules detected"]'
        ids = _Ids("m")
        lines = ["flowchart LR"]
        for n in nodes:
            nid = ids(n.name)
            layers = ", ".join(f"{k}: {len(v)}" for k, v in n.layers.items() if v)
            label = f"{n.name}<br/>{n.type} · {n.fileCount} files" + (f"<br/>{layers}" if layers else "")
            lines.append(f"  {nid}[{_q(label)}]")
        for e in a.moduleMap.edges:
            if e.source in ids.map and e.target in ids.map:
                lines.append(f"  {ids(e.source)} -->|{e.kind}| {ids(e.target)}")
        return "\n".join(lines)

    # -------------------------------------------------------------- dependency
    def _dependency(self, a: ArchitectureResult, warnings: List[str]) -> str:
        d = a.dependencyMap
        edges = d.internal
        if not edges and not d.registrations:
            warnings.append("No internal dependencies found; dependency diagram is empty.")
            return 'flowchart LR\n  empty["No dependencies detected"]'
        if len(edges) > MAX_EDGES:
            warnings.append(f"Dependency diagram truncated to {MAX_EDGES} of {len(edges)} edges.")
        ids = _Ids("d")
        lines = ["flowchart LR"]
        body: List[str] = []
        seen = set()
        for e in edges[:MAX_EDGES]:
            key = (e.source, e.target, e.kind)
            if key in seen:
                continue
            seen.add(key)
            arrow = "-->" if e.kind == "injects" else "-.->"
            body.append(f"  {ids(e.source)}[{_q(e.source)}] {arrow}|{e.kind}| {ids(e.target)}[{_q(e.target)}]")
        for r in d.registrations:
            if r.service in ids.map or r.implementation in ids.map:
                body.append(
                    f"  {ids(r.service)}[{_q(r.service)}] ==>|{r.lifetime}| {ids(r.implementation)}[{_q(r.implementation)}]")
        lines += body
        top = sorted(d.packageUsage.items(), key=lambda kv: -kv[1])[:8]
        if top:
            lines.append('  subgraph pkgs["Top packages"]')
            for name, count in top:
                lines.append(f"    {ids('pkg:' + name)}[{_q(f'{name} ({count})')}]")
            lines.append("  end")
        return "\n".join(lines)

    # ---------------------------------------------------------------- API flow
    def _route_flow(self, a: ArchitectureResult) -> str:
        """Fallback for apps without API endpoints: route -> handler -> services / view."""
        ids = _Ids("r")
        services_of: Dict[str, List[str]] = {}
        for e in a.dependencyMap.internal:
            if e.kind == "injects":
                services_of.setdefault(e.source, []).append(e.target)
        lines = ["flowchart LR"]
        for r in a.routeMap.routes[:MAX_API]:
            label = f"{r.method + ' ' if r.method else ''}{r.path}"
            route = ids("route:" + label)
            lines.append(f"  {route}{{{{{_q(label)}}}}}")
            if r.handler:
                h = ids("h:" + r.handler)
                lines.append(f"  {h}[{_q(r.handler)}]")
                lines.append(f"  {route} --> {h}")
                ctl = r.handler.split(".")[0].split("/")[0]
                for svc in sorted(set(services_of.get(ctl, []))):
                    s = ids("svc:" + svc)
                    lines.append(f"  {s}[({_q(svc)})]")
                    lines.append(f"  {h} --> {s}")
                if r.view:
                    v = ids("v:" + r.view)
                    lines.append(f"  {v}([{_q(r.view)}])")
                    lines.append(f"  {h} --> {v}")
        out, seen = [lines[0]], set()
        for ln in lines[1:]:
            if ln not in seen:
                seen.add(ln)
                out.append(ln)
        return "\n".join(out)

    def _api_flow(self, a: ArchitectureResult, warnings: List[str]) -> str:
        eps = a.apiMap.endpoints
        calls = a.apiMap.clientCalls
        if not eps and not calls:
            if a.routeMap.routes:
                return self._route_flow(a)
            warnings.append("No API endpoints or client calls found; API flow diagram is empty.")
            return 'flowchart LR\n  empty["No APIs detected"]'
        if len(eps) > MAX_API:
            warnings.append(f"API flow diagram truncated to {MAX_API} of {len(eps)} endpoints.")
        ids = _Ids("a")
        by_controller: Dict[str, List[str]] = {}
        services_of: Dict[str, List[str]] = {}
        for e in a.dependencyMap.internal:
            if e.kind == "injects":
                services_of.setdefault(e.source, []).append(e.target)

        lines = ["flowchart LR"]
        edge_lines: List[str] = []
        shown = eps[:MAX_API]
        shown_keys = {f"{e.method} {e.route}" for e in shown}
        for e in shown:
            key = f"{e.method} {e.route}"
            ep = ids("ep:" + key)
            lines.append(f"  {ep}{{{{{_q(key)}}}}}")
            if e.controller:
                ctl = ids("ctl:" + e.controller)
                by_controller.setdefault(e.controller, [])
                label = f"{e.controller}.{e.action}" if e.action else e.controller
                act = ids("act:" + label)
                lines.append(f"  {act}[{_q(label)}]")
                edge_lines.append(f"  {ep} --> {act}")
                if act not in by_controller[e.controller]:
                    by_controller[e.controller].append(act)
        for ctl, acts in by_controller.items():
            for svc in sorted(set(services_of.get(ctl, []))):
                sid = ids("svc:" + svc)
                lines.append(f"  {sid}[({_q(svc)})]")
                edge_lines.append(f"  {acts[0]} --> {sid}")
        for c in calls:
            if c.matchedEndpoint and c.matchedEndpoint not in shown_keys:
                continue
            src = ids("call:" + c.file)
            lines.append(f"  {src}[{_q(Path(c.file).name)}]")
            if c.matchedEndpoint:
                edge_lines.append(f"  {src} -->|{c.method}| {ids('ep:' + c.matchedEndpoint)}")
            else:
                miss = ids("miss:" + f"{c.method} {c.route}")
                lines.append(f"  {miss}{{{{{_q(f'{c.method} {c.route} (unmatched)')}}}}}")
                edge_lines.append(f"  {src} -.->|{c.method}| {miss}")
        # de-duplicate node declarations and edges, keep order
        out, seen = [lines[0]], set()
        for ln in lines[1:] + edge_lines:
            if ln not in seen:
                seen.add(ln)
                out.append(ln)
        return "\n".join(out)
