"""Provide the calculator function used by the local MCP server."""

from __future__ import annotations


def calculate(a: float, b: float, operation: str = "+") -> float:
    """Calculate two numbers using +, -, *, or /."""

    if isinstance(a, bool) or not isinstance(a, (int, float)):
        raise ValueError("a must be a number")
    if isinstance(b, bool) or not isinstance(b, (int, float)):
        raise ValueError("b must be a number")
    if not isinstance(operation, str):
        raise ValueError("operation must be one of: +, -, *, /")

    normalized_operation = operation.strip()
    if normalized_operation == "+":
        return float(a + b)
    if normalized_operation == "-":
        return float(a - b)
    if normalized_operation == "*":
        return float(a * b)
    if normalized_operation == "/":
        if b == 0:
            raise ValueError("division by zero is not allowed")
        return float(a / b)
    raise ValueError("operation must be one of: +, -, *, /")
