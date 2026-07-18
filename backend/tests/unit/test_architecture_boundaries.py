import ast
from pathlib import Path

ALLOWED_DEPENDENCIES: dict[str, frozenset[str]] = {
    "domain": frozenset({"domain", "shared"}),
    "application": frozenset({"application", "domain", "shared"}),
    "presentation": frozenset({"presentation", "application", "domain", "shared"}),
    "infrastructure": frozenset(
        {"infrastructure", "presentation", "application", "domain", "shared"}
    ),
    "shared": frozenset({"shared"}),
}


def _app_imports(source_file: Path) -> set[str]:
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    return {module for module in imported_modules if module.startswith("app.")}


def test_clean_architecture_dependency_direction() -> None:
    app_root = Path(__file__).parents[2] / "app"
    violations: list[str] = []

    for source_file in app_root.rglob("*.py"):
        relative_path = source_file.relative_to(app_root)
        source_layer = relative_path.parts[0]
        allowed_layers = ALLOWED_DEPENDENCIES.get(source_layer)
        if allowed_layers is None:
            continue

        for module in _app_imports(source_file):
            imported_layer = module.split(".", maxsplit=2)[1]
            if imported_layer not in allowed_layers:
                violations.append(
                    f"{relative_path}: {source_layer} cannot import {module}"
                )

    assert violations == []
