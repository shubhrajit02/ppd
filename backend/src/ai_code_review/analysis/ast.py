"""Tree-Sitter syntax context for Python, JavaScript and TypeScript."""

from functools import lru_cache

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser, Tree

from ai_code_review.core.models import ASTContext, FileChange, LineRange, Symbol


@lru_cache(maxsize=4)
def grammar(language: str) -> Language:
    capsules = {
        "python": tree_sitter_python.language,
        "javascript": tree_sitter_javascript.language,
        "typescript": tree_sitter_typescript.language_typescript,
        "tsx": tree_sitter_typescript.language_tsx,
    }
    return Language(capsules[language]())


def walk(node: Node) -> list[Node]:
    """Iterative traversal avoids recursion limits on deeply nested source."""
    nodes, stack = [], [node]
    while stack:
        current = stack.pop()
        nodes.append(current)
        stack.extend(reversed(current.children))
    return nodes


def parse(file: FileChange) -> tuple[ASTContext, Tree]:
    tree = Parser(grammar(file.language)).parse(file.content.encode("utf-8"))
    context = ASTContext(file=file.path, language=file.language)
    lines: set[int] = set()
    for node in walk(tree.root_node):
        if node.is_error or node.is_missing:
            context.error_lines.append(node.start_point.row + 1)
        if not node.children and node.type not in {"comment", "string", "string_content"}:
            lines.add(node.start_point.row + 1)
        if node.type in {
            "function_definition",
            "class_definition",
            "function_declaration",
            "class_declaration",
            "method_definition",
            "variable_declarator",
        }:
            name = node.child_by_field_name("name")
            if name is not None and name.text:
                context.symbols.append(
                    Symbol(
                        name=name.text.decode("utf-8"),
                        lines=LineRange(start=node.start_point.row + 1, end=node.end_point.row + 1),
                    )
                )
    context.code_lines = sorted(lines)
    context.error_lines = sorted(set(context.error_lines))
    return context, tree
