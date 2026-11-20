"""Conservative syntax rules. Findings describe patterns, not proven exploitability."""

import ast
import re

from tree_sitter import Tree

from ai_code_review.analysis.ast import walk
from ai_code_review.core.models import (
    ASTContext,
    Category,
    FileChange,
    LineRange,
    Severity,
    StaticFinding,
    SuggestedFix,
)


def finding(
    file: FileChange,
    line: int,
    rule: str,
    category: Category,
    severity: Severity,
    title: str,
    description: str,
    recommendation: str,
    confidence: float = 0.95,
) -> StaticFinding:
    return StaticFinding(
        rule_id=rule,
        category=category,
        severity=severity,
        confidence=confidence,
        title=title,
        description=description,
        file=file.path,
        lines=LineRange(start=line, end=line),
        recommendation=recommendation,
        analyzer="builtin-ast",
    )


def analyze(file: FileChange, context: ASTContext, tree: Tree) -> list[StaticFinding]:
    findings = [
        finding(
            file,
            min(line, max(1, len(file.content.splitlines()))),
            "syntax-error",
            Category.BUG,
            Severity.HIGH,
            "Source contains a syntax error",
            "The parser could not parse this region.",
            "Correct the syntax and run the language compiler or interpreter.",
        )
        for line in context.error_lines
    ]
    if file.language == "python":
        try:
            module = ast.parse(file.content)
        except SyntaxError as exc:
            err_line = exc.lineno or (findings[0].lines.start if findings else 1)
            lines = file.content.splitlines(keepends=True)
            line_text = lines[err_line - 1] if 0 < err_line <= len(lines) else ""
            for item in findings:
                if item.rule_id == "syntax-error" and item.lines.start == err_line:
                    item.description = f"Syntax error: {exc.msg}."
                    c_type = re.match(
                        r"^\s*(int|float|double|char|bool|long|short|void)\s+([^;]+);?",
                        line_text,
                        re.IGNORECASE,
                    )
                    if c_type:
                        item.suggested_fix = SuggestedFix(
                            lines=item.lines,
                            original=line_text,
                            replacement="# In Python, variables are initialized on assignment\n",
                            explanation=(
                                "Python variables do not use static type declarations. "
                                "Variables are initialized upon assignment."
                            ),
                        )
                    elif line_text.strip().endswith(";"):
                        item.suggested_fix = SuggestedFix(
                            lines=item.lines,
                            original=line_text,
                            replacement=line_text.rstrip().rstrip(";") + "\n",
                            explanation="Remove unnecessary semicolon.",
                        )
            return findings
        except RecursionError:
            return findings
        findings.extend(_python(file, module))
    else:
        for node in walk(tree.root_node):
            if node.type == "call_expression":
                function = node.child_by_field_name("function")
                if function is not None and function.text == b"eval":
                    findings.append(
                        finding(
                            file,
                            node.start_point.row + 1,
                            "dynamic-eval",
                            Category.SECURITY,
                            Severity.HIGH,
                            "Dynamic code evaluation",
                            "eval executes a string as code; untrusted input can execute code.",
                            "Replace dynamic evaluation with explicit parsing and dispatch.",
                            0.9,
                        )
                    )
            if node.type == "debugger_statement":
                item = finding(
                    file,
                    node.start_point.row + 1,
                    "debugger-statement",
                    Category.MAINTAINABILITY,
                    Severity.LOW,
                    "Debugger statement left in source",
                    "This statement can pause execution when a debugger is attached.",
                    "Remove the debugging statement before release.",
                )
                line = file.content.splitlines(keepends=True)[item.lines.start - 1]
                if line.strip() in {"debugger;", "debugger"}:
                    item.suggested_fix = SuggestedFix(
                        lines=item.lines,
                        original=line,
                        replacement="",
                        explanation="Remove the standalone debugger statement.",
                    )
                findings.append(item)
    return findings


def _python(file: FileChange, module: ast.Module) -> list[StaticFinding]:
    items: list[StaticFinding] = []
    aliases: dict[str, str] = {}
    bindings: dict[str, str] = {}
    ambiguous_bindings: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                value_type = _known_python_type(node.value, bindings)
                if value_type is None:
                    ambiguous_bindings.add(target.id)
                elif target.id in bindings and bindings[target.id] != value_type:
                    ambiguous_bindings.add(target.id)
                else:
                    bindings[target.id] = value_type

    def call_name(expr: ast.expr) -> str:
        if isinstance(expr, ast.Name):
            return aliases.get(expr.id, expr.id)
        if isinstance(expr, ast.Attribute):
            return f"{call_name(expr.value)}.{expr.attr}"
        return ""

    def add(
        node: ast.stmt | ast.expr | ast.ExceptHandler,
        rule: str,
        cat: Category,
        sev: Severity,
        title: str,
        detail: str,
        advice: str,
        confidence: float = 0.95,
    ) -> None:
        items.append(
            finding(file, int(node.lineno), rule, cat, sev, title, detail, advice, confidence)
        )

    for node in ast.walk(module):
        if isinstance(node, ast.BinOp):
            left_type = _known_python_type(node.left, bindings, ambiguous_bindings)
            right_type = _known_python_type(node.right, bindings, ambiguous_bindings)
            if _incompatible_binary_operands(node.op, left_type, right_type):
                add(
                    node,
                    "incompatible-operands",
                    Category.BUG,
                    Severity.HIGH,
                    "Operation uses incompatible operand types",
                    (
                        f"This operation combines a {left_type} value with a {right_type} "
                        "value and will raise TypeError at runtime."
                    ),
                    (
                        "Make both operands compatible with the intended operation, for "
                        "example by assigning a numeric radius before calculating an area."
                    ),
                    0.98,
                )
        if isinstance(node, ast.Call):
            name = call_name(node.func)
            if name in {"eval", "exec", "builtins.eval", "builtins.exec"}:
                add(
                    node,
                    "dynamic-eval",
                    Category.SECURITY,
                    Severity.HIGH,
                    "Dynamic code evaluation",
                    "This call executes strings as Python code.",
                    "Use a constrained parser or explicit operation dispatch.",
                    0.9,
                )
            if name in {
                "subprocess.run",
                "subprocess.call",
                "subprocess.Popen",
                "subprocess.check_call",
                "subprocess.check_output",
            } and any(
                kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                for kw in node.keywords
            ):
                add(
                    node,
                    "shell-true",
                    Category.SECURITY,
                    Severity.HIGH,
                    "Shell command execution enabled",
                    "shell=True enables shell interpretation; input may inject commands.",
                    "Pass an argument list with shell=False and validate external input.",
                    0.9,
                )
            if name in {"pickle.load", "pickle.loads"}:
                add(
                    node,
                    "unsafe-pickle",
                    Category.SECURITY,
                    Severity.HIGH,
                    "Unsafe deserialization boundary",
                    "Unpickling untrusted data can execute code.",
                    "Use a data-only format for untrusted input; verify the trust boundary.",
                    0.85,
                )
            if (
                name.endswith((".execute", ".executemany"))
                and node.args
                and isinstance(node.args[0], (ast.JoinedStr, ast.BinOp))
            ):
                add(
                    node,
                    "dynamic-query",
                    Category.SECURITY,
                    Severity.HIGH,
                    "Dynamically constructed query",
                    "An execute call receives a formatted expression; inspect for SQL input.",
                    "Use your database driver's bound parameters instead of string interpolation.",
                    0.8,
                )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defaults = [*node.args.defaults, *[v for v in node.args.kw_defaults if v is not None]]
            for default in defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    add(
                        default,
                        "mutable-default",
                        Category.BUG,
                        Severity.MEDIUM,
                        "Mutable default argument",
                        "This default object is created once and shared between calls.",
                        "Default to None and create a fresh collection inside the function.",
                    )
            if not node.name.startswith("_") and ast.get_docstring(node) is None:
                add(
                    node,
                    "missing-docstring",
                    Category.DOCUMENTATION,
                    Severity.INFO,
                    "Add a description to this public function",
                    (
                        "This function does not explain what it does, what it needs, "
                        "or what it returns."
                    ),
                    (
                        "Add a short docstring that explains the function's purpose, "
                        "inputs, output, and important errors."
                    ),
                    1.0,
                )
            span = (node.end_lineno or node.lineno) - node.lineno + 1
            if span > 80:
                add(
                    node,
                    "long-function",
                    Category.MAINTAINABILITY,
                    Severity.LOW,
                    "Long function",
                    f"This function spans {span} lines.",
                    "Consider extracting cohesive operations into named helpers.",
                    0.85,
                )
            branches = sum(
                isinstance(
                    n, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp)
                )
                for n in ast.walk(node)
            )
            if branches >= 10:
                add(
                    node,
                    "branch-count",
                    Category.COMPLEXITY,
                    Severity.MEDIUM,
                    "High branch count",
                    f"Function subtree contains {branches} branching constructs.",
                    "Simplify branching and test each path; this is not a full CFG metric.",
                    0.9,
                )
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            add(
                node,
                "bare-except",
                Category.BUG,
                Severity.MEDIUM,
                "Bare except catches process-control exceptions",
                "This handler also catches SystemExit and KeyboardInterrupt.",
                "Catch the specific exceptions the operation can recover from.",
            )
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                add(
                    node,
                    "division-by-zero",
                    Category.BUG,
                    Severity.HIGH,
                    "Literal zero divisor",
                    "This operation raises on execution with numeric operands.",
                    "Correct the divisor or explicitly handle the zero case.",
                )
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            if any(
                isinstance(child, (ast.For, ast.AsyncFor, ast.While))
                for stmt in node.body
                for child in ast.walk(stmt)
            ):
                add(
                    node,
                    "nested-loop",
                    Category.PERFORMANCE,
                    Severity.LOW,
                    "Nested iteration",
                    "Nested loops may multiply work for growing input sizes.",
                    "Measure with representative inputs; consider indexing or set membership.",
                    0.7,
                )
    return items


def _known_python_type(
    node: ast.AST,
    bindings: dict[str, str],
    ambiguous_bindings: set[str] | None = None,
) -> str | None:
    """Return a small, conservative type fact for literals and simple names."""
    ambiguous_bindings = ambiguous_bindings or set()
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "None"
        if isinstance(node.value, bool):
            return "bool"
        if isinstance(node.value, (int, float, complex)):
            return "number"
        if isinstance(node.value, str):
            return "str"
        if isinstance(node.value, bytes):
            return "bytes"
    if isinstance(node, ast.Name) and node.id not in ambiguous_bindings:
        return bindings.get(node.id)
    return None


def _incompatible_binary_operands(
    operator: ast.operator, left_type: str | None, right_type: str | None
) -> bool:
    if left_type is None or right_type is None:
        return False
    if isinstance(operator, (ast.Add, ast.Sub, ast.Div, ast.FloorDiv, ast.Pow)):
        if left_type == "str" or right_type == "str":
            return not (isinstance(operator, ast.Add) and left_type == right_type == "str")
        return left_type not in {"number", "bool"} or right_type not in {"number", "bool"}
    if isinstance(operator, ast.Mult):
        return not (
            left_type in {"number", "bool"} and right_type in {"number", "bool"}
            or left_type == "str" and right_type in {"number", "bool"}
            or right_type == "str" and left_type in {"number", "bool"}
        )
    if isinstance(operator, ast.Mod):
        return not (
            left_type in {"number", "bool"} and right_type in {"number", "bool"}
            or left_type == "str"
        )
    return False
