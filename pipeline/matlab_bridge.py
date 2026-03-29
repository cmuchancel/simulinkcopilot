"""JSON request/response bridge for MATLAB-facing backend calls."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Mapping

from latex_frontend.symbols import DeterministicCompileError


def run_matlab_bridge_request(
    request: Mapping[str, object],
) -> dict[str, object]:
    """Run a MATLAB bridge request through the shared backend pipeline."""
    from pipeline.run_pipeline import DEFAULT_TOLERANCE, run_pipeline_payload

    if not isinstance(request, Mapping):
        raise DeterministicCompileError("MATLAB bridge request must be a JSON object.")

    options = request.get("options")
    if options is None:
        options_dict: dict[str, object] = {}
    elif isinstance(options, Mapping):
        options_dict = dict(options)
    else:
        raise DeterministicCompileError("MATLAB bridge request field 'options' must be an object when provided.")

    payload = {key: value for key, value in dict(request).items() if key not in {"options", "provenance"}}
    model_name = request.get("model_name")
    if isinstance(model_name, str) and model_name.strip() and "name" not in payload:
        payload["name"] = model_name.strip()

    tolerance = float(options_dict.get("tolerance", DEFAULT_TOLERANCE))
    run_sim = bool(options_dict.get("run_sim", True))
    build = bool(options_dict.get("build", False))
    validate_graph = bool(options_dict.get("validate_graph", True))
    classification_mode = _optional_string_option(options_dict, "classification_mode")
    symbol_config = options_dict.get("symbol_config")
    runtime_override = _optional_mapping_option(options_dict, "runtime_override")
    simulink_output_dir = _optional_string_option(options_dict, "simulink_output_dir")

    if build and not run_sim:
        raise DeterministicCompileError(
            "MATLAB bridge requests that build Simulink models must also enable run_sim; generated diagrams are always validated."
        )

    results = run_pipeline_payload(
        payload,
        tolerance=tolerance,
        run_sim=run_sim,
        validate_graph=validate_graph,
        run_simulink=build,
        runtime_override=runtime_override,
        classification_mode=classification_mode,
        symbol_config=symbol_config,
        simulink_output_dir=simulink_output_dir,
    )
    return build_matlab_bridge_response(results, request=request)


def build_matlab_bridge_response(
    results: Mapping[str, object],
    *,
    request: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Convert pipeline results into a MATLAB-friendly response contract."""
    from pipeline.run_pipeline import summarize_pipeline_results

    summary = summarize_pipeline_results(dict(results))
    classification = results["dae_classification"]  # type: ignore[index]
    simulink_result = results["simulink_result"]  # type: ignore[index]
    dae_validation = results["dae_validation"]  # type: ignore[index]
    simulink_validation = results["simulink_validation"]  # type: ignore[index]
    comparison = results["comparison"]  # type: ignore[index]

    generated_model_path = None
    model_name = None
    if simulink_result is not None:
        generated_model_path = simulink_result.get("model_file")  # type: ignore[union-attr]
        model_name = simulink_result.get("model_name")  # type: ignore[union-attr]

    return {
        "status": "ok",
        "route": classification["kind"],
        "message": "Backend request completed successfully.",
        "diagnostics": [],
        "source_type": results.get("source_type"),  # type: ignore[union-attr]
        "validation": {
            "dae_validation": dae_validation,
            "simulink_validation": simulink_validation,
            "comparison": comparison,
            "consistent_initialization": results["consistent_initialization"].to_dict(),  # type: ignore[index, union-attr]
        },
        "normalized_problem": results["normalized_problem"].to_dict(),  # type: ignore[index, union-attr]
        "generated_model_path": generated_model_path,
        "model_name": model_name,
        "artifacts": {
            "summary": summary,
        },
        "request_echo": None if request is None else dict(request),
    }


def build_matlab_bridge_error_response(
    exc: Exception,
    *,
    request: Mapping[str, object] | None = None,
    verbose: bool = False,
) -> dict[str, object]:
    """Build a deterministic error response for bridge failures."""
    diagnostics: list[str] = [str(exc)]
    if verbose:
        diagnostics.append(traceback.format_exc())
    return {
        "status": "error",
        "route": None,
        "error_code": _bridge_error_code(exc),
        "message": str(exc),
        "diagnostics": diagnostics,
        "source_type": None if request is None else request.get("source_type"),
        "validation": None,
        "normalized_problem": None,
        "generated_model_path": None,
        "model_name": None,
        "artifacts": None,
        "request_echo": None if request is None else dict(request),
    }


def process_matlab_bridge_request_file(
    request_path: str | Path,
    response_path: str | Path,
    *,
    verbose: bool = False,
) -> int:
    """Run a bridge request from JSON files and write a JSON response."""
    resolved_request_path = Path(request_path)
    resolved_response_path = Path(response_path)
    request: dict[str, object] | None = None

    try:
        raw_request = json.loads(resolved_request_path.read_text(encoding="utf-8"))
        if not isinstance(raw_request, dict):
            raise DeterministicCompileError("MATLAB bridge request JSON must decode to an object.")
        request = raw_request
        response = run_matlab_bridge_request(request)
        exit_code = 0
    except Exception as exc:
        response = build_matlab_bridge_error_response(exc, request=request, verbose=verbose)
        exit_code = 1

    resolved_response_path.write_text(json.dumps(response, indent=2), encoding="utf-8")
    return exit_code


def _bridge_error_code(exc: Exception) -> str:
    message = str(exc).lower()
    if "opaque function handles" in message:
        return "opaque_matlab_ode_function"
    if "state derivative or an ordinary variable" in message:
        return "ambiguous_derivative_alias"
    if "non-square" in message or "structurally singular" in message:
        return "unsupported_algebraic_subsystem"
    if "exactly one independent variable" in message:
        return "invalid_independent_variable"
    if isinstance(exc, DeterministicCompileError):
        return "deterministic_compile_error"
    return "backend_error"


def _optional_mapping_option(
    options: Mapping[str, object],
    key: str,
) -> dict[str, object] | None:
    raw = options.get(key)
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise DeterministicCompileError(f"MATLAB bridge option {key!r} must be an object.")
    return dict(raw)


def _optional_string_option(options: Mapping[str, object], key: str) -> str | None:
    raw = options.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise DeterministicCompileError(f"MATLAB bridge option {key!r} must be a non-empty string.")
    return raw.strip()
