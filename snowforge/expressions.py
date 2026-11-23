"""Small deterministic expression resolver. Never executes arbitrary Python."""
from __future__ import annotations
import ast
import math
import operator
from collections.abc import Mapping

FUNCS = {
    'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos,
    'tan': math.tan, 'asin': math.asin, 'acos': math.acos,
    'atan': math.atan, 'atan2': math.atan2, 'radians': math.radians,
    'degrees': math.degrees, 'hypot': math.hypot,
    'abs': abs, 'min': min, 'max': max, 'round': round,
}
BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub,
           ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.Pow: operator.pow, ast.Mod: operator.mod}
UN_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

class ExpressionError(ValueError):
    pass


def eval_ast(node, names):
    if isinstance(node, ast.Expression):
        return eval_ast(node.body, names)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in BIN_OPS:
        a,b=eval_ast(node.left, names),eval_ast(node.right, names)
        if isinstance(node.op, ast.Pow) and (abs(b)>12 or abs(a)>1e9):
            raise ExpressionError('Power expression exceeds safe bounds')
        return BIN_OPS[type(node.op)](a,b)
    if isinstance(node, ast.UnaryOp) and type(node.op) in UN_OPS:
        return UN_OPS[type(node.op)](eval_ast(node.operand, names))
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and not node.keywords:
        return FUNCS[node.func.id](*[eval_ast(arg, names) for arg in node.args])
    raise ExpressionError(f"Forbidden or unknown expression: {ast.dump(node)}")


def evaluate(value, names):
    """Numeric primitives or string expressions beginning '='."""
    if isinstance(value, bool):
        raise ExpressionError('Boolean cannot be used as a dimension')
    if isinstance(value, (int, float)):
        result = value
    elif isinstance(value, str) and value.startswith('='):
        if len(value)>500:
            raise ExpressionError('Formula too long')
        try:
            result = eval_ast(ast.parse(value[1:], mode='eval'), names)
        except (SyntaxError, TypeError, ZeroDivisionError, OverflowError, ValueError) as exc:
            raise ExpressionError(f'Invalid expression {value!r}: {exc}') from exc
    else:
        raise ExpressionError(f'Dimension must be a number or expression beginning =, received: {value!r}')
    if isinstance(result, bool) or not isinstance(result, (int, float)) or not math.isfinite(result):
        raise ExpressionError(f'Expression is not finite numeric: {value!r}')
    if abs(result) > 1e9:
        raise ExpressionError('Value beyond supported geometric magnitude')
    return result


def resolve_parameters(params):
    if not isinstance(params, Mapping):
        raise ExpressionError('parameters must be an object')
    resolved, stack = {}, set()
    def resolve_one(name):
        if name in resolved:
            return resolved[name]
        if name in stack:
            raise ExpressionError(f'Circular parameter dependency: {name}')
        if name not in params:
            raise ExpressionError(f'Unknown parameter: {name}')
        stack.add(name)
        raw = params[name]
        # Parse dependency names before evaluation; built-ins are handled separately.
        if isinstance(raw, str) and raw.startswith('='):
            try:
                tree = ast.parse(raw[1:], mode='eval')
            except SyntaxError as exc:
                raise ExpressionError(f'Invalid parameter {name}: {exc}') from exc
            dependencies = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - set(FUNCS) - {'pi', 'e'}
            for dep in dependencies:
                resolve_one(dep)
        resolved[name] = evaluate(raw, {**resolved, 'pi': math.pi, 'e': math.e})
        stack.remove(name)
        return resolved[name]
    for key in params:
        if not key.isidentifier() or key in FUNCS or key in ('pi', 'e'):
            raise ExpressionError(f'Invalid parameter name: {key!r}')
        resolve_one(key)
    return resolved


def numeric(v, names):
    return float(evaluate(v, {**names, 'pi': math.pi, 'e': math.e}))


def xy(value, names):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ExpressionError('Coordinate must be a two-element array')
    return (numeric(value[0], names), numeric(value[1], names))
