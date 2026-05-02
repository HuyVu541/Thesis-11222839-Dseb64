"""
Math tools for the agent.
"""

from langchain_core.tools import tool
from ..registry import registry
import ast
import operator

# Safe operators for calculator
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    """Safely evaluate mathematical expression AST."""
    if isinstance(node, ast.Constant):  # Python 3.8+
        return node.value
    elif isinstance(node, ast.BinOp):
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        op = SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsafe operation: {type(node.op).__name__}")
        return op(left, right)
    elif isinstance(node, ast.UnaryOp):
        operand = _safe_eval(node.operand)
        op = SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsafe operation: {type(node.op).__name__}")
        return op(operand)
    else:
        raise ValueError(f"Unsafe node type: {type(node).__name__}")


@registry.register('math')
@tool
def calculator(expression: str) -> str:
    """
    Safely evaluate a mathematical expression.
    Supports: +, -, *, /, ** (power)
    Example: "2 + 2 * 3" returns "8"
    """
    try:
        # Parse expression into AST
        tree = ast.parse(expression, mode='eval')
        # Safely evaluate
        result = _safe_eval(tree.body)
        return str(result)
    except SyntaxError:
        return "Error: Invalid mathematical expression"
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error - {e}"
