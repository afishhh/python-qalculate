import ast
from pathlib import Path
from generate.bindings import PyContext


def merge_typing_files(lower: Path | str, upper: Path | str, context: PyContext) -> str:
    def _parse(source: Path | str) -> ast.Module:
        if isinstance(source, Path):
            return ast.parse(source.read_text(), source)
        else:
            return ast.parse(source)

    lower_module = _parse(lower)
    upper_module = _parse(upper)

    def make_union(values: list[str], current_name: str, recurse_to: str) -> ast.expr:
        def make_constant(value: str) -> ast.Constant:
            if value != current_name:
                value = value.replace(current_name, recurse_to)
            return ast.Constant(value)

        union: ast.expr = make_constant(values[0])
        i = 1
        while i < len(values):
            union = ast.BinOp(union, ast.BitOr(), make_constant(values[i]))
            i += 1
        return union

    new_body = []
    for type, castable_from in context.implicit_casts.items():
        convertible_name = f"_ConvertibleTo{type}"
        constructible_name = f"_{type}ConstructibleFrom"
        new_body.append(
            ast.AnnAssign(
                target=ast.Name(convertible_name),
                annotation=ast.Name("typing.TypeAlias"),
                value=make_union(castable_from + [type], type, convertible_name),
                simple=1
            )
        )
        new_body.append(
            ast.AnnAssign(
                target=ast.Name(constructible_name),
                annotation=ast.Name("typing.TypeAlias"),
                value=make_union(castable_from, type, convertible_name),
                simple=1
            )
        )

    class CasterAnnotationVisitor(ast.NodeTransformer):
        def _make_union(self, type: str) -> ast.expr | None:
            if type in context.implicit_casts:
                return ast.Name(f"_ConvertibleTo{type}")

        def visit_Constant(self, node: ast.Constant) -> ast.expr:
            if isinstance(node.value, str):
                return self._make_union(node.value) or node
            return node

        def visit_Name(self, node: ast.Name) -> ast.expr:
            return self._make_union(node.id) or node

    class ImplicitCasterVisitor(ast.NodeTransformer):
        def visit_arg(self, node: ast.arg):
            if node.annotation:
                node.annotation = CasterAnnotationVisitor().visit(node.annotation)
                return node
            return node

    upper_module = ImplicitCasterVisitor().visit(upper_module)
    assert isinstance(upper_module, ast.Module)

    lower_classes: dict[str, ast.ClassDef] = {}
    imported_aliases: set[tuple[str, str]] = set()
    imports: list[ast.alias] = [
        ast.alias("typing")
    ]

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
                lower_class = lower_classes[stmt.name]
                lower_class.body += stmt.body
                lower_base_names = {
                    base.id for base in lower_class.bases if isinstance(base, ast.Name)
                }
                for base in stmt.bases:
                    assert isinstance(base, ast.Name)
                    if base.id not in lower_base_names:
                        lower_class.bases.append(base)
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
