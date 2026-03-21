"""Deterministic lowering from linear descriptor systems to Simulink model dictionaries."""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy

from backend.block_library import BLOCK_LIBRARY
from backend.layout import apply_deterministic_layout
from backend.simulink_dict import BackendSimulinkModelDict, ROOT_SYSTEM, validate_simulink_model_dict
from ir.equation_dict import matrix_from_dict
from latex_frontend.symbols import DeterministicCompileError
from simulink.utils import sanitize_block_name


def _sanitize(name: str) -> str:
    return sanitize_block_name(name)


def _numeric_string(value: sympy.Expr) -> str:
    simplified = sympy.simplify(value)
    if simplified.is_Integer:
        return str(int(simplified))
    return sympy.sstr(simplified)


@dataclass
class DescriptorToSimulinkLowerer:
    descriptor_system: dict[str, object]
    model_name: str
    parameter_values: dict[str, float] = field(default_factory=dict)
    input_values: dict[str, float] = field(default_factory=dict)
    input_signals: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    differential_initial_conditions: dict[str, float] = field(default_factory=dict)
    algebraic_initial_conditions: dict[str, float] = field(default_factory=dict)
    blocks: dict[str, dict[str, object]] = field(default_factory=dict)
    connections: list[dict[str, object]] = field(default_factory=list)
    workspace_variables: dict[str, object] = field(default_factory=dict)
    sources: dict[str, tuple[str, str]] = field(default_factory=dict)
    counter: int = 0

    def __post_init__(self) -> None:
        if self.descriptor_system.get("form") != "linear_descriptor":
            raise DeterministicCompileError("Descriptor lowering requires a linear_descriptor system.")

        self.differential_states = list(self.descriptor_system["differential_states"])  # type: ignore[index]
        self.algebraic_variables = list(self.descriptor_system["algebraic_variables"])  # type: ignore[index]
        self.variables = list(self.descriptor_system["variables"])  # type: ignore[index]
        self.inputs = list(self.descriptor_system["inputs"])  # type: ignore[index]
        self.independent_variable = self.descriptor_system.get("independent_variable")

        substitutions = {
            sympy.Symbol(name): sympy.Float(float(value))
            for name, value in self.parameter_values.items()
        }
        self.E = self._substitute_matrix(matrix_from_dict(self.descriptor_system["E"]), substitutions)  # type: ignore[arg-type]
        self.A = self._substitute_matrix(matrix_from_dict(self.descriptor_system["A"]), substitutions)  # type: ignore[arg-type]
        self.B = self._substitute_matrix(matrix_from_dict(self.descriptor_system["B"]), substitutions)  # type: ignore[arg-type]
        self.offset = self._substitute_matrix(matrix_from_dict(self.descriptor_system["offset"]), substitutions)  # type: ignore[arg-type]

        self._validate_descriptor_shape()
        self._validate_coefficients()
        self.algebraic_row_assignment = self._match_algebraic_rows()

    def _next_id(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}_{self.counter:04d}"

    def _substitute_matrix(self, matrix: sympy.Matrix, substitutions: dict[sympy.Symbol, sympy.Expr]) -> sympy.Matrix:
        return sympy.Matrix(
            [
                [sympy.simplify(matrix[row, col].subs(substitutions, simultaneous=True)) for col in range(matrix.cols)]
                for row in range(matrix.rows)
            ]
        )

    def _validate_descriptor_shape(self) -> None:
        equation_count = len(self.variables)
        if self.E.rows != equation_count or self.A.rows != equation_count:
            raise DeterministicCompileError("Descriptor system must have one equation row per variable.")
        if self.E.cols != len(self.variables):
            raise DeterministicCompileError("Descriptor E matrix width must match total variable count.")
        if self.A.cols != len(self.variables):
            raise DeterministicCompileError("Descriptor A matrix width must match total variable count.")
        if self.B.rows != equation_count:
            raise DeterministicCompileError("Descriptor B matrix row count must match equation count.")
        if self.offset.rows != equation_count or self.offset.cols != 1:
            raise DeterministicCompileError("Descriptor offset must be a column vector with one entry per equation.")

    def _validate_coefficients(self) -> None:
        allowed_symbols = set()
        if self.independent_variable is not None:
            allowed_symbols.add(str(self.independent_variable))
        for matrix_name, matrix in [("E", self.E), ("A", self.A), ("B", self.B), ("offset", self.offset)]:
            for entry in matrix:
                unresolved = sorted(symbol.name for symbol in entry.free_symbols if symbol.name not in allowed_symbols)
                if unresolved:
                    raise DeterministicCompileError(
                        f"Descriptor {matrix_name} retains unsupported symbolic coefficients: {unresolved}."
                    )
        if self.independent_variable is not None:
            raise DeterministicCompileError(
                "Descriptor-to-Simulink lowering currently supports time-invariant descriptor systems only."
            )

    def _match_algebraic_rows(self) -> dict[int, int]:
        row_count = len(self.algebraic_variables)
        if row_count == 0:
            return {}

        row_indices = list(range(len(self.differential_states), len(self.variables)))
        col_indices = list(range(len(self.differential_states), len(self.variables)))
        adjacency: dict[int, list[int]] = {}
        for row_position, row_index in enumerate(row_indices):
            adjacency[row_position] = [
                col_position
                for col_position, col_index in enumerate(col_indices)
                if sympy.simplify(self.A[row_index, col_index]) != 0
            ]

        matches: dict[int, int] = {}

        def _assign(row_position: int, seen: set[int]) -> bool:
            for col_position in adjacency[row_position]:
                if col_position in seen:
                    continue
                seen.add(col_position)
                current_row = matches.get(col_position)
                if current_row is None or _assign(current_row, seen):
                    matches[col_position] = row_position
                    return True
            return False

        for row_position in range(row_count):
            if not _assign(row_position, set()):
                raise DeterministicCompileError(
                    "Descriptor algebraic subsystem lacks a deterministic row-to-variable assignment."
                )

        assignment: dict[int, int] = {}
        for col_position, row_position in matches.items():
            assignment[col_indices[col_position]] = row_indices[row_position]
        return assignment

    def add_block(
        self,
        block_id: str,
        block_type: str,
        *,
        name: str,
        params: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        if block_id not in self.blocks:
            self.blocks[block_id] = {
                "type": block_type,
                "lib_path": BLOCK_LIBRARY[block_type]["path"],
                "system": ROOT_SYSTEM,
                "name": name,
                "params": dict(params or {}),
                "metadata": dict(metadata or {}),
            }
        return block_id

    def add_connection(
        self,
        src: tuple[str, str],
        dst_block: str,
        dst_port: int,
        *,
        label: str,
    ) -> None:
        self.connections.append(
            {
                "system": ROOT_SYSTEM,
                "src_block": src[0],
                "src_port": src[1],
                "dst_block": dst_block,
                "dst_port": str(dst_port),
                "label": label,
                "metadata": {},
            }
        )

    def _constant_source(self, value: sympy.Expr, *, name: str, layer_hint: int) -> tuple[str, str]:
        block_id = self.add_block(
            self._next_id("const"),
            "Constant",
            name=name,
            params={"Value": _numeric_string(value)},
            metadata={"layout_role": "shared", "layer_hint": layer_hint, "trace_expression": _numeric_string(value)},
        )
        return (block_id, "1")

    def _apply_gain(self, source: tuple[str, str], coefficient: sympy.Expr, *, trace: str, layer_hint: int) -> tuple[str, str]:
        simplified = sympy.simplify(coefficient)
        if simplified == 1:
            return source
        block_id = self.add_block(
            self._next_id("gain"),
            "Gain",
            name=f"gain_{_sanitize(trace)}",
            params={"Gain": _numeric_string(simplified)},
            metadata={"layout_role": "shared", "layer_hint": layer_hint, "trace_expression": f"{_numeric_string(simplified)}*{trace}"},
        )
        self.add_connection(source, block_id, 1, label=trace)
        return (block_id, "1")

    def _sum_terms(
        self,
        terms: list[tuple[tuple[str, str], str]],
        *,
        trace_expression: str,
        layer_hint: int,
    ) -> tuple[str, str]:
        if not terms:
            return self._constant_source(sympy.Integer(0), name="zero", layer_hint=layer_hint)
        if len(terms) == 1:
            return terms[0][0]
        block_id = self.add_block(
            self._next_id("sum"),
            "Sum",
            name=f"sum_{self.counter}",
            params={"Inputs": "+" * len(terms)},
            metadata={"layout_role": "shared", "layer_hint": layer_hint, "trace_expression": trace_expression},
        )
        for index, (source, label) in enumerate(terms, start=1):
            self.add_connection(source, block_id, index, label=label)
        return (block_id, "1")

    def _build_linear_combination(
        self,
        *,
        variable_coefficients: list[tuple[str, sympy.Expr]],
        input_coefficients: list[tuple[str, sympy.Expr]],
        constant_term: sympy.Expr,
        trace_expression: str,
        layer_hint: int,
    ) -> tuple[str, str]:
        terms: list[tuple[tuple[str, str], str]] = []
        for variable_name, coefficient in variable_coefficients:
            simplified = sympy.simplify(coefficient)
            if simplified == 0:
                continue
            source = self._apply_gain(
                self.sources[variable_name],
                simplified,
                trace=variable_name,
                layer_hint=layer_hint,
            )
            terms.append((source, f"{_numeric_string(simplified)}*{variable_name}" if simplified != 1 else variable_name))
        for input_name, coefficient in input_coefficients:
            simplified = sympy.simplify(coefficient)
            if simplified == 0:
                continue
            source = self._apply_gain(
                self.sources[input_name],
                simplified,
                trace=input_name,
                layer_hint=layer_hint,
            )
            terms.append((source, f"{_numeric_string(simplified)}*{input_name}" if simplified != 1 else input_name))
        constant_simplified = sympy.simplify(constant_term)
        if constant_simplified != 0:
            const_source = self._constant_source(
                constant_simplified,
                name=f"const_{self.counter}",
                layer_hint=layer_hint,
            )
            terms.append((const_source, _numeric_string(constant_simplified)))
        return self._sum_terms(terms, trace_expression=trace_expression, layer_hint=layer_hint)

    def _materialize_inputs(self) -> None:
        for input_name in self.inputs:
            metadata = {"layout_role": "source", "layer_hint": 0, "trace_expression": input_name}
            if input_name in self.input_signals:
                series = self.input_signals[input_name]
                workspace_name = f"{self.model_name}_{_sanitize(input_name)}_input"
                self.workspace_variables[workspace_name] = [
                    [float(time), float(value)]
                    for time, value in zip(series["time"], series["values"])
                ]
                block_id = self.add_block(
                    f"input_{_sanitize(input_name)}",
                    "FromWorkspace",
                    name=input_name,
                    params={"VariableName": workspace_name},
                    metadata=metadata,
                )
            elif input_name in self.input_values:
                block_id = self.add_block(
                    f"input_{_sanitize(input_name)}",
                    "Constant",
                    name=input_name,
                    params={"Value": _numeric_string(sympy.Float(float(self.input_values[input_name])))},
                    metadata=metadata,
                )
            else:
                raise DeterministicCompileError(
                    f"No numeric value or input signal provided for descriptor input {input_name!r}."
                )
            self.sources[input_name] = (block_id, "1")

    def _materialize_differential_states(self) -> None:
        for index, state in enumerate(self.differential_states):
            params: dict[str, object] = {}
            if state in self.differential_initial_conditions:
                params["InitialCondition"] = _numeric_string(sympy.Float(float(self.differential_initial_conditions[state])))
            block_id = self.add_block(
                f"int_{_sanitize(state)}",
                "Integrator",
                name=state,
                params=params,
                metadata={"layout_role": "shared", "layer_hint": 4 + index, "trace_expression": state, "state_order": 0},
            )
            self.sources[state] = (block_id, "1")

    def _materialize_algebraic_variables(self) -> None:
        for index, variable in enumerate(self.algebraic_variables):
            params: dict[str, object] = {}
            if variable in self.algebraic_initial_conditions:
                params["InitialGuess"] = _numeric_string(sympy.Float(float(self.algebraic_initial_conditions[variable])))
            block_id = self.add_block(
                f"alg_{_sanitize(variable)}",
                "AlgebraicConstraint",
                name=variable,
                params=params,
                metadata={"layout_role": "shared", "layer_hint": 3 + index, "trace_expression": variable},
            )
            self.sources[variable] = (block_id, "1")

    def _build_differential_rhs(self) -> None:
        for row_index, state in enumerate(self.differential_states):
            derivative_coefficients = [sympy.simplify(self.E[row_index, column]) for column in range(self.E.cols)]
            nonzero_positions = [index for index, coefficient in enumerate(derivative_coefficients) if coefficient != 0]
            if nonzero_positions != [row_index]:
                raise DeterministicCompileError(
                    "Descriptor differential rows must isolate the matching state derivative deterministically."
                )
            scale = sympy.simplify(derivative_coefficients[row_index])
            variable_coefficients = [
                (variable, sympy.simplify(self.A[row_index, column] / scale))
                for column, variable in enumerate(self.variables)
            ]
            input_coefficients = [
                (input_name, sympy.simplify(self.B[row_index, column] / scale))
                for column, input_name in enumerate(self.inputs)
            ]
            rhs_source = self._build_linear_combination(
                variable_coefficients=variable_coefficients,
                input_coefficients=input_coefficients,
                constant_term=sympy.simplify(self.offset[row_index, 0] / scale),
                trace_expression=f"d/dt {state}",
                layer_hint=2,
            )
            self.add_connection(rhs_source, self.sources[state][0], 1, label=f"d/dt {state}")

    def _build_algebraic_constraints(self) -> None:
        if not self.algebraic_variables:
            return
        for algebraic_index, variable in enumerate(self.algebraic_variables):
            variable_column = len(self.differential_states) + algebraic_index
            row_index = self.algebraic_row_assignment[variable_column]
            variable_coefficients = [
                (name, sympy.simplify(self.A[row_index, column]))
                for column, name in enumerate(self.variables)
            ]
            input_coefficients = [
                (input_name, sympy.simplify(self.B[row_index, column]))
                for column, input_name in enumerate(self.inputs)
            ]
            residual_source = self._build_linear_combination(
                variable_coefficients=variable_coefficients,
                input_coefficients=input_coefficients,
                constant_term=sympy.simplify(self.offset[row_index, 0]),
                trace_expression=f"constraint_{variable}",
                layer_hint=1,
            )
            self.add_connection(residual_source, self.sources[variable][0], 1, label=f"0 = constraint_{variable}")

    def lower(
        self,
        *,
        output_names: list[str] | None = None,
        model_params: dict[str, object] | None = None,
    ) -> BackendSimulinkModelDict:
        self._materialize_inputs()
        self._materialize_differential_states()
        self._materialize_algebraic_variables()
        self._build_algebraic_constraints()
        self._build_differential_rhs()

        outputs: list[dict[str, str]] = []
        names = output_names or [*self.differential_states, *self.algebraic_variables]
        for index, name in enumerate(names, start=1):
            if name not in self.sources:
                raise DeterministicCompileError(f"Descriptor output {name!r} is not available.")
            out_block = self.add_block(
                f"out_{_sanitize(name)}",
                "Outport",
                name=f"out_{name}",
                params={"Port": index},
                metadata={"layout_role": "output", "trace_expression": name},
            )
            self.add_connection(self.sources[name], out_block, 1, label=name)
            outputs.append({"name": name, "block": out_block, "port": "1"})

        model = validate_simulink_model_dict(
            {
                "name": self.model_name,
                "blocks": self.blocks,
                "connections": self.connections,
                "outputs": outputs,
                "model_params": dict(model_params or {}),
                "workspace_variables": dict(self.workspace_variables),
                "metadata": {
                    "descriptor_form": self.descriptor_system.get("form"),
                    "differential_states": list(self.differential_states),
                    "algebraic_variables": list(self.algebraic_variables),
                },
            }
        )
        return validate_simulink_model_dict(apply_deterministic_layout(model))


def descriptor_to_simulink_model(
    descriptor_system: dict[str, object],
    *,
    name: str,
    parameter_values: dict[str, float] | None = None,
    input_values: dict[str, float] | None = None,
    input_signals: dict[str, dict[str, list[float]]] | None = None,
    differential_initial_conditions: dict[str, float] | None = None,
    algebraic_initial_conditions: dict[str, float] | None = None,
    output_names: list[str] | None = None,
    model_params: dict[str, object] | None = None,
) -> BackendSimulinkModelDict:
    """Lower a linear descriptor system into a Simulink-ready model dictionary."""
    lowerer = DescriptorToSimulinkLowerer(
        descriptor_system=descriptor_system,
        model_name=name,
        parameter_values=dict(parameter_values or {}),
        input_values=dict(input_values or {}),
        input_signals=dict(input_signals or {}),
        differential_initial_conditions=dict(differential_initial_conditions or {}),
        algebraic_initial_conditions=dict(algebraic_initial_conditions or {}),
    )
    return lowerer.lower(output_names=output_names, model_params=model_params)
