"""Deterministic extraction of database entities: EF Core / annotated classes, model classes, SQL tables."""
import re
from pathlib import Path
from typing import Dict, List

from app.analyzers.discovery import iter_files, parts_lower, read, rel
from app.models.comparison import EntityInfo

CLASS_DECL = re.compile(r"\b(?:class|record)\s+(\w+)\s*(?::\s*([^{;]+?))?\s*\{")
DBSET = re.compile(r"\bDbSet<\s*([\w.]+)\s*>\s+(\w+)")
PROP = re.compile(r"\bpublic\s+(?!class\b)(?:virtual\s+|required\s+)*([\w<>\[\]?,.]+)\s+(\w+)\s*\{\s*get")
SQL_TABLE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\[\"`]?(?:\w+[\]\"`]?\.[\[\"`]?)?(\w+)", re.I)
MODEL_DIRS = {"models", "entities", "entity", "domain", "data"}
NOT_ENTITY = ("ViewModel", "Dto", "Request", "Response", "Controller", "Service", "Context",
              "Options", "Settings", "Config", "Exception", "Model" + "State")


def _body(text: str, open_idx: int) -> str:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i]
    return text[open_idx + 1:]


def extract_entities(root: Path) -> List[EntityInfo]:
    found: Dict[str, EntityInfo] = {}
    cs_files = [(f, read(f)) for f in iter_files(root, (".cs",))]
    dbsets: Dict[str, str] = {}
    for _, text in cs_files:
        for m in DBSET.finditer(text):
            dbsets[m.group(1).split(".")[-1]] = m.group(2)

    for f, text in cs_files:
        parts = parts_lower(root, f)
        for m in CLASS_DECL.finditer(text):
            name, base = m.group(1), m.group(2) or ""
            if "DbContext" in base or name.endswith(NOT_ENTITY):
                continue
            above = "\n".join(text[:m.start()].splitlines()[-4:])
            body = _body(text, m.end() - 1)
            props = {p.group(2): p.group(1) for p in PROP.finditer(body)}
            table = dbsets.get(name)
            annotated = bool(re.search(r"\[\s*Table\b", above) or re.search(r"\[\s*Key\b", body))
            tm = re.search(r"\[\s*Table\(\s*\"([^\"]+)\"", above)
            if tm:
                table = tm.group(1)
            if name in dbsets or annotated:
                kind = "ef-entity"
            elif props and MODEL_DIRS.intersection(parts):
                kind = "model"
            else:
                continue
            found[name] = EntityInfo(name=name, kind=kind, table=table, properties=props, file=rel(root, f))

    for f in iter_files(root, (".sql",)):
        for m in SQL_TABLE.finditer(read(f)):
            found.setdefault(m.group(1), EntityInfo(name=m.group(1), kind="sql-table",
                                                    table=m.group(1), file=rel(root, f)))
    return sorted(found.values(), key=lambda e: e.name)
