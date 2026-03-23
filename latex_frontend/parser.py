"""Recursive-descent parser for the restricted LaTeX ODE grammar."""

from __future__ import annotations

from dataclasses import dataclass

from ir.expression_nodes import (
    AddNode,
    DerivativeNode,
    DivNode,
    EquationNode,
    ExpressionNode,
    FunctionNode,
    MulNode,
    NegNode,
    NumberNode,
    PowNode,
    SymbolNode,
    flatten_add,
    flatten_mul,
)
from latex_frontend.symbols import LATEX_FUNCTION_ALIASES, function_arity, UnsupportedSyntaxError
from latex_frontend.tokenizer import Token


@dataclass
class Parser:
    """Deterministic parser for the supported LaTeX expression subset."""

    tokens: list[Token]
    index: int = 0

    def parse_document(self) -> list[EquationNode]:
        equations: list[EquationNode] = []
        while self.current().kind != "EOF":
            while self.current().kind == "NEWLINE":
                self.advance()
            if self.current().kind == "EOF":
                break
            equations.append(self.parse_equation())
            while self.current().kind == "NEWLINE":
                self.advance()
        return equations

    def parse_equation(self) -> EquationNode:
        lhs = self.parse_expression()
        self.expect("EQUALS")
        rhs = self.parse_expression()
        return EquationNode(lhs=lhs, rhs=rhs)

    def parse_expression(self) -> ExpressionNode:
        node = self.parse_term()
        while self.current().kind in {"PLUS", "MINUS"}:
            operator = self.advance()
            rhs = self.parse_term()
            if operator.kind == "PLUS":
                node = AddNode(flatten_add([node, rhs]))
            else:
                node = AddNode(flatten_add([node, NegNode(rhs)]))
        return node

    def parse_term(self) -> ExpressionNode:
        node = self.parse_unary()
        while True:
            if self.current().kind == "STAR":
                self.advance()
                rhs = self.parse_unary()
                node = MulNode(flatten_mul([node, rhs]))
                continue
            if self.current().kind == "SLASH":
                self.advance()
                rhs = self.parse_unary()
                node = DivNode(node, rhs)
                continue
            if self._starts_factor(self.current().kind):
                rhs = self.parse_unary()
                node = MulNode(flatten_mul([node, rhs]))
                continue
            break
        return node

    def parse_power(self) -> ExpressionNode:
        node = self.parse_primary()
        if self.current().kind == "CARET":
            self.advance()
            exponent = self.parse_unary()
            return PowNode(node, exponent)
        return node

    def parse_unary(self) -> ExpressionNode:
        if self.current().kind == "MINUS":
            self.advance()
            return NegNode(self.parse_unary())
        return self.parse_power()

    def parse_primary(self) -> ExpressionNode:
        token = self.current()
        if token.kind == "NUMBER":
            self.advance()
            if "." in token.value:
                return NumberNode(float(token.value))
            return NumberNode(int(token.value))
        if token.kind == "IDENT":
            self.advance()
            return SymbolNode(token.value)
        if token.kind == "COMMAND":
            if token.value == "frac":
                return self.parse_fraction()
            if token.value == "dot":
                return self.parse_derivative(order=1)
            if token.value == "ddot":
                return self.parse_derivative(order=2)
            if token.value == "deriv":
                return self.parse_general_derivative()
            if token.value in LATEX_FUNCTION_ALIASES:
                return self.parse_function()
            raise UnsupportedSyntaxError(f"Unsupported command '\\{token.value}' at position {token.position}.")
        if token.kind in {"LPAREN", "LBRACE"}:
            return self.parse_group()
        raise UnsupportedSyntaxError(
            f"Unexpected token {token.kind} at position {token.position}; unable to parse primary expression."
        )

    def parse_fraction(self) -> ExpressionNode:
        self.expect("COMMAND", "frac")
        numerator = self.parse_group()
        denominator = self.parse_group()
        return DivNode(numerator, denominator)

    def parse_derivative(self, order: int) -> ExpressionNode:
        self.advance()
        target = self.parse_group_or_symbol()
        if not isinstance(target, SymbolNode):
            raise UnsupportedSyntaxError("Derivative arguments must be single symbols in this deterministic frontend.")
        return DerivativeNode(base=target.name, order=order)

    def parse_general_derivative(self) -> ExpressionNode:
        self.expect("COMMAND", "deriv")
        order_expr = self.parse_group()
        if not isinstance(order_expr, NumberNode) or not isinstance(order_expr.value, int):
            raise UnsupportedSyntaxError("General derivatives require an explicit integer order.")
        target = self.parse_group_or_symbol()
        if not isinstance(target, SymbolNode):
            raise UnsupportedSyntaxError("Derivative arguments must be single symbols in this deterministic frontend.")
        return DerivativeNode(base=target.name, order=order_expr.value)

    def parse_function(self) -> ExpressionNode:
        function_name = self.expect("COMMAND").value
        op_name = LATEX_FUNCTION_ALIASES[function_name]
        min_arity, max_arity = function_arity(op_name)
        if self.current().kind in {"LPAREN", "LBRACE"}:
            args = self.parse_function_arguments()
        elif min_arity == 1 and max_arity == 1:
            args = (self.parse_group_or_symbol(),)
        else:
            token = self.current()
            raise UnsupportedSyntaxError(
                f"Function '\\{function_name}' requires an explicit grouped argument list at position {token.position}."
            )
        if len(args) < min_arity or (max_arity is not None and len(args) > max_arity):
            token = self.current()
            raise UnsupportedSyntaxError(
                f"Function '\\{function_name}' requires between {min_arity} and "
                f"{max_arity if max_arity is not None else 'many'} arguments at position {token.position}."
            )
        return FunctionNode(function=op_name, args=args)

    def parse_function_arguments(self) -> tuple[ExpressionNode, ...]:
        opening = self.current()
        if opening.kind == "LPAREN":
            closing = "RPAREN"
        elif opening.kind == "LBRACE":
            closing = "RBRACE"
        else:
            raise UnsupportedSyntaxError(
                f"Expected function argument list at position {opening.position}, found {opening.kind}."
            )
        self.advance()
        args = [self.parse_expression()]
        while self.current().kind == "COMMA":
            self.advance()
            args.append(self.parse_expression())
        self.expect(closing)
        return tuple(args)

    def parse_group_or_symbol(self) -> ExpressionNode:
        if self.current().kind == "IDENT":
            token = self.advance()
            return SymbolNode(token.value)
        return self.parse_group()

    def parse_group(self) -> ExpressionNode:
        opening = self.current()
        if opening.kind == "LPAREN":
            closing = "RPAREN"
        elif opening.kind == "LBRACE":
            closing = "RBRACE"
        else:
            raise UnsupportedSyntaxError(
                f"Expected grouped expression at position {opening.position}, found {opening.kind}."
            )
        self.advance()
        expr = self.parse_expression()
        self.expect(closing)
        return expr

    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def expect(self, kind: str, value: str | None = None) -> Token:
        token = self.current()
        if token.kind != kind or (value is not None and token.value != value):
            expected = f"{kind} {value!r}" if value is not None else kind
            raise UnsupportedSyntaxError(
                f"Expected {expected} at position {token.position}, found {token.kind} {token.value!r}."
            )
        return self.advance()

    @staticmethod
    def _starts_factor(kind: str) -> bool:
        return kind in {"NUMBER", "IDENT", "COMMAND", "LPAREN", "LBRACE"}
