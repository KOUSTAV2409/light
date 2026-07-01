"""Calculator provider — safe port of Snap/CalculatorSearchItem.swift."""

from __future__ import annotations

import ast
import operator
import subprocess
from typing import Any

from .search_item import SearchItem

_ALLOWED_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expression: str) -> str | None:
    try:
        node = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("unsupported expression")

    try:
        value = _eval(node)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None

    if value == int(value):
        return str(int(value))
    return str(round(value, 10)).rstrip("0").rstrip(".")


def _copy_to_clipboard(text: str) -> None:
    for cmd in (
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ):
        try:
            subprocess.run(cmd, input=text.encode(), check=True, timeout=2)
            return
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue


def maybe_calculator_item(query: str) -> SearchItem | None:
    stripped = query.strip()
    if not stripped:
        return None
    if stripped[0] not in "0123456789+-(":
        return None

    result = _safe_eval(stripped)
    if result is None:
        return None

    title = f"{stripped} = {result}"

    return SearchItem(
        title=title,
        subtitle="Copy result to clipboard",
        icon_name="accessories-calculator",
        action=lambda r=result: _copy_to_clipboard(r),
    )
