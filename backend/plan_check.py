"""Offline check of ImplementationPlanningAgent.
Scenario 1 (React): base has a reports module; the enhancement adds a ReportDashboard page + route.
Scenario 2 (.NET, optional path arg): modified copy of a .NET app (new service/controller/view/entity,
retyped property). Usage: python plan_check.py [dotnet base repo path]"""
import shutil
import sys
import tempfile
from pathlib import Path

from app.agents.planning_agent import ImplementationPlanningAgent

agent = ImplementationPlanningAgent()


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ---- scenario 1: React -------------------------------------------------
root = Path(tempfile.mkdtemp())
PKG = '{"name": "portal", "dependencies": {"react": "^18", "react-router-dom": "^6"}}'
APP = ('import {Route, Routes} from "react-router-dom";\nexport default function App() { return (<Routes>\n'
       '  <Route path="/" element={<HomePage />} />\n  <Route path="/reports" element={<ReportList />} />\n'
       '  {EXTRA}</Routes>); }\n')
page = lambda n: f"export default function {n}() {{ return <div>{n}</div>; }}\n"
for r, extra, pages in (("base", "", {}), ("enh", '<Route path="/reports/dashboard" element={<ReportDashboard />} />\n',
                                           {"src/pages/reports/ReportDashboard.tsx": "ReportDashboard"})):
    write(root / r / "package.json", PKG)
    write(root / r / "src/App.tsx", APP.replace("{EXTRA}", extra))
    for f, n in {"src/pages/HomePage.tsx": "HomePage", "src/pages/reports/ReportList.tsx": "ReportList",
                 "src/pages/reports/ReportDetails.tsx": "ReportDetails", **pages}.items():
        write(root / r / f, page(n))
print("=" * 20, "REACT")
print(agent.analyze_and_plan(root / "base", root / "enh").planMarkdown)
shutil.rmtree(root, ignore_errors=True)

# ---- scenario 2: .NET ----------------------------------------------------
if len(sys.argv) > 1:
    base = Path(sys.argv[1]).resolve()
    tmp = Path(tempfile.mkdtemp()) / "ManufacturingPortalPlus"
    shutil.copytree(base, tmp, ignore=shutil.ignore_patterns(".git", "bin", "obj"))
    write(tmp / "Services/ReportService.cs",
          "namespace ManufacturingPortal.Services;\npublic interface IReportService { int Count(); }\n"
          "public class ReportService : IReportService { public int Count() => 1; }\n")
    write(tmp / "Controllers/ReportController.cs",
          "using ManufacturingPortal.Services;\nusing Microsoft.AspNetCore.Mvc;\nnamespace ManufacturingPortal.Controllers;\n"
          "public class ReportController : Controller\n{\n    private readonly IReportService _reports;\n"
          "    public ReportController(IReportService reports) { _reports = reports; }\n"
          "    public IActionResult Dashboard() => View();\n}\n")
    write(tmp / "Views/Report/Dashboard.cshtml", "<h1>Reports</h1>")
    write(tmp / "Models/Report.cs", "namespace ManufacturingPortal.Models;\npublic class Report\n{\n"
          "    public int Id { get; set; }\n    public string Title { get; set; } = \"\";\n}\n")
    prog = tmp / "Program.cs"
    prog.write_text(prog.read_text(encoding="utf-8").replace(
        "var app = builder.Build();",
        "builder.Services.AddSingleton<IReportService, ReportService>();\n\nvar app = builder.Build();"), encoding="utf-8")
    eq = tmp / "Models/Equipment.cs"
    eq.write_text(eq.read_text(encoding="utf-8").replace("public string Notes", "public int Notes"), encoding="utf-8")
    print("=" * 20, ".NET")
    print(agent.analyze_and_plan(base, tmp).planMarkdown)
    shutil.rmtree(tmp.parent, ignore_errors=True)
