"""Bounded Python expressions for deterministic calculations without attachments."""

import ast
import json
import os
import subprocess
import sys
from copy import deepcopy

from huggingface_agents_langgraph.config import CODE_EXECUTION_TIMEOUT_SECONDS
from huggingface_agents_langgraph.experiments import improvement_enabled
from huggingface_agents_langgraph.run_tracking import remaining_seconds

STRING_METHODS = {
    "join",
    "split",
    "strip",
    "lower",
    "upper",
    "replace",
    "count",
    "find",
}


def execution_environment() -> dict[str, str]:
    """Pass operating-system essentials without application credentials."""
    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH"}
    }


ALLOWED_FUNCTIONS = {
    "sum",
    "min",
    "max",
    "len",
    "sorted",
    "round",
    "abs",
    "set",
    "list",
    "tuple",
    "range",
    "enumerate",
    "zip",
    "all",
    "any",
    "str",
    "int",
    "float",
}
ALLOWED_NODES = (
    ast.Expression,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.Load,
    ast.Store,
    ast.Name,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Subscript,
    ast.Slice,
    ast.Call,
    ast.ListComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.UAdd,
    ast.USub,
    ast.Not,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
)


def validate_expression(expression: str, *, enhanced: bool = False) -> None:
    """Reject imports, attribute access, arbitrary calls, and oversized syntax."""
    if (
        not isinstance(expression, str)
        or not expression.strip()
        or len(expression) > 12000
    ):
        raise ValueError("Calculation expression must contain 1 to 12000 characters")
    tree = ast.parse(expression, mode="eval")
    nodes = list(ast.walk(tree))
    if len(nodes) > 2000:
        raise ValueError("Calculation expression is too complex")
    for node in nodes:
        if not isinstance(node, ALLOWED_NODES + ((ast.Attribute,) if enhanced else ())):
            raise ValueError(f"Unsupported calculation syntax: {type(node).__name__}")
        if isinstance(node, ast.Attribute):
            if node.attr not in STRING_METHODS or not any(
                isinstance(parent, ast.Call) and parent.func is node for parent in nodes
            ):
                raise ValueError("Only whitelisted string method calls are allowed")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError("Private names are not allowed in calculations")
        if isinstance(node, ast.Call):
            named = isinstance(node.func, ast.Name) and node.func.id in (
                ALLOWED_FUNCTIONS
                | ({"reversed", "bool", "dict"} if enhanced else set())
            )
            method = (
                enhanced
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in STRING_METHODS
            )
            if not (named or method) or node.keywords:
                raise ValueError("Calculation calls must use an allowed pure function")
        if isinstance(node, ast.comprehension) and node.is_async:
            raise ValueError("Async expressions are not allowed")


def calculate(expression: str) -> str:
    """Evaluate a validated expression in a timed, isolated Python process."""
    enhanced = improvement_enabled(None, "calculation_tools")
    validate_expression(expression, enhanced=enhanced)
    functions = ALLOWED_FUNCTIONS | (
        {"reversed", "bool", "dict"} if enhanced else set()
    )
    if enhanced:
        tree = ast.parse(expression, mode="eval")

        class StringCalls(ast.NodeTransformer):
            def visit_Call(self, node):
                node = self.generic_visit(node)
                if isinstance(node.func, ast.Attribute):
                    return ast.copy_location(
                        ast.Call(
                            func=ast.Name(id="string_method", ctx=ast.Load()),
                            args=[
                                node.func.value,
                                ast.Constant(node.func.attr),
                                *node.args,
                            ],
                            keywords=[],
                        ),
                        node,
                    )
                return node

        expression = ast.unparse(
            ast.fix_missing_locations(StringCalls().visit(deepcopy(tree)))
        )
    program = (
        "import builtins,json,sys;"
        f"allowed={sorted(functions)!r};"
        "scope={name:getattr(builtins,name) for name in allowed};"
        "scope['string_method']=lambda value,name,*args: "
        "getattr(value,name)(*args) if isinstance(value,str) "
        "else (_ for _ in ()).throw(ValueError('String receiver required'));"
        "scope['__builtins__']={};"
        "result=eval(compile(sys.argv[1],'<calculation>','eval'),scope);"
        "print(json.dumps(result,default=lambda value:"
        "sorted(value) if isinstance(value,set) else str(value)))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-c", program, expression],
            capture_output=True,
            text=True,
            timeout=min(CODE_EXECUTION_TIMEOUT_SECONDS, remaining_seconds()),
            check=False,
            **({"env": execution_environment()} if enhanced else {}),
        )
    except subprocess.TimeoutExpired as error:
        raise TimeoutError("Calculation exceeded its time budget") from error
    if result.returncode:
        raise ValueError("Calculation failed: " + result.stderr.strip()[-1500:])
    if len(result.stdout) > 18000:
        raise ValueError("Calculation output exceeds the evidence budget")
    return json.dumps(json.loads(result.stdout), ensure_ascii=False)
