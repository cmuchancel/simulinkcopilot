"""Shared front-door normalization for LaTeX and MATLAB-native inputs."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

import sympy
from sympy.parsing.sympy_parser import convert_xor, parse_expr, standard_transformations

from ir.equation_dict import sympy_function_locals, sympy_to_equation
from latex_frontend.symbols import DeterministicCompileError, derivative_symbol_name
from latex_frontend.translator import translate_file, translate_latex
from pipeline.normalized_problem import NormalizedProblem, build_normalized_problem


_PARSE_TRANSFORMATIONS = standard_transformations + (convert_xor,)
_SYMPY_PARSE_LOCALS = sympy_function_locals()
_SYMPY_PARSE_LOCALS.update(
    {
        "Abs": sympy.Abs,
        "heaviside": sympy.Heaviside,
        "Heaviside": sympy.Heaviside,
        "Min": sympy.Min,
        "Max": sympy.Max,
    }
)
_IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*\b")
_DIFF_PATTERN = re.compile(
    r"diff\(\s*(?P<base>[A-Za-z][A-Za-z0-9_]*)\s*,\s*(?P<time>[A-Za-z][A-Za-z0-9_]*)\s*(?:,\s*(?P<order>\d+)\s*)?\)"
)
_TIME_DEPENDENT_DIFF_PATTERN = re.compile(
    r"diff\(\s*(?P<base>[A-Za-z][A-Za-z0-9_]*)\(\s*(?P<func_time>[A-Za-z][A-Za-z0-9_]*)\s*\)\s*,\s*(?P<args>[^)]*?)\)"
)
_TIME_DEPENDENT_SYMBOL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?P<base>[A-Za-z][A-Za-z0-9_]*)\(\s*(?P<time>[A-Za-z][A-Za-z0-9_]*)\s*\)"
)
_KNOWN_FUNCTION_NAMES = set(_SYMPY_PARSE_LOCALS)


def normalize_problem(input_payload: Mapping[str, object] | NormalizedProblem) -> NormalizedProblem:
    """Normalize any supported front-door payload into a shared problem schema."""
    if isinstance(input_payload, NormalizedProblem):
        return input_payload
    if not isinstance(input_payload, Mapping):
        raise DeterministicCompileError("normalize_problem expects a mapping payload or NormalizedProblem.")

    source_type_raw = input_payload.get("source_type")
    if not isinstance(source_type_raw, str) or not source_type_raw.strip():
        raise DeterministicCompileError("Input payload must declare a non-empty source_type.")
    source_type = source_type_raw.strip()

    if source_type == "latex":
        return normalize_from_latex(input_payload)
    if source_type == "matlab_symbolic":
        return normalize_from_matlab_symbolic(input_payload)
    if source_type == "matlab_equation_text":
        return normalize_from_matlab_equation_text(input_payload)
    if source_type == "matlab_ode_function":
        return normalize_from_matlab_ode_function(input_payload)
    raise DeterministicCompileError(
        "Unsupported source_type "
        f"{source_type!r}. Expected one of ['latex', 'matlab_equation_text', 'matlab_ode_function', 'matlab_symbolic']."
    )


def normalize_from_latex(input_payload: Mapping[str, object]) -> NormalizedProblem:
    """Normalize LaTeX text or file input into the shared problem schema."""
    if "path" in input_payload:
        path = _require_string(input_payload, "path")
        equations = translate_file(path)
        source_metadata = {
            "path": str(Path(path).resolve()),
            "name": input_payload.get("name", Path(path).stem),
        }
        original_texts = None
    else:
        text = _extract_text_document(input_payload, field="text")
        equations = translate_latex(text)
        source_metadata = {"name": input_payload.get("name", "inline_equations")}
        display_path = input_payload.get("display_path")
        if isinstance(display_path, str) and display_path.strip():
            source_metadata["display_path"] = display_path
        original_texts = None

    return build_normalized_problem(
        source_type="latex",
        equations=equations,
        original_texts=original_texts,
        source_metadata=source_metadata,
        time_variable=_optional_string(input_payload, "time_variable"),
        states=_optional_name_list(input_payload, "states", "state_names"),
        algebraics=_optional_name_list(input_payload, "algebraics", "algebraic_names"),
        inputs=_optional_name_list(input_payload, "inputs", "input_names"),
        parameters=_optional_name_list(input_payload, "parameters", "parameter_names"),
        assumptions=_optional_mapping(input_payload, "assumptions"),
    )


def normalize_from_latex_path(path: str | Path) -> NormalizedProblem:
    """Normalize a LaTeX file path into the shared problem schema."""
    return normalize_from_latex({"source_type": "latex", "path": str(path)})


def normalize_from_latex_text(
    text: str,
    *,
    name: str = "inline_equations",
    assumptions: Mapping[str, object] | None = None,
) -> NormalizedProblem:
    """Normalize inline LaTeX text into the shared problem schema."""
    payload: dict[str, object] = {
        "source_type": "latex",
        "text": text,
        "name": name,
        "display_path": f"{name}.tex",
    }
    if assumptions is not None:
        payload["assumptions"] = dict(assumptions)
    return normalize_from_latex(payload)


def normalize_from_matlab_symbolic(input_payload: Mapping[str, object]) -> NormalizedProblem:
    """Normalize MATLAB symbolic-style equation strings into the shared problem schema."""
    raw_equations = _coerce_equation_list(input_payload, "equations")
    declared_time = _optional_string(input_payload, "time_variable")
    rewritten_equations, inferred_time = _rewrite_symbolic_diff_equations(
        raw_equations,
        declared_time,
        source_type="matlab_symbolic",
    )
    equations = [
        _parse_equation_text(
            equation_text,
            source_type="matlab_symbolic",
            states=_optional_name_list(input_payload, "states", "state_names"),
            time_variable=declared_time or inferred_time,
        )
        for equation_text in rewritten_equations
    ]
    return build_normalized_problem(
        source_type="matlab_symbolic",
        equations=equations,
        original_texts=raw_equations,
        source_metadata={"name": input_payload.get("name", "matlab_symbolic")},
        time_variable=declared_time or inferred_time,
        states=_optional_name_list(input_payload, "states", "state_names"),
        algebraics=_optional_name_list(input_payload, "algebraics", "algebraic_names"),
        inputs=_optional_name_list(input_payload, "inputs", "input_names"),
        parameters=_optional_name_list(input_payload, "parameters", "parameter_names"),
        assumptions=_optional_mapping(input_payload, "assumptions"),
    )


def normalize_from_matlab_equation_text(input_payload: Mapping[str, object]) -> NormalizedProblem:
    """Normalize MATLAB-ish equation text into the shared problem schema."""
    states = _optional_name_list(input_payload, "states", "state_names")
    time_variable = _optional_string(input_payload, "time_variable")
    derivative_map = _load_derivative_map(
        input_payload.get("derivative_map"),
        states=states,
        time_variable=time_variable,
    )
    raw_equations = _coerce_equation_list(input_payload, "equations")
    equations = [
        _parse_equation_text(
            equation_text,
            source_type="matlab_equation_text",
            states=states,
            time_variable=time_variable,
            derivative_map=derivative_map,
        )
        for equation_text in raw_equations
    ]
    return build_normalized_problem(
        source_type="matlab_equation_text",
        equations=equations,
        original_texts=raw_equations,
        source_metadata={"name": input_payload.get("name", "matlab_equation_text")},
        time_variable=time_variable,
        states=states,
        algebraics=_optional_name_list(input_payload, "algebraics", "algebraic_names"),
        inputs=_optional_name_list(input_payload, "inputs", "input_names"),
        parameters=_optional_name_list(input_payload, "parameters", "parameter_names"),
        assumptions=_optional_mapping(input_payload, "assumptions"),
    )


def normalize_from_matlab_ode_function(input_payload: Mapping[str, object]) -> NormalizedProblem:
    """Normalize a structured MATLAB ODE-function export into the shared problem schema."""
    function_spec = input_payload.get("function_spec")
    if not isinstance(function_spec, Mapping):
        raise DeterministicCompileError(
            "matlab_ode_function currently requires a structured exported specification in function_spec."
        )

    representation = function_spec.get("representation")
    if representation == "opaque_function_handle":
        raise DeterministicCompileError(
            "matlab_ode_function currently supports only structured exported RHS expressions, "
            "not opaque function handles or arbitrary MATLAB source."
        )
    if not isinstance(representation, str) or not representation.strip():
        raise DeterministicCompileError("matlab_ode_function function_spec must declare a representation.")

    states = _optional_name_list(input_payload, "states", "state_names")
    inputs = _optional_name_list(input_payload, "inputs", "input_names")
    parameters = _optional_name_list(input_payload, "parameters", "parameter_names")
    time_variable = _optional_string(input_payload, "time_variable")

    if representation == "component_expressions":
        equations = _normalize_component_expression_ode_function(
            function_spec,
            states=states,
            inputs=inputs,
            parameters=parameters,
            time_variable=time_variable,
        )
    elif representation == "vector_rhs":
        equations = _normalize_vector_rhs_ode_function(
            function_spec,
            states=states,
            inputs=inputs,
            parameters=parameters,
            time_variable=time_variable,
        )
    else:
        raise DeterministicCompileError(
            f"matlab_ode_function representation {representation!r} is unsupported. "
            "Supported representations: component_expressions, vector_rhs."
        )

    return build_normalized_problem(
        source_type="matlab_ode_function",
        equations=equations,
        original_texts=None,
        source_metadata={"name": input_payload.get("name", "matlab_ode_function")},
        time_variable=time_variable,
        states=states,
        algebraics=_optional_name_list(input_payload, "algebraics", "algebraic_names"),
        inputs=inputs,
        parameters=parameters,
        assumptions=_optional_mapping(input_payload, "assumptions"),
    )


def _normalize_component_expression_ode_function(
    function_spec: Mapping[str, object],
    *,
    states: tuple[str, ...],
    inputs: tuple[str, ...],
    parameters: tuple[str, ...],
    time_variable: str | None,
):
    if not states:
        raise DeterministicCompileError(
            "matlab_ode_function component_expressions requires explicit states/state_names metadata."
        )
    expressions = _require_string_list(function_spec, "expressions")
    outputs = _optional_name_list(function_spec, "outputs")
    if len(expressions) != len(states):
        raise DeterministicCompileError(
            "matlab_ode_function component_expressions requires one RHS expression per declared state."
        )
    if outputs and len(outputs) != len(expressions):
        raise DeterministicCompileError(
            "matlab_ode_function component_expressions outputs must match the RHS expression count."
        )

    equations = []
    for index, expression_text in enumerate(expressions):
        state_name = states[index]
        if outputs and not _output_matches_state(outputs[index], state_name, time_variable):
            raise DeterministicCompileError(
                "matlab_ode_function component_expressions output "
                f"{outputs[index]!r} does not match the derivative of declared state {state_name!r}."
            )
        equations.append(
            _parse_equation_text(
                f"{derivative_symbol_name(state_name, 1)} = {expression_text}",
                source_type="matlab_ode_function",
                states=states,
                time_variable=time_variable,
                derivative_map={},
            )
        )
    return equations


def _normalize_vector_rhs_ode_function(
    function_spec: Mapping[str, object],
    *,
    states: tuple[str, ...],
    inputs: tuple[str, ...],
    parameters: tuple[str, ...],
    time_variable: str | None,
):
    if not states:
        raise DeterministicCompileError(
            "matlab_ode_function vector_rhs requires explicit state_names/states metadata."
        )
    rhs_entries = _require_string_list(function_spec, "rhs")
    if len(rhs_entries) != len(states):
        raise DeterministicCompileError("matlab_ode_function vector_rhs requires one RHS entry per declared state.")

    state_vector_name = _require_string(function_spec, "state_vector_name")
    input_vector_name = _optional_string(function_spec, "input_vector_name")
    parameter_vector_name = _optional_string(function_spec, "parameter_vector_name")

    equations = []
    for index, rhs_text in enumerate(rhs_entries):
        rewritten_rhs = _replace_vector_references(rhs_text, state_vector_name, states, source_type="matlab_ode_function")
        if input_vector_name is not None:
            rewritten_rhs = _replace_vector_references(
                rewritten_rhs,
                input_vector_name,
                inputs,
                source_type="matlab_ode_function",
            )
        if parameter_vector_name is not None:
            rewritten_rhs = _replace_vector_references(
                rewritten_rhs,
                parameter_vector_name,
                parameters,
                source_type="matlab_ode_function",
            )
        equations.append(
            _parse_equation_text(
                f"{derivative_symbol_name(states[index], 1)} = {rewritten_rhs}",
                source_type="matlab_ode_function",
                states=states,
                time_variable=time_variable,
                derivative_map={},
            )
        )
    return equations


def _parse_equation_text(
    equation_text: str,
    *,
    source_type: str,
    states: Sequence[str] = (),
    time_variable: str | None = None,
    derivative_map: Mapping[str, tuple[str, int]] | None = None,
):
    lhs_text, rhs_text = _split_equation(equation_text, source_type=source_type)
    alias_map = _build_derivative_alias_map(
        states=tuple(states),
        time_variable=time_variable,
        derivative_map=derivative_map,
    )
    lhs_expr = _parse_math_expression(
        lhs_text,
        source_type=source_type,
        alias_map=alias_map,
        time_variable=time_variable,
    )
    rhs_expr = _parse_math_expression(
        rhs_text,
        source_type=source_type,
        alias_map=alias_map,
        time_variable=time_variable,
    )
    return sympy_to_equation(lhs_expr, rhs_expr)


def _parse_math_expression(
    expression_text: str,
    *,
    source_type: str,
    alias_map: Mapping[str, str],
    time_variable: str | None,
) -> sympy.Expr:
    rewritten = expression_text.strip()
    rewritten = _replace_identifier_aliases(
        rewritten,
        alias_map,
        source_type=source_type,
        time_variable=time_variable,
    )
    try:
        return parse_expr(
            rewritten,
            local_dict=dict(_SYMPY_PARSE_LOCALS),
            transformations=_PARSE_TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:  # pragma: no cover - precise message path is exercised in tests
        raise DeterministicCompileError(
            f"{source_type} parse failed: could not parse expression {expression_text!r}."
        ) from exc


def _rewrite_symbolic_diff_equations(
    equations: list[str],
    declared_time: str | None,
    *,
    source_type: str,
) -> tuple[list[str], str | None]:
    inferred_times: set[str] = set()
    rewritten: list[str] = []
    for equation_text in equations:
        rewritten_text = _rewrite_time_dependent_diff_calls(
            equation_text,
            declared_time,
            inferred_times,
            source_type=source_type,
        )
        while True:
            match = _DIFF_PATTERN.search(rewritten_text)
            if match is None:
                break
            base = match.group("base")
            time_name = match.group("time")
            order = int(match.group("order") or 1)
            if declared_time is not None and time_name != declared_time:
                raise DeterministicCompileError(
                    f"{source_type} parse failed: diff() uses time variable {time_name!r}, "
                    f"but payload declares {declared_time!r}."
                )
            inferred_times.add(time_name)
            rewritten_text = (
                rewritten_text[: match.start()]
                + derivative_symbol_name(base, order)
                + rewritten_text[match.end() :]
            )
        rewritten.append(rewritten_text)
    if len(inferred_times) > 1:
        raise DeterministicCompileError(
            f"{source_type} parse failed: diff() uses multiple time variables {sorted(inferred_times)}."
        )
    inferred_time = next(iter(inferred_times)) if inferred_times else None
    resolved_time = declared_time or inferred_time
    if resolved_time is not None:
        rewritten = [
            _rewrite_time_dependent_symbol_calls(equation_text, resolved_time)
            for equation_text in rewritten
        ]
    return rewritten, resolved_time


def _rewrite_time_dependent_symbol_calls(equation_text: str, time_variable: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        base = match.group("base")
        time_name = match.group("time")
        if time_name != time_variable or base in _KNOWN_FUNCTION_NAMES:
            return match.group(0)
        return base

    return _TIME_DEPENDENT_SYMBOL_PATTERN.sub(_replace, equation_text)


def _rewrite_time_dependent_diff_calls(
    equation_text: str,
    declared_time: str | None,
    inferred_times: set[str],
    *,
    source_type: str,
) -> str:
    def _replace(match: re.Match[str]) -> str:
        base = match.group("base")
        func_time = match.group("func_time")
        args = [entry.strip() for entry in match.group("args").split(",") if entry.strip()]
        if not args:
            raise DeterministicCompileError(
                f"{source_type} parse failed: diff() on {base!r} is missing a time variable."
            )

        if declared_time is not None and func_time != declared_time:
            raise DeterministicCompileError(
                f"{source_type} parse failed: symbolic function {base}({func_time}) uses time variable {func_time!r}, "
                f"but payload declares {declared_time!r}."
            )

        derivative_time = args[0]
        if derivative_time != func_time:
            raise DeterministicCompileError(
                f"{source_type} parse failed: diff() on {base}({func_time}) differentiates with respect to {derivative_time!r}."
            )

        if len(args) == 1:
            order = 1
        elif len(args) == 2 and args[1].isdigit():
            order = int(args[1])
        else:
            if any(entry != func_time for entry in args[1:]):
                raise DeterministicCompileError(
                    f"{source_type} parse failed: unsupported diff() signature {match.group(0)!r}."
                )
            order = len(args)

        inferred_times.add(func_time)
        return derivative_symbol_name(base, order)

    return _TIME_DEPENDENT_DIFF_PATTERN.sub(_replace, equation_text)


def _split_equation(text: str, *, source_type: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        raise DeterministicCompileError(f"{source_type} parse failed: encountered an empty equation.")
    if "==" in stripped:
        if stripped.count("==") != 1:
            raise DeterministicCompileError(
                f"{source_type} parse failed: equations must contain exactly one equality operator."
            )
        lhs, rhs = stripped.split("==", 1)
    elif "=" in stripped:
        if stripped.count("=") != 1:
            raise DeterministicCompileError(
                f"{source_type} parse failed: equations must contain exactly one equality operator."
            )
        lhs, rhs = stripped.split("=", 1)
    else:
        raise DeterministicCompileError(
            f"{source_type} parse failed: equation {text!r} is missing '=' or '=='."
        )
    if not lhs.strip() or not rhs.strip():
        raise DeterministicCompileError(
            f"{source_type} parse failed: equation {text!r} must have non-empty lhs and rhs."
        )
    return lhs.strip(), rhs.strip()


def _build_derivative_alias_map(
    *,
    states: tuple[str, ...],
    time_variable: str | None,
    derivative_map: Mapping[str, tuple[str, int]] | None = None,
) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for state_name in states:
        alias_map[f"{state_name}dot"] = derivative_symbol_name(state_name, 1)
        alias_map[f"{state_name}_dot"] = derivative_symbol_name(state_name, 1)
        if time_variable is not None:
            alias_map[f"d{state_name}d{time_variable}"] = derivative_symbol_name(state_name, 1)
    for alias, target in (derivative_map or {}).items():
        alias_map[alias] = derivative_symbol_name(target[0], target[1])
    return alias_map


def _replace_identifier_aliases(
    text: str,
    alias_map: Mapping[str, str],
    *,
    source_type: str,
    time_variable: str | None,
) -> str:
    ambiguous_tokens = sorted(
        {
            token
            for token in _IDENTIFIER_PATTERN.findall(text)
            if _looks_like_derivative_alias(token) and token not in alias_map
        }
    )
    if ambiguous_tokens:
        token = ambiguous_tokens[0]
        raise DeterministicCompileError(
            f"{source_type} parse failed: could not determine whether {token!r} is a state derivative or an ordinary variable; "
            "provide explicit states/derivative map."
        )

    rewritten = text
    for alias in sorted(alias_map, key=len, reverse=True):
        rewritten = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(alias)}(?![A-Za-z0-9_])",
            alias_map[alias],
            rewritten,
        )
    return rewritten


def _looks_like_derivative_alias(token: str) -> bool:
    return bool(
        token.endswith("dot")
        or token.endswith("_dot")
        or re.match(r"^d[A-Za-z][A-Za-z0-9_]*d[A-Za-z][A-Za-z0-9_]*$", token)
    )


def _load_derivative_map(
    raw_map: object,
    *,
    states: tuple[str, ...],
    time_variable: str | None,
) -> dict[str, tuple[str, int]]:
    if raw_map is None:
        return {}
    if not isinstance(raw_map, Mapping):
        raise DeterministicCompileError("derivative_map must be a mapping of alias -> state or alias -> {base, order}.")

    normalized: dict[str, tuple[str, int]] = {}
    state_set = set(states)
    for alias, raw_target in raw_map.items():
        if not isinstance(alias, str) or not alias.strip():
            raise DeterministicCompileError(f"Invalid derivative_map alias {alias!r}.")
        if isinstance(raw_target, str):
            base = raw_target
            order = 1
        elif isinstance(raw_target, Mapping):
            base = raw_target.get("base")
            order = int(raw_target.get("order", 1))
        else:
            raise DeterministicCompileError(
                f"derivative_map entry for {alias!r} must be a state name or mapping with base/order."
            )
        if not isinstance(base, str) or not base.strip():
            raise DeterministicCompileError(f"derivative_map entry for {alias!r} is missing a valid base state name.")
        if state_set and base not in state_set:
            raise DeterministicCompileError(
                f"derivative_map entry for {alias!r} targets undeclared state {base!r}."
            )
        normalized[alias] = (base, order)
    return normalized


def _replace_vector_references(
    text: str,
    vector_name: str,
    names: Sequence[str],
    *,
    source_type: str,
) -> str:
    if not names:
        return text

    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(vector_name)}\(\s*(?P<index>\d+)\s*\)")

    def _replace(match: re.Match[str]) -> str:
        index = int(match.group("index"))
        if index < 1 or index > len(names):
            raise DeterministicCompileError(
                f"{source_type} parse failed: {vector_name}({index}) is out of range for declared names {list(names)}."
            )
        return names[index - 1]

    return pattern.sub(_replace, text)


def _output_matches_state(output_name: str, state_name: str, time_variable: str | None) -> bool:
    expected = {
        f"{state_name}dot",
        f"{state_name}_dot",
        f"d{state_name}",
    }
    if time_variable is not None:
        expected.add(f"d{state_name}d{time_variable}")
    return output_name in expected


def _extract_text_document(payload: Mapping[str, object], *, field: str) -> str:
    raw = payload.get(field)
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        parts = []
        for index, item in enumerate(raw):
            if not isinstance(item, str):
                raise DeterministicCompileError(
                    f"{field} entry at index {index} must be a string."
                )
            stripped = item.strip()
            if stripped:
                parts.append(stripped)
        if not parts:
            raise DeterministicCompileError(f"{field} must contain at least one non-empty equation string.")
        return "\n".join(parts)
    raise DeterministicCompileError(f"{field} must be a string or list of equation strings.")


def _coerce_equation_list(payload: Mapping[str, object], field: str) -> list[str]:
    raw = payload.get(field)
    if raw is None and field == "equations" and "text" in payload:
        raw = payload.get("text")
    if isinstance(raw, str):
        equations = [line.strip() for line in raw.splitlines() if line.strip()]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        equations = []
        for index, item in enumerate(raw):
            if not isinstance(item, str):
                raise DeterministicCompileError(f"{field} entry at index {index} must be a string.")
            stripped = item.strip()
            if stripped:
                equations.append(stripped)
    else:
        raise DeterministicCompileError(f"{field} must be a string or list of equation strings.")
    if not equations:
        raise DeterministicCompileError(f"{field} must contain at least one non-empty equation string.")
    return equations


def _optional_name_list(payload: Mapping[str, object], *keys: str) -> tuple[str, ...]:
    for key in keys:
        if key not in payload:
            continue
        raw = payload[key]
        if raw is None:
            return ()
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise DeterministicCompileError(f"{key} must be a list of symbol names.")
        names: list[str] = []
        for index, item in enumerate(raw):
            if not isinstance(item, str) or not item.strip():
                raise DeterministicCompileError(f"{key} entry at index {index} must be a non-empty string.")
            names.append(item.strip())
        return tuple(names)
    return ()


def _optional_mapping(payload: Mapping[str, object], key: str) -> dict[str, object] | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise DeterministicCompileError(f"{key} must be a mapping.")
    return dict(raw)


def _optional_string(payload: Mapping[str, object], key: str) -> str | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise DeterministicCompileError(f"{key} must be a non-empty string.")
    return raw.strip()


def _require_string(payload: Mapping[str, object], key: str) -> str:
    value = _optional_string(payload, key)
    if value is None:
        raise DeterministicCompileError(f"{key} is required.")
    return value


def _require_string_list(payload: Mapping[str, object], key: str) -> list[str]:
    raw = payload.get(key)
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise DeterministicCompileError(f"{key} must be a list of strings.")
    values: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise DeterministicCompileError(f"{key} entry at index {index} must be a non-empty string.")
        values.append(item.strip())
    if not values:
        raise DeterministicCompileError(f"{key} must contain at least one string.")
    return values
