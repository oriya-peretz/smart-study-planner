"""Only api.py may talk HTTP: the pages never import httpx themselves."""

import ast
from pathlib import Path

FRONTEND = Path(__file__).parent.parent


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_only_api_imports_httpx():
    pages = [p for p in FRONTEND.glob("*.py") if p.name != "api.py"]
    assert pages, "no frontend modules found"
    for page in pages:
        assert "httpx" not in imported_modules(page), f"{page.name} talks HTTP directly"
