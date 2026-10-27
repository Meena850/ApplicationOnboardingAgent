"""Offline check of IntegrationRecommendationAgent: builds a modified copy of a .NET app as the
enhancement (new service/controller/view/entity, added + retyped property). Usage: python recommend_check.py <base>"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from app.agents.recommendation_agent import IntegrationRecommendationAgent

base = Path(sys.argv[1]).resolve()
tmp = Path(tempfile.mkdtemp()) / "ManufacturingPortalPlus"
shutil.copytree(base, tmp, ignore=shutil.ignore_patterns(".git", "bin", "obj"))
(tmp / "Services" / "ReportService.cs").write_text(
    "namespace ManufacturingPortal.Services;\npublic interface IReportService { int Count(); }\n"
    "public class ReportService : IReportService { public int Count() => 1; }\n", encoding="utf-8")
(tmp / "Controllers" / "ReportController.cs").write_text(
    "using ManufacturingPortal.Services;\nusing Microsoft.AspNetCore.Mvc;\nnamespace ManufacturingPortal.Controllers;\n"
    "public class ReportController : Controller\n{\n    private readonly IReportService _reports;\n"
    "    public ReportController(IReportService reports) { _reports = reports; }\n"
    "    public IActionResult Dashboard() => View();\n}\n", encoding="utf-8")
(tmp / "Views" / "Report").mkdir()
(tmp / "Views" / "Report" / "Dashboard.cshtml").write_text("<h1>Reports</h1>", encoding="utf-8")
(tmp / "Models" / "Report.cs").write_text(
    "namespace ManufacturingPortal.Models;\npublic class Report\n{\n    public int Id { get; set; }\n"
    "    public string Title { get; set; } = \"\";\n}\n", encoding="utf-8")
prog = tmp / "Program.cs"
prog.write_text(prog.read_text(encoding="utf-8").replace(
    "var app = builder.Build();",
    "builder.Services.AddSingleton<IReportService, ReportService>();\n\nvar app = builder.Build();"), encoding="utf-8")
eq = tmp / "Models" / "Equipment.cs"
eq.write_text(eq.read_text(encoding="utf-8").replace("public string Notes", "public int Notes")
              .replace("public int Id { get; set; }", "public int Id { get; set; }\n    public string Location { get; set; } = \"\";"),
              encoding="utf-8")

agent = IntegrationRecommendationAgent()
print("IDENTICAL:", agent.analyze_and_recommend(base, base).model_dump(by_alias=True)["warnings"])
res = agent.analyze_and_recommend(base, tmp)
print(json.dumps(res.model_dump(by_alias=True), indent=1))
shutil.rmtree(tmp.parent, ignore_errors=True)
