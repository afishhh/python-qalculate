import ast
from os import walk
from pathlib import Path


def merge_typing_files(lower: Path | str, upper: Path | str) -> str:
    def _parse(source: Path | str) -> ast.Module:
        if isinstance(source, Path):
            return ast.parse(source.read_text(), source, type_comments=True)
        else:
            return ast.parse(source, type_comments=True)

    lower_module = _parse(lower)
    upper_module = _parse(upper)

    lower_classes: dict[str, ast.ClassDef] = {}
    imported_aliases: set[tuple[str, str]] = set()
    imports: list[ast.alias] = []
    new_body = []

    for stmt in lower_module.body:
        if isinstance(stmt, ast.ClassDef):
            lower_classes[stmt.name] = stmt
        elif isinstance(stmt, ast.Import):
            imported_aliases.update(
                (alias.name, alias.asname or alias.name) for alias in stmt.names
            )
            imports += stmt.names
            continue
        new_body.append(stmt)

    for stmt in upper_module.body:
        if isinstance(stmt, ast.ClassDef):
            if stmt.name in lower_classes:
                lower_classes[stmt.name].body += stmt.body
            else:
                new_body.append(stmt)
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                alias_tuple = (alias.name, alias.asname or alias.name)
                if alias_tuple not in imported_aliases:
                    imported_aliases.add(alias_tuple)
                    imports.append(alias)
        else:
            new_body.append(stmt)

    header: list[ast.stmt] = [ast.Import(imports)]
    lower_module.body = header + new_body

    return ast.unparse(lower_module)
