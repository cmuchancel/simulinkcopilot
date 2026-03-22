from __future__ import annotations

import sympy
import pytest

from ir import equation_dict as equation_dict_module
from ir.equation_dict import (
    derivative_equation_label,
    equation_from_dict,
    expression_from_dict,
    expression_to_dict,
    expression_to_sympy,
    sympy_to_expression,
)
from ir.expression_nodes import EquationNode, NumberNode
from latex_frontend.symbols import DeterministicCompileError


def test_equation_dict_helper_paths_cover_error_branches() -> None:
    with pytest.raises(TypeError, match="Unsupported expression node"):
        expression_to_dict(EquationNode(lhs=NumberNode(0), rhs=NumberNode(1)))  # type: ignore[arg-type]

    with pytest.raises(DeterministicCompileError, match="Unknown serialized operation"):
        expression_from_dict({"op": "mystery"})

    with pytest.raises(TypeError, match="Unsupported serialized expression operation"):
        expression_from_dict({"op": "equation", "lhs": {"op": "const", "value": 0}, "rhs": {"op": "const", "value": 1}})

    with pytest.raises(TypeError, match="Expected equation dictionary"):
        equation_from_dict({"op": "symbol", "name": "x"})

    with pytest.raises(TypeError, match="Unsupported expression node"):
        expression_to_sympy(EquationNode(lhs=NumberNode(0), rhs=NumberNode(1)))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Unsupported SymPy expression"):
        sympy_to_expression(sympy.Matrix([[1]]))

    assert derivative_equation_label("x", 2) == "D2(x)"
