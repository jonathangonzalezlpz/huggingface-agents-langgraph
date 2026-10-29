"""Bounded Python expressions for deterministic calculations without attachments."""

import ast
import json
import subprocess
import sys

from huggingface_agents_langgraph.config import CODE_EXECUTION_TIMEOUT_SECONDS
from huggingface_agents_langgraph.run_tracking import remaining_seconds

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


def validate_expression(expression: str) -> None:
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
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"Unsupported calculation syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError("Private names are not allowed in calculations")
        if isinstance(node, ast.Call):
            if (
                not isinstance(node.func, ast.Name)
                or node.func.id not in ALLOWED_FUNCTIONS
                or node.keywords
            ):
                raise ValueError("Calculation calls must use an allowed pure function")
        if isinstance(node, ast.comprehension) and node.is_async:
            raise ValueError("Async expressions are not allowed")


def calculate(expression: str) -> str:
    """Evaluate a validated expression in a timed, isolated Python process."""
    validate_expression(expression)
    program = (
        "import builtins,json,sys;"
        f"allowed={sorted(ALLOWED_FUNCTIONS)!r};"
        "scope={name:getattr(builtins,name) for name in allowed};"
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
        )
    except subprocess.TimeoutExpired as error:
        raise TimeoutError("Calculation exceeded its time budget") from error
    if result.returncode:
        raise ValueError("Calculation failed: " + result.stderr.strip()[-1500:])
    if len(result.stdout) > 18000:
        raise ValueError("Calculation output exceeds the evidence budget")
    return json.dumps(json.loads(result.stdout), ensure_ascii=False)
