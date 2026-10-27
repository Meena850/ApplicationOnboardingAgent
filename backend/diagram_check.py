import sys

from app.agents.diagram_agent import DiagramAgent

r = DiagramAgent().run(__import__("pathlib").Path(sys.argv[1]))
for t in ("moduleDiagram", "dependencyDiagram", "apiFlowDiagram"):
    print("=" * 10, t)
    print(getattr(r, t))
print(r.warnings)
