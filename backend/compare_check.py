"""Offline check of RepositoryComparisonAgent. Builds a modified copy of a .NET app as the
"enhancement" (new service/controller/view/entity, an added property and a changed property type).
Usage: python compare_check.py <base repo path>"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from app.agents.comparison_agent import RepositoryComparisonAgent

base = Path(sys.argv[1]).resolve()
tmp = Path(tempfile.mkdtemp()) / "ManufacturingPortalPlus"
shutil.copytree(base, tmp, ignore=shutil.ignore_patterns(".git", "bin", "obj"))

(tmp / "Services" / "ReportService.cs").write_text(
    "namespace ManufacturingPortal.Services;\n"
    "public interface IReportService { int Count(); }\n"
    "public class ReportService : IReportService { public int Count() => 1; }\n", encoding="utf-8")
(tmp / "Controllers" / "ReportController.cs").write_text(
    "using ManufacturingPortal.Services;\nusing Microsoft.AspNetCore.Mvc;\n"
    "namespace ManufacturingPortal.Controllers;\n"
    "public class ReportController : Controller\n{\n"
    "    private readonly IReportService _reports;\n"
    "    public ReportController(IReportService reports) { _reports = reports; }\n"
    "    public IActionResult Dashboard() => View();\n}\n", encoding="utf-8")
(tmp / "Views" / "Report").mkdir()
(tmp / "Views" / "Report" / "Dashboard.cshtml").write_text("<h1>Reports</h1>", encoding="utf-8")
(tmp / "Models" / "Report.cs").write_text(
    "namespace ManufacturingPortal.Models;\npublic class Report\n{\n"
    "    public int Id { get; set; }\n    public string Title { get; set; } = \"\";\n}\n", encoding="utf-8")
prog = tmp / "Program.cs"
prog.write_text(prog.read_text(encoding="utf-8").replace(
    "var app = builder.Build();",
    "builder.Services.AddSingleton<IReportService, ReportService>();\n\nvar app = builder.Build();"), encoding="utf-8")
eq = tmp / "Models" / "Equipment.cs"
eq.write_text(eq.read_text(encoding="utf-8")
              .replace("public string Notes", "public int Notes")
              .replace("public int Id { get; set; }", "public int Id { get; set; }\n    public string Location { get; set; } = \"\";"),
              encoding="utf-8")

agent = RepositoryComparisonAgent()
same = agent.run(base, base)
print("IDENTICAL: candidates", len(same.integrationCandidates), "missing", len(same.missingComponents))
r = agent.run(base, tmp).model_dump(by_alias=True)
print("SUMMARY", json.dumps({k: v for k, v in r["summary"].items() if v and "Common" not in k and "Base" not in k.replace("MissingInBase", "")}))
print("MISSING", [(m["kind"], m["name"], m["missingFrom"]) for m in r["missingComponents"]])
for c in r["integrationCandidates"]:
    print(c["id"], c["kind"], c["name"], c["action"], c["risk"], c["dependsOn"], "|", c["reason"][:130])
shutil.rmtree(tmp.parent, ignore_errors=True)
