"""Deterministic matrix/vector input expansion into scalar equations."""

from __future__ import annotations

from dataclasses import dataclass
import re

from latex_frontend.symbols import UnsupportedSyntaxError


_MATRIX_ENVIRONMENTS = {
    "matrix",
    "pmatrix",
    "bmatrix",
    "Bmatrix",
    "vmatrix",
    "Vmatrix",
}
_MATRIX_ENV_START_RE = re.compile(r"\\begin\{(?P<env>[A-Za-z*]+)\}")
_STRIPPED_ENV_RE = re.compile(r"\\(?P<command>begin|end)\{(?P<env>equation\*?|align\*?)\}")
_DOT_VECTOR_RE = re.compile(r"\\(?P<command>dot|ddot)\{(?P<symbol>[A-Za-z][A-Za-z0-9_]*)\}")
_GENERAL_DERIV_RE = re.compile(r"\\deriv\{(?P<order>\d+)\}\{(?P<symbol>[A-Za-z][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class MatrixValue:
    rows: tuple[tuple[str, ...], ...]

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.rows), len(self.rows[0]) if self.rows else 0

    @property
    def row_count(self) -> int:
        return self.shape[0]

    @property
    def col_count(self) -> int:
        return self.shape[1]

    def is_scalar(self) -> bool:
        return self.shape == (1, 1)

    def scalar(self) -> str:
        if not self.is_scalar():
            raise UnsupportedSyntaxError("Expected a scalar expression during matrix expansion.")
        return self.rows[0][0]

    def transpose(self) -> MatrixValue:
        return MatrixValue(tuple(tuple(self.rows[row][col] for row in range(self.row_count)) for col in range(self.col_count)))


def expand_matrix_syntax(text: str) -> str:
    """Expand supported matrix/vector syntax into scalar equations."""
    text = _STRIPPED_ENV_RE.sub("", text)
    context: dict[str, MatrixValue] = {}
    output_lines: list[str] = []
    for statement in _split_statements(text):
        if not statement:
            continue
        lhs_text, rhs_text = _split_equation(statement)
        lhs_matrix = _evaluate_lhs(lhs_text, context)
        rhs_has_matrix_intent = _has_matrix_intent(rhs_text, context)
        rhs_matrix = _evaluate_expr(rhs_text, context)

        if lhs_matrix is None and rhs_matrix.is_scalar() and not rhs_has_matrix_intent:
            output_lines.append(f"{lhs_text.strip()} = {rhs_matrix.scalar()}")
            continue

        if lhs_matrix is None:
            symbol_name = _parse_plain_symbol(lhs_text)
            if symbol_name is None:
                raise UnsupportedSyntaxError(
                    "Matrix-valued equations require a plain symbol definition or matrix/vector left-hand side."
                )
            context[symbol_name] = rhs_matrix
            continue

        if lhs_matrix.shape != rhs_matrix.shape:
            raise UnsupportedSyntaxError(
                f"Matrix equation shape mismatch: lhs {lhs_matrix.shape}, rhs {rhs_matrix.shape}."
            )
        output_lines.extend(_matrix_equations(lhs_matrix, rhs_matrix))

    return "\n".join(output_lines)


def _split_statements(text: str) -> list[str]:
    statements: list[str] = []
    start = 0
    i = 0
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    while i < len(text):
        env_end = _consume_matrix_environment(text, i)
        if env_end is not None:
            i = env_end
            continue
        char = text[i]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char == "\n" and paren_depth == brace_depth == bracket_depth == 0:
            statement = text[start:i].strip()
            if statement:
                statements.append(statement)
            start = i + 1
        i += 1
    tail = text[start:].strip()
    if tail:
        statements.append(tail)
    return statements


def _split_equation(statement: str) -> tuple[str, str]:
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    i = 0
    while i < len(statement):
        env_end = _consume_matrix_environment(statement, i)
        if env_end is not None:
            i = env_end
            continue
        char = statement[i]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char == "=" and paren_depth == brace_depth == bracket_depth == 0:
            return statement[:i].strip(), statement[i + 1 :].strip()
        i += 1
    raise UnsupportedSyntaxError(f"Unable to split equation {statement!r}; missing top-level '='.")


def _evaluate_lhs(expr: str, context: dict[str, MatrixValue]) -> MatrixValue | None:
    literal = _parse_matrix_literal(expr)
    if literal is not None:
        return literal

    derivative = _expand_vector_derivative(expr.strip(), context)
    if derivative is not None:
        return derivative
    return None


def _evaluate_expr(expr: str, context: dict[str, MatrixValue]) -> MatrixValue:
    literal = _parse_matrix_literal(expr)
    if literal is not None:
        return literal

    derivative = _expand_vector_derivative(expr.strip(), context)
    if derivative is not None:
        return derivative

    terms = _split_additive_terms(expr)
    total: MatrixValue | None = None
    for sign, term_text in terms:
        value = _evaluate_product_term(term_text, context)
        if sign < 0:
            value = _scale_matrix("-1", value)
        total = value if total is None else _add_matrices(total, value)
    if total is None:
        raise UnsupportedSyntaxError(f"Unsupported empty matrix expression {expr!r}.")
    return total


def _has_matrix_intent(expr: str, context: dict[str, MatrixValue]) -> bool:
    if _parse_matrix_literal(expr) is not None:
        return True
    if _expand_vector_derivative(expr.strip(), context) is not None:
        return True
    for symbol_name in context:
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(symbol_name)}(?![A-Za-z0-9_])", expr):
            return True
        if symbol_name in expr:
            return True
    return False


def _evaluate_product_term(term: str, context: dict[str, MatrixValue]) -> MatrixValue:
    factors = _parse_factors(term, context)
    if not factors:
        raise UnsupportedSyntaxError(f"Unsupported matrix product term {term!r}.")
    result = factors[0]
    for factor in factors[1:]:
        result = _multiply_values(result, factor)
    return result


def _parse_factors(term: str, context: dict[str, MatrixValue]) -> list[MatrixValue]:
    factors: list[MatrixValue] = []
    i = 0
    while i < len(term):
        while i < len(term) and term[i].isspace():
            i += 1
        if i >= len(term):
            break
        if term[i] == "*":
            i += 1
            continue

        literal_end = _matrix_literal_end(term, i)
        if literal_end is not None:
            factors.append(_parse_matrix_literal(term[i:literal_end]))
            i = literal_end
            continue

        derivative_match = _match_vector_derivative(term, i, context)
        if derivative_match is not None:
            end, matrix = derivative_match
            factors.append(matrix)
            i = end
            continue

        symbol_match = _match_matrix_symbol(term, i, context)
        if symbol_match is not None:
            end, matrix = symbol_match
            factors.append(matrix)
            i = end
            continue

        scalar_end = _consume_scalar_segment(term, i, context)
        scalar_text = term[i:scalar_end].strip()
        if not scalar_text:
            raise UnsupportedSyntaxError(f"Unable to parse matrix product term {term!r}.")
        factors.append(MatrixValue(((scalar_text,),)))
        i = scalar_end
    return factors


def _split_additive_terms(expr: str) -> list[tuple[int, str]]:
    terms: list[tuple[int, str]] = []
    start = 0
    sign = 1
    i = 0
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    while i < len(expr):
        env_end = _consume_matrix_environment(expr, i)
        if env_end is not None:
            i = env_end
            continue
        char = expr[i]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char in "+-" and paren_depth == brace_depth == bracket_depth == 0:
            if i == start:
                sign = -1 if char == "-" else 1
                start = i + 1
                i += 1
                continue
            term = expr[start:i].strip()
            if term:
                terms.append((sign, term))
            sign = -1 if char == "-" else 1
            start = i + 1
        i += 1
    tail = expr[start:].strip()
    if tail:
        terms.append((sign, tail))
    return terms


def _matrix_equations(lhs: MatrixValue, rhs: MatrixValue) -> list[str]:
    return [
        f"{lhs.rows[row][col]} = {rhs.rows[row][col]}"
        for row in range(lhs.row_count)
        for col in range(lhs.col_count)
    ]


def _parse_plain_symbol(text: str) -> str | None:
    stripped = text.strip()
    return stripped if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", stripped) else None


def _expand_vector_derivative(expr: str, context: dict[str, MatrixValue]) -> MatrixValue | None:
    match = _DOT_VECTOR_RE.fullmatch(expr)
    if match is not None:
        base_symbol = match.group("symbol")
        if base_symbol not in context:
            return None
        order = 1 if match.group("command") == "dot" else 2
        return _apply_derivative(context[base_symbol], order)

    match = _GENERAL_DERIV_RE.fullmatch(expr)
    if match is not None:
        base_symbol = match.group("symbol")
        if base_symbol not in context:
            return None
        return _apply_derivative(context[base_symbol], int(match.group("order")))
    return None


def _apply_derivative(value: MatrixValue, order: int) -> MatrixValue:
    command = "dot" if order == 1 else "ddot" if order == 2 else None
    if command is not None:
        rows = tuple(
            tuple(rf"\{command}{{{entry}}}" for entry in row)
            for row in value.rows
        )
    else:
        rows = tuple(
            tuple(rf"\deriv{{{order}}}{{{entry}}}" for entry in row)
            for row in value.rows
        )
    return MatrixValue(rows)


def _parse_matrix_literal(text: str) -> MatrixValue | None:
    stripped = text.strip()
    env_match = _MATRIX_ENV_START_RE.match(stripped)
    if env_match is not None:
        env = env_match.group("env")
        if env not in _MATRIX_ENVIRONMENTS:
            return None
        end_tag = rf"\end{{{env}}}"
        if not stripped.endswith(end_tag):
            raise UnsupportedSyntaxError(f"Unterminated matrix environment {env!r}.")
        inner = stripped[env_match.end() : -len(end_tag)].strip()
        rows = _split_top_level(inner, row_delimiter=r"\\")
        parsed_rows = tuple(
            tuple(entry.strip() for entry in _split_top_level(row, row_delimiter="&"))
            for row in rows
        )
        return _validate_matrix_rows(parsed_rows)

    transpose = False
    if stripped.endswith("^{T}"):
        stripped = stripped[:-4].strip()
        transpose = True
    elif stripped.endswith("^T"):
        stripped = stripped[:-2].strip()
        transpose = True
    elif stripped.endswith(r"^{\top}"):
        stripped = stripped[: -len(r"^{\top}")].strip()
        transpose = True
    elif stripped.endswith(r"^\top"):
        stripped = stripped[: -len(r"^\top")].strip()
        transpose = True

    if not (stripped.startswith("[") and stripped.endswith("]")):
        return None
    inner = stripped[1:-1].strip()
    if not inner:
        raise UnsupportedSyntaxError("Empty matrix/vector literal is unsupported.")
    row_texts = _split_top_level(inner, row_delimiter=";")
    if len(row_texts) == 1:
        row = tuple(entry.strip() for entry in _split_top_level(row_texts[0], row_delimiter=","))
        parsed_rows = (row,)
    else:
        parsed_rows = tuple(
            tuple(entry.strip() for entry in _split_top_level(row_text, row_delimiter=","))
            for row_text in row_texts
        )
    matrix = _validate_matrix_rows(parsed_rows)
    return matrix.transpose() if transpose else matrix


def _validate_matrix_rows(rows: tuple[tuple[str, ...], ...]) -> MatrixValue:
    if not rows or not rows[0]:
        raise UnsupportedSyntaxError("Empty matrix/vector literal is unsupported.")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise UnsupportedSyntaxError("Matrix rows must have consistent widths.")
    if any(not entry for row in rows for entry in row):
        raise UnsupportedSyntaxError("Matrix entries may not be empty.")
    return MatrixValue(rows)


def _split_top_level(text: str, *, row_delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    i = 0
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    while i < len(text):
        env_end = _consume_matrix_environment(text, i)
        if env_end is not None:
            i = env_end
            continue
        char = text[i]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)

        if paren_depth == brace_depth == bracket_depth == 0 and text.startswith(row_delimiter, i):
            parts.append(text[start:i].strip())
            i += len(row_delimiter)
            start = i
            continue
        i += 1
    parts.append(text[start:].strip())
    return parts


def _consume_scalar_segment(term: str, start: int, context: dict[str, MatrixValue]) -> int:
    i = start
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    while i < len(term):
        if paren_depth == brace_depth == bracket_depth == 0:
            if term[i] == "*":
                break
            if _matrix_literal_end(term, i) is not None and i != start:
                break
            if _match_vector_derivative(term, i, context) is not None and i != start:
                break
            if _match_matrix_symbol(term, i, context) is not None and i != start:
                break
        env_end = _consume_matrix_environment(term, i)
        if env_end is not None:
            i = env_end
            continue
        char = term[i]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        i += 1
    return i


def _matrix_literal_end(text: str, start: int) -> int | None:
    env_end = _consume_matrix_environment(text, start)
    if env_end is not None:
        return env_end
    if start < len(text) and text[start] == "[":
        end = _consume_balanced(text, start, "[", "]")
        if end is None:
            raise UnsupportedSyntaxError("Unterminated square-bracket matrix/vector literal.")
        transpose_end = _consume_transpose_suffix(text, end)
        return transpose_end
    return None


def _consume_matrix_environment(text: str, start: int) -> int | None:
    match = _MATRIX_ENV_START_RE.match(text, start)
    if match is None:
        return None
    env = match.group("env")
    if env not in _MATRIX_ENVIRONMENTS:
        return None
    end_tag = rf"\end{{{env}}}"
    end = text.find(end_tag, match.end())
    if end == -1:
        raise UnsupportedSyntaxError(f"Unterminated matrix environment {env!r}.")
    return end + len(end_tag)


def _consume_balanced(text: str, start: int, opening: str, closing: str) -> int | None:
    depth = 0
    i = start
    while i < len(text):
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def _consume_transpose_suffix(text: str, start: int) -> int:
    for suffix in (r"^{\top}", r"^\top", "^{T}", "^T"):
        if text.startswith(suffix, start):
            return start + len(suffix)
    return start


def _match_vector_derivative(text: str, start: int, context: dict[str, MatrixValue]) -> tuple[int, MatrixValue] | None:
    for regex in (_DOT_VECTOR_RE, _GENERAL_DERIV_RE):
        match = regex.match(text, start)
        if match is None:
            continue
        symbol_name = match.group("symbol")
        if symbol_name not in context:
            return None
        if "order" in match.groupdict() and match.group("order") is not None:
            order = int(match.group("order"))
        else:
            order = 1 if match.group("command") == "dot" else 2
        return match.end(), _apply_derivative(context[symbol_name], order)
    return None


def _match_matrix_symbol(text: str, start: int, context: dict[str, MatrixValue]) -> tuple[int, MatrixValue] | None:
    for name in sorted(context, key=len, reverse=True):
        if text.startswith(name, start):
            end = start + len(name)
            if end < len(text) and (text[end].isalnum() or text[end] == "_"):
                if _match_vector_derivative(text, end, context) is None and _match_matrix_symbol(text, end, context) is None:
                    continue
            return end, context[name]
    return None


def _add_matrices(left: MatrixValue, right: MatrixValue) -> MatrixValue:
    if left.shape != right.shape:
        raise UnsupportedSyntaxError(f"Cannot add matrices of shapes {left.shape} and {right.shape}.")
    return MatrixValue(
        tuple(
            tuple(_combine_add(left.rows[row][col], right.rows[row][col]) for col in range(left.col_count))
            for row in range(left.row_count)
        )
    )


def _scale_matrix(scalar: str, value: MatrixValue) -> MatrixValue:
    return MatrixValue(
        tuple(
            tuple(_combine_mul(scalar, entry) for entry in row)
            for row in value.rows
        )
    )


def _multiply_values(left: MatrixValue, right: MatrixValue) -> MatrixValue:
    if left.is_scalar():
        return _scale_matrix(left.scalar(), right)
    if right.is_scalar():
        return _scale_matrix(right.scalar(), left)
    if left.col_count != right.row_count:
        raise UnsupportedSyntaxError(
            f"Cannot multiply matrices of shapes {left.shape} and {right.shape}."
        )
    rows: list[tuple[str, ...]] = []
    for row in range(left.row_count):
        result_row: list[str] = []
        for col in range(right.col_count):
            terms = [
                _combine_mul(left.rows[row][shared], right.rows[shared][col])
                for shared in range(left.col_count)
            ]
            result_row.append(_sum_terms(terms))
        rows.append(tuple(result_row))
    return MatrixValue(tuple(rows))


def _sum_terms(terms: list[str]) -> str:
    result = "0"
    for term in terms:
        result = _combine_add(result, term)
    return result


def _combine_add(left: str, right: str) -> str:
    left = left.strip()
    right = right.strip()
    if left == "0":
        return right
    if right == "0":
        return left
    return f"({left}) + ({right})"


def _combine_mul(left: str, right: str) -> str:
    left = left.strip()
    right = right.strip()
    if left == "0" or right == "0":
        return "0"
    if left == "1":
        return right
    if right == "1":
        return left
    if left == "-1":
        return f"-({right})"
    if right == "-1":
        return f"-({left})"
    return f"({left})*({right})"
