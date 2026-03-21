"""Local Flask app for staged Eqn2Sim drafting, validation, and model download."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from pathlib import Path
import time
import traceback
from typing import Any
import uuid

from flask import Flask, abort, render_template, request, send_file, url_for

from canonicalize.algebraic_substitution import inline_algebraic_definitions
from eqn2sim_gui.model_metadata import (
    GUI_SYMBOL_ROLES,
    GuiModelMetadata,
    build_model_symbol_values_from_gui,
    build_runtime_override_from_gui,
    extract_symbol_inventory,
    gui_symbols_to_symbol_config,
    save_gui_metadata,
    validate_gui_symbol_payload,
)
from eqn2sim_gui.llm_draft import (
    draft_model_spec_from_raw_text_with_diagnostics,
    draft_spec_to_form_defaults,
    draft_spec_to_json,
)
from eqn2sim_gui.preview import (
    render_equation_preview,
    render_state_trajectory_comparison_preview,
)
from latex_frontend.symbols import DeterministicCompileError
from latex_frontend.normalize import normalize_latex
from latex_frontend.translator import translate_latex
from ir.equation_dict import equation_to_dict, equation_to_string
from repo_paths import GUI_DEBUG_ROOT, GUI_RUNS_ROOT

_INLINE_MATH_NOTE_RE = re.compile(r"\\\((?P<body>.*?)\\\)")
_SCIENTIFIC_LITERAL_RE = re.compile(
    r"(?P<base>[+-]?\d+(?:\.\d+)?)\s*(?:\\times|\*)\s*10\^\{?(?P<exp>[+-]?\d+)\}?"
)
_PLAIN_FLOAT_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")


@dataclass
class _RequestDebugTrace:
    request_id: str
    path: Path
    action: str
    started_at: float = field(default_factory=time.time)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "running"
    error_message: str | None = None

    def record(self, stage: str, **details: Any) -> None:
        event = {
            "stage": stage,
            "elapsed_seconds": round(time.time() - self.started_at, 3),
            "details": _json_safe(details),
        }
        self.events.append(event)
        self.flush()

    def fail(self, stage: str, exc: Exception) -> None:
        self.status = "failed"
        self.error_message = str(exc)
        self.record(
            stage,
            status="failed",
            error_type=type(exc).__name__,
            error_message=str(exc),
            traceback=traceback.format_exc(),
        )

    def finish(self, *, status: str = "completed") -> None:
        self.status = status
        self.flush()

    def flush(self) -> None:
        payload = {
            "request_id": self.request_id,
            "action": self.action,
            "status": self.status,
            "started_at_epoch": self.started_at,
            "error_message": self.error_message,
            "events": self.events,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def create_app() -> Flask:
    """Create the local Eqn2Sim GUI application."""
    app = Flask(__name__)
    app.config.setdefault("GUI_REPORT_ROOT", str(GUI_RUNS_ROOT.resolve()))
    app.config.setdefault("GUI_DEBUG_ROOT", str(GUI_DEBUG_ROOT.resolve()))

    @app.route("/download/<run_name>", methods=["GET"])
    def download_model(run_name: str):
        if not _is_valid_run_name(run_name):
            abort(404)
        artifact_dir = Path(str(app.config["GUI_REPORT_ROOT"])) / run_name
        model_files = sorted(artifact_dir.glob("*.slx"))
        if not model_files:
            abort(404)
        model_path = model_files[-1].resolve()
        return send_file(model_path, as_attachment=True, download_name=model_path.name)

    @app.route("/debug/<request_id>", methods=["GET"])
    def download_debug_trace(request_id: str):
        if not re.fullmatch(r"[0-9a-f]{12}", request_id):
            abort(404)
        debug_path = Path(str(app.config["GUI_DEBUG_ROOT"])) / f"{request_id}.json"
        if not debug_path.exists():
            abort(404)
        return send_file(debug_path.resolve(), as_attachment=True, download_name=debug_path.name)

    @app.route("/", methods=["GET", "POST"])
    def index() -> str:
        context = _default_context()
        debug_root = Path(str(app.config["GUI_DEBUG_ROOT"]))
        report_root = Path(str(app.config["GUI_REPORT_ROOT"]))
        context["debug_root_hint"] = str(debug_root.resolve())
        context["recent_runs"] = _list_recent_runs(report_root)

        if request.method == "GET":
            selected_run_name = request.args.get("run", "").strip()
            if selected_run_name:
                try:
                    context.update(_load_saved_run_context(report_root, selected_run_name))
                    context["info_message"] = f"Loaded saved run `{selected_run_name}` for review."
                    context["active_run_name"] = selected_run_name
                except Exception as exc:
                    context["error_message"] = f"Could not load saved run `{selected_run_name}`: {exc}"
            _apply_run_browser_context(context)
            return render_template("index.html", **context)

        request_id = _resolve_debug_request_id(request.form.get("debug_request_id", "").strip())
        debug_trace = _open_debug_trace(
            debug_root,
            request_id=request_id,
            action=_normalize_action(request.form.get("action", "refresh_equations")),
            raw_text=request.form.get("raw_text", "").strip(),
            latex_text=request.form.get("latex", "").strip(),
        )
        raw_text = request.form.get("raw_text", "").strip()
        latex_text = request.form.get("latex", "").strip()
        action = _normalize_action(request.form.get("action", "refresh_equations"))
        context["raw_text"] = raw_text
        context["latex_text"] = latex_text
        context["structured_output_json"] = request.form.get("structured_output_json", "").strip()
        context["debug_request_id"] = request_id
        context["debug_trace_path"] = str(debug_trace.path.resolve())
        context["debug_download_url"] = url_for("download_debug_trace", request_id=request_id)

        seeded_symbol_values: dict[str, dict[str, object]] = {}
        preserved_value_note_count = 0

        if action == "draft_structured":
            if not raw_text:
                debug_trace.record("draft_input_validation", status="failed", reason="empty_raw_text")
                debug_trace.finish(status="failed")
                context["error_message"] = "Enter raw system text before generating a structured output."
                return render_template("index.html", **context)
            try:
                seed_start = time.perf_counter()
                raw_seeded_symbol_values, preserved_value_note_count = _extract_seeded_symbol_values_from_raw_text(raw_text)
                debug_trace.record(
                    "seed_numeric_value_notes",
                    elapsed_seconds=round(time.perf_counter() - seed_start, 3),
                    preserved_value_note_count=preserved_value_note_count,
                    seeded_symbol_count=len(raw_seeded_symbol_values),
                )
                draft_start = time.perf_counter()
                draft_result = draft_model_spec_from_raw_text_with_diagnostics(raw_text)
                debug_trace.record(
                    "llm_draft_completed",
                    elapsed_seconds=round(time.perf_counter() - draft_start, 3),
                    model=draft_result.diagnostics.model,
                    timeout_seconds=draft_result.diagnostics.timeout_seconds,
                    prepared_input_chars=draft_result.diagnostics.prepared_input_chars,
                    discarded_equation_count=draft_result.diagnostics.discarded_equation_count,
                    equation_count=len(draft_result.spec.equations),
                )
                draft = draft_result.spec
                drafted_latex, drafted_symbol_values = draft_spec_to_form_defaults(draft)
                context["structured_output_json"] = draft_spec_to_json(draft)
                context["latex_text"] = drafted_latex
                latex_text = drafted_latex
                seeded_symbol_values = _merge_seeded_symbol_values(raw_seeded_symbol_values, drafted_symbol_values)
                context["info_message"] = (
                    f"Structured output generated in {draft_result.diagnostics.elapsed_seconds:.1f} seconds "
                    f"with {draft_result.diagnostics.model}. Review the equations below."
                )
                if draft_result.diagnostics.discarded_equation_count:
                    context["info_message"] += (
                        f" Filtered out {draft_result.diagnostics.discarded_equation_count} non-equation "
                        "lines returned by the LLM."
                    )
                if preserved_value_note_count:
                    context["info_message"] += (
                        f" Preserved {preserved_value_note_count} numeric value notes from the raw text."
                    )
            except Exception as exc:
                debug_trace.fail("draft_structured", exc)
                context["error_message"] = str(exc)
                context["error_message"] += f" Debug request id: {request_id}."
                return render_template("index.html", **context)

        if not latex_text:
            context["show_latex_stage"] = False
            if action != "draft_structured":
                debug_trace.record("latex_validation", status="failed", reason="empty_latex_after_action")
                debug_trace.finish(status="failed")
                context["error_message"] = "Generate a structured output or provide LaTeX equations before continuing."
            return render_template("index.html", **context)

        try:
            analysis_timer = time.perf_counter()
            analysis = _analyze_submission(
                latex_text,
                request.form,
                seeded_symbol_values=seeded_symbol_values,
                debug_trace=debug_trace,
            )
            analysis_elapsed = time.perf_counter() - analysis_timer
            debug_trace.record("deterministic_analysis_completed", elapsed_seconds=round(analysis_elapsed, 3))
            context.update(analysis)
            readiness = _evaluate_generation_readiness(
                context["inventory"],
                context["symbol_values"],
                context["state_chain"],
                context["state_initials"],
            )
            context["can_generate_model"] = readiness["ready"]
            context["readiness_blockers"] = readiness["blockers"]
            debug_trace.record(
                "generation_readiness_evaluated",
                ready=readiness["ready"],
                blocker_count=len(readiness["blockers"]),
            )
            if action == "draft_structured" and context.get("info_message"):
                context["info_message"] += f" Deterministic analysis took {analysis_elapsed:.1f} seconds."

            if action != "generate_model":
                if action != "draft_structured":
                    context["info_message"] = (
                        "Equations parsed. Complete the remaining symbol values and state initial conditions to unlock model generation."
                    )
                debug_trace.finish()
                return render_template("index.html", **context)

            if not readiness["ready"]:
                raise DeterministicCompileError(
                    "Every symbol and state must be fully defined before generating the Simulink model."
                )

            metadata = _build_validated_metadata(
                latex_text=latex_text,
                normalized_latex=context["normalized_latex"],
                equation_strings=context["equation_strings"],
                symbol_values=context["symbol_values"],
                state_initials=context["state_initials"],
                state_chain=context["state_chain"],
                derivative_orders=context["derivative_orders"],
            )
            artifact_info = _persist_validated_representation(
                Path(str(app.config["GUI_REPORT_ROOT"])),
                metadata,
            )
            debug_trace.record(
                "validated_representation_persisted",
                artifact_dir=artifact_info["artifact_dir"],
                metadata_path=artifact_info["metadata_path"],
            )
            context.update(artifact_info)
            build_info = _generate_simulink_artifact(metadata, artifact_info["artifact_dir_path"])
            debug_trace.record(
                "simulink_artifact_generated",
                model_dict_path=build_info["model_dict_path"],
                model_file=build_info["model_file"],
            )
            context["model_dict_path"] = str(Path(build_info["model_dict_path"]).resolve())
            context["simulink_model_path"] = str(Path(build_info["model_file"]).resolve())
            context["download_url"] = url_for("download_model", run_name=artifact_info["artifact_dir_path"].name)
            context["download_name"] = Path(build_info["model_file"]).name
            context["summary"] = {
                "normalized_latex": context["normalized_latex"],
                "equations": context["equation_strings"],
                "equation_dicts": context["equation_dicts"],
                "states": list(context["state_chain"]),
                "symbols": metadata.symbols,
            }
            context["info_message"] = "Simulink model generated. Download the `.slx` artifact below."
            try:
                trajectory_context = _generate_state_trajectory_artifacts(metadata, artifact_info["artifact_dir_path"])
                context.update(trajectory_context)
                debug_trace.record(
                    "state_trajectory_preview_generated",
                    plot_path=trajectory_context.get("state_trajectory_plot_path"),
                    data_path=trajectory_context.get("state_trajectory_data_path"),
                    state_count=(trajectory_context.get("state_trajectory_summary") or {}).get("state_count"),
                )
            except Exception as exc:
                context["state_trajectory_error"] = str(exc)
                debug_trace.record(
                    "state_trajectory_preview_failed",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            context["recent_runs"] = _list_recent_runs(report_root)
            context["active_run_name"] = artifact_info["artifact_dir_path"].name
            _apply_run_browser_context(context)
            debug_trace.finish()
            return render_template("index.html", **context)
        except Exception as exc:
            debug_trace.fail("post_draft_pipeline", exc)
            context["error_message"] = str(exc)
            context["error_message"] += f" Debug request id: {request_id}."
            _apply_run_browser_context(context)
            return render_template("index.html", **context)

    return app


def _resolve_debug_request_id(candidate: str) -> str:
    if re.fullmatch(r"[0-9a-f]{12}", candidate):
        return candidate
    return uuid.uuid4().hex[:12]


def _open_debug_trace(
    debug_root: Path,
    *,
    request_id: str,
    action: str,
    raw_text: str,
    latex_text: str,
) -> _RequestDebugTrace:
    trace = _RequestDebugTrace(
        request_id=request_id,
        path=debug_root / f"{request_id}.json",
        action=action,
    )
    trace.record(
        "request_received",
        action=action,
        raw_text_chars=len(raw_text),
        latex_text_chars=len(latex_text),
        raw_text_preview=raw_text[:200],
        latex_text_preview=latex_text[:200],
    )
    return trace


def _artifact_dir(root: Path, latex_text: str) -> Path:
    digest = hashlib.sha1(latex_text.encode("utf-8")).hexdigest()[:12]
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    nonce = uuid.uuid4().hex[:6]
    return root / f"run_{timestamp}_{digest}_{nonce}"


def _is_valid_run_name(run_name: str) -> bool:
    return bool(
        re.fullmatch(r"run_[0-9a-f]{12}", run_name)
        or re.fullmatch(r"run_[0-9]{8}_[0-9]{6}_[0-9a-f]{12}_[0-9a-f]{6}", run_name)
    )


def _list_recent_runs(root: Path, *, limit: int = 8) -> list[dict[str, object]]:
    if not root.exists():
        return []

    recent_runs: list[dict[str, object]] = []
    for artifact_dir in root.iterdir():
        if not artifact_dir.is_dir() or not _is_valid_run_name(artifact_dir.name):
            continue
        model_files = sorted(artifact_dir.glob("*.slx"))
        metadata_path = artifact_dir / "gui_metadata.json"
        latex_preview = ""
        equation_count = 0
        if metadata_path.exists():
            try:
                metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                latex_value = str(metadata_payload.get("latex", "")).strip()
                normalized_preview = " ".join(line.strip() for line in latex_value.splitlines() if line.strip())
                latex_preview = normalized_preview[:140]
                equations = metadata_payload.get("equations", [])
                if isinstance(equations, list):
                    equation_count = len(equations)
            except Exception:
                latex_preview = ""
                equation_count = 0
        last_updated_epoch = artifact_dir.stat().st_mtime
        recent_runs.append(
            {
                "run_name": artifact_dir.name,
                "artifact_dir": str(artifact_dir.resolve()),
                "load_url": url_for("index", run=artifact_dir.name),
                "download_url": url_for("download_model", run_name=artifact_dir.name) if model_files else None,
                "model_name": model_files[-1].name if model_files else None,
                "has_model": bool(model_files),
                "equation_count": equation_count,
                "latex_preview": latex_preview,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_updated_epoch)),
                "_sort_key": last_updated_epoch,
            }
        )

    recent_runs.sort(key=lambda item: float(item["_sort_key"]), reverse=True)
    trimmed = recent_runs[:limit]
    for entry in trimmed:
        entry.pop("_sort_key", None)
    return trimmed


def _load_saved_run_context(root: Path, run_name: str) -> dict[str, Any]:
    if not _is_valid_run_name(run_name):
        raise FileNotFoundError("run id format is not recognized")

    artifact_dir = root / run_name
    metadata_path = artifact_dir / "gui_metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError("gui_metadata.json is missing")

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    latex_text = str(payload.get("latex", "")).strip()
    if not latex_text:
        raise ValueError("saved run metadata has no LaTeX payload")

    form_defaults: dict[str, object] = {}
    raw_symbols = payload.get("symbols", {})
    if isinstance(raw_symbols, dict):
        for name, entry in raw_symbols.items():
            if not isinstance(entry, dict):
                continue
            form_defaults[f"symbol_role__{name}"] = str(entry.get("role", ""))
            form_defaults[f"symbol_description__{name}"] = str(entry.get("description", ""))
            form_defaults[f"symbol_units__{name}"] = str(entry.get("units", ""))
            raw_value = entry.get("value")
            form_defaults[f"symbol_value__{name}"] = "" if raw_value is None else str(raw_value)
            form_defaults[f"symbol_input_kind__{name}"] = str(entry.get("input_kind", "constant"))

    raw_initial_conditions = payload.get("initial_conditions", {})
    if isinstance(raw_initial_conditions, dict):
        for state, value in raw_initial_conditions.items():
            form_defaults[f"state_ic__{state}"] = "" if value is None else str(value)

    context = _analyze_submission(latex_text, form_defaults)
    readiness = _evaluate_generation_readiness(
        context["inventory"],
        context["symbol_values"],
        context["state_chain"],
        context["state_initials"],
    )
    model_files = sorted(artifact_dir.glob("*.slx"))
    model_dict_path = artifact_dir / "simulink_model_dict.json"
    validated_spec_path = artifact_dir / "validated_model_spec.json"
    model_path = model_files[-1].resolve() if model_files else None

    context.update(
        {
            "raw_text": "",
            "structured_output_json": "",
            "can_generate_model": readiness["ready"],
            "readiness_blockers": readiness["blockers"],
            "artifact_dir": str(artifact_dir.resolve()),
            "artifact_dir_path": artifact_dir,
            "metadata_path": str(metadata_path.resolve()),
            "validated_spec_path": str(validated_spec_path.resolve()) if validated_spec_path.exists() else None,
            "model_dict_path": str(model_dict_path.resolve()) if model_dict_path.exists() else None,
            "simulink_model_path": str(model_path) if model_path else None,
            "download_url": url_for("download_model", run_name=run_name) if model_path else None,
            "download_name": model_path.name if model_path else None,
            "summary": {
                "normalized_latex": context["normalized_latex"],
                "equations": context["equation_strings"],
                "equation_dicts": context["equation_dicts"],
                "states": list(context["state_chain"]),
                "symbols": raw_symbols if isinstance(raw_symbols, dict) else {},
            },
        }
    )
    metadata = GuiModelMetadata(
        latex=latex_text,
        normalized_latex=str(payload.get("normalized_latex", context["normalized_latex"])),
        equations=list(payload.get("equations", context["equation_strings"])),
        symbols=raw_symbols if isinstance(raw_symbols, dict) else {},
        initial_conditions={
            str(state): float(value)
            for state, value in raw_initial_conditions.items()
            if value not in {None, ""}
        } if isinstance(raw_initial_conditions, dict) else {},
        extracted_states=list(payload.get("extracted_states", context["state_chain"])),
        derivative_orders={
            str(name): int(order)
            for name, order in (payload.get("derivative_orders", context["derivative_orders"]) or {}).items()
        },
    )
    try:
        context.update(_load_or_generate_state_trajectory_artifacts(metadata, artifact_dir))
    except Exception as exc:
        context["state_trajectory_error"] = str(exc)
    return context


def _apply_run_browser_context(context: dict[str, Any]) -> None:
    recent_runs = list(context.get("recent_runs", []))
    active_run_name = str(context.get("active_run_name", "") or "").strip()
    active_run_index: int | None = None
    active_run_download_url = None

    for index, run in enumerate(recent_runs):
        is_active = run.get("run_name") == active_run_name
        run["is_active"] = is_active
        if is_active:
            active_run_index = index
            active_run_download_url = run.get("download_url")

    if active_run_index is not None and len(recent_runs) > 1:
        previous_run = recent_runs[(active_run_index - 1) % len(recent_runs)]
        next_run = recent_runs[(active_run_index + 1) % len(recent_runs)]
        context["run_prev_url"] = previous_run.get("load_url")
        context["run_next_url"] = next_run.get("load_url")
    else:
        context["run_prev_url"] = None
        context["run_next_url"] = None

    context["active_run_name"] = active_run_name
    context["active_run_index"] = active_run_index
    context["active_run_download_url"] = active_run_download_url


def _default_context() -> dict[str, Any]:
    return {
        "gui_symbol_roles": GUI_SYMBOL_ROLES,
        "raw_text": "",
        "latex_text": "",
        "structured_output_json": "",
        "debug_request_id": "",
        "debug_trace_path": None,
        "debug_download_url": None,
        "debug_root_hint": "",
        "show_latex_stage": False,
        "normalized_latex": "",
        "equation_strings": [],
        "equation_dicts": [],
        "preview_svg": None,
        "preview_error": None,
        "inventory": [],
        "state_chain": [],
        "derivative_orders": {},
        "symbol_values": {},
        "state_initials": {},
        "can_generate_model": False,
        "readiness_blockers": [],
        "artifact_dir": None,
        "artifact_dir_path": None,
        "metadata_path": None,
        "validated_spec_path": None,
        "model_dict_path": None,
        "simulink_model_path": None,
        "download_url": None,
        "download_name": None,
        "state_trajectory_svg": None,
        "state_trajectory_error": None,
        "state_trajectory_plot_path": None,
        "state_trajectory_data_path": None,
        "state_trajectory_summary": None,
        "recent_runs": [],
        "active_run_name": "",
        "active_run_index": None,
        "active_run_download_url": None,
        "run_prev_url": None,
        "run_next_url": None,
        "summary": None,
        "info_message": None,
        "error_message": None,
    }


def _normalize_action(action: str) -> str:
    aliases = {
        "draft": "draft_structured",
        "analyze": "refresh_equations",
        "refresh": "refresh_equations",
        "run": "generate_model",
    }
    return aliases.get(action, action)


def _merge_seeded_symbol_values(
    primary: dict[str, dict[str, object]],
    secondary: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for name in set(primary) | set(secondary):
        merged[name] = {}
        merged[name].update(primary.get(name, {}))
        merged[name].update(secondary.get(name, {}))
    return merged


def _extract_seeded_symbol_values_from_raw_text(raw_text: str) -> tuple[dict[str, dict[str, object]], int]:
    seeded: dict[str, dict[str, object]] = {}
    preserved_value_note_count = 0
    for match in _INLINE_MATH_NOTE_RE.finditer(raw_text):
        body = match.group("body").strip()
        if "=" not in body and r"\approx" not in body:
            continue
        preserved_value_note_count += 1
        symbol_name = _extract_seedable_symbol_name(body)
        numeric_value = _extract_numeric_value_hint(body)
        if symbol_name is None or numeric_value is None:
            continue
        seeded.setdefault(symbol_name, {})
        seeded[symbol_name]["value"] = numeric_value
    return seeded, preserved_value_note_count


def _extract_seedable_symbol_name(note_body: str) -> str | None:
    if "=" in note_body:
        lhs = note_body.split("=", 1)[0].strip()
    elif r"\approx" in note_body:
        lhs = note_body.split(r"\approx", 1)[0].strip()
    else:
        return None
    normalized = normalize_latex(lhs).strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", normalized):
        return None
    return normalized


def _extract_numeric_value_hint(note_body: str) -> float | None:
    value_region = note_body
    if r"\approx" in note_body:
        value_region = note_body.split(r"\approx", 1)[1]
    elif "=" in note_body:
        value_region = note_body.split("=", 1)[1]
    scientific = _SCIENTIFIC_LITERAL_RE.search(value_region)
    if scientific:
        return float(scientific.group("base")) * (10 ** int(scientific.group("exp")))
    plain = _PLAIN_FLOAT_RE.search(value_region)
    if plain:
        return float(plain.group(0))
    return None


def _analyze_submission(
    latex_text: str,
    form,
    *,
    seeded_symbol_values: dict[str, dict[str, object]] | None = None,
    debug_trace: _RequestDebugTrace | None = None,
) -> dict[str, Any]:
    normalize_start = time.perf_counter()
    normalized_latex = normalize_latex(latex_text)
    if debug_trace is not None:
        debug_trace.record(
            "normalize_latex_completed",
            elapsed_seconds=round(time.perf_counter() - normalize_start, 3),
            normalized_chars=len(normalized_latex),
        )

    translate_start = time.perf_counter()
    equations = translate_latex(latex_text)
    if debug_trace is not None:
        debug_trace.record(
            "translate_latex_completed",
            elapsed_seconds=round(time.perf_counter() - translate_start, 3),
            equation_count=len(equations),
        )

    substitution_start = time.perf_counter()
    substitution_result = inline_algebraic_definitions(equations)
    resolved_equations = substitution_result.equations
    if debug_trace is not None:
        debug_trace.record(
            "inline_algebraic_definitions_completed",
            elapsed_seconds=round(time.perf_counter() - substitution_start, 3),
            helper_definition_count=len(substitution_result.resolved_definitions),
            expanded_equation_count=len(resolved_equations),
        )

    inventory_start = time.perf_counter()
    inventory_entries, state_chain, derivative_orders = extract_symbol_inventory(resolved_equations)
    if debug_trace is not None:
        debug_trace.record(
            "extract_symbol_inventory_completed",
            elapsed_seconds=round(time.perf_counter() - inventory_start, 3),
            symbol_count=len(inventory_entries),
            state_count=len(state_chain),
        )

    preview_start = time.perf_counter()
    preview = render_equation_preview(latex_text)
    if debug_trace is not None:
        debug_trace.record(
            "render_equation_preview_completed",
            elapsed_seconds=round(time.perf_counter() - preview_start, 3),
            preview_error=preview.error,
            has_preview_svg=bool(preview.svg),
        )
    seeded_symbol_values = seeded_symbol_values or {}

    symbol_values = {
        entry.name: {
            "role": request_value(form, f"symbol_role__{entry.name}", seeded_symbol_values.get(entry.name, {}).get("role", entry.suggested_role)),
            "description": request_value(form, f"symbol_description__{entry.name}", seeded_symbol_values.get(entry.name, {}).get("description", "")),
            "units": request_value(form, f"symbol_units__{entry.name}", seeded_symbol_values.get(entry.name, {}).get("units", "")),
            "value": request_value(form, f"symbol_value__{entry.name}", seeded_symbol_values.get(entry.name, {}).get("value", "")),
            "input_kind": request_value(form, f"symbol_input_kind__{entry.name}", seeded_symbol_values.get(entry.name, {}).get("input_kind", "constant")),
        }
        for entry in inventory_entries
    }
    state_initials = {
        state: request_value(form, f"state_ic__{state}", "0.0")
        for state in state_chain
    }

    return {
        "latex_text": latex_text,
        "show_latex_stage": True,
        "normalized_latex": normalized_latex,
        "equation_strings": [equation_to_string(equation) for equation in resolved_equations],
        "equation_dicts": [equation_to_dict(equation) for equation in resolved_equations],
        "preview_svg": preview.svg,
        "preview_error": preview.error,
        "inventory": [entry.to_dict() for entry in inventory_entries],
        "state_chain": list(state_chain),
        "derivative_orders": derivative_orders,
        "symbol_values": symbol_values,
        "state_initials": state_initials,
    }


def request_value(form, key: str, default: object) -> str:
    return str(form.get(key, default))


def _evaluate_generation_readiness(
    inventory: list[dict[str, object]],
    symbol_values: dict[str, dict[str, object]],
    state_chain: list[str],
    state_initials: dict[str, object],
) -> dict[str, object]:
    blockers: list[str] = []

    for entry in inventory:
        name = str(entry["name"])
        derivative_order = int(entry["max_derivative_order"])
        values = symbol_values.get(name, {})
        role = str(values.get("role", "")).strip()
        raw_value = str(values.get("value", "")).strip()
        input_kind = str(values.get("input_kind", "constant")).strip() or "constant"

        if role not in GUI_SYMBOL_ROLES:
            blockers.append(f"Choose a valid role for `{name}`.")
            continue
        if derivative_order > 0 and role != "state":
            blockers.append(f"`{name}` has derivatives and must stay marked as a state.")
        if derivative_order == 0 and role == "state":
            blockers.append(f"`{name}` is marked as a state, but no derivative of `{name}` appears in the equations.")
        if role in {"parameter", "known_constant", "input"}:
            if not raw_value:
                blockers.append(f"Provide a numeric value for `{name}`.")
            elif not _is_float(raw_value):
                blockers.append(f"`{name}` must have a numeric value.")
        if role == "input" and input_kind not in {"constant", "inport"}:
            blockers.append(f"`{name}` has unsupported input handling `{input_kind}`.")

    for state in state_chain:
        raw_initial = str(state_initials.get(state, "")).strip()
        if not raw_initial:
            blockers.append(f"Provide an initial condition for `{state}`.")
        elif not _is_float(raw_initial):
            blockers.append(f"`{state}` must have a numeric initial condition.")

    return {
        "ready": bool(inventory) and not blockers,
        "blockers": blockers,
    }


def _is_float(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _build_validated_metadata(
    *,
    latex_text: str,
    normalized_latex: str,
    equation_strings: list[str],
    symbol_values: dict[str, dict[str, object]],
    state_initials: dict[str, object],
    state_chain: list[str],
    derivative_orders: dict[str, int],
) -> GuiModelMetadata:
    validated_symbols = validate_gui_symbol_payload(symbol_values, derivative_orders)
    return GuiModelMetadata(
        latex=latex_text,
        normalized_latex=normalized_latex,
        equations=equation_strings,
        symbols=validated_symbols,
        initial_conditions={state: float(state_initials[state]) for state in state_chain},
        extracted_states=list(state_chain),
        derivative_orders=derivative_orders,
    )


def _persist_validated_representation(root: Path, metadata: GuiModelMetadata) -> dict[str, Any]:
    artifact_dir = _artifact_dir(root, metadata.latex)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "input_equations.tex").write_text(metadata.latex, encoding="utf-8")
    metadata_path = save_gui_metadata(artifact_dir / "gui_metadata.json", metadata)
    validated_spec_path = _write_validated_spec(artifact_dir, metadata)
    return {
        "artifact_dir": str(artifact_dir.resolve()),
        "artifact_dir_path": artifact_dir,
        "metadata_path": str(metadata_path.resolve()),
        "validated_spec_path": str(validated_spec_path.resolve()),
    }


def _compile_first_order_system(metadata: GuiModelMetadata) -> dict[str, object]:
    from canonicalize.first_order import build_first_order_system
    from canonicalize.solve_for_derivatives import solve_for_highest_derivatives
    from states.extract_states import extract_states

    equations = inline_algebraic_definitions(translate_latex(metadata.latex)).equations
    extraction = extract_states(
        equations,
        mode="configured",
        symbol_config=gui_symbols_to_symbol_config(metadata.symbols),
    )
    solved_derivatives = solve_for_highest_derivatives(equations)
    first_order = build_first_order_system(
        equations,
        extraction=extraction,
        solved_derivatives=solved_derivatives,
    )
    return {
        "equations": equations,
        "extraction": extraction,
        "solved_derivatives": solved_derivatives,
        "first_order": first_order,
    }


def _simulation_artifact_paths(artifact_dir: Path) -> tuple[Path, Path]:
    return artifact_dir / "state_trajectory_plot.svg", artifact_dir / "state_trajectory_data.json"


def _load_state_trajectory_artifacts(artifact_dir: Path) -> dict[str, Any]:
    plot_path, data_path = _simulation_artifact_paths(artifact_dir)
    plot_svg = plot_path.read_text(encoding="utf-8") if plot_path.exists() else None
    summary = None
    if data_path.exists():
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        state_names = payload.get("state_names", [])
        series = payload.get("series")
        if isinstance(series, list):
            series_labels = [str(item.get("label", "")) for item in series if isinstance(item, dict)]
            sample_count = len(series[0].get("t", [])) if series and isinstance(series[0], dict) else 0
            t_span = payload.get("t_span", [None, None])
            simulink_error = payload.get("simulink_error")
        else:
            series_labels = [str(payload.get("source", "ODE"))]
            sample_count = len(payload.get("t", []))
            t_span = payload.get("t_span", [None, None])
            simulink_error = payload.get("simulink_error")
        summary = {
            "state_count": len(state_names),
            "sample_count": sample_count,
            "t_start": t_span[0],
            "t_stop": t_span[1],
            "state_names": state_names,
            "series_labels": series_labels,
            "simulink_available": "Simulink" in series_labels,
            "simulink_error": simulink_error,
        }
    return {
        "state_trajectory_svg": plot_svg,
        "state_trajectory_error": summary.get("simulink_error") if summary is not None and not summary.get("simulink_available") else None,
        "state_trajectory_plot_path": str(plot_path.resolve()) if plot_path.exists() else None,
        "state_trajectory_data_path": str(data_path.resolve()) if data_path.exists() else None,
        "state_trajectory_summary": summary,
    }


def _load_or_generate_state_trajectory_artifacts(metadata: GuiModelMetadata, artifact_dir: Path) -> dict[str, Any]:
    plot_path, data_path = _simulation_artifact_paths(artifact_dir)
    if plot_path.exists() and data_path.exists():
        loaded = _load_state_trajectory_artifacts(artifact_dir)
        summary = loaded.get("state_trajectory_summary") or {}
        if summary.get("simulink_available") or not any(artifact_dir.glob("*.slx")):
            return loaded
    return _generate_state_trajectory_artifacts(metadata, artifact_dir)


def _generate_state_trajectory_artifacts(metadata: GuiModelMetadata, artifact_dir: Path) -> dict[str, Any]:
    from backend.graph_to_simulink import graph_to_simulink_model
    from backend.simulate_simulink import simulation_model_params, simulate_simulink_model
    from pipeline.run_pipeline import apply_runtime_override, default_runtime_context
    from simulate.ode_sim import simulate_ode_system
    from ir.graph_lowering import lower_first_order_system_graph
    from simulink.engine import start_engine

    compiled = _compile_first_order_system(metadata)
    first_order = compiled["first_order"]
    graph = lower_first_order_system_graph(first_order, name=f"{artifact_dir.name}_preview")
    runtime_override = build_runtime_override_from_gui(
        metadata.symbols,
        metadata.initial_conditions,
        simulation={"t_start": 0.0, "t_stop": 10.0, "sample_count": 400},
        preview_inports_as_constant=True,
    )
    runtime = apply_runtime_override(default_runtime_context(artifact_dir.name, first_order), runtime_override)
    ode_result = simulate_ode_system(
        first_order,
        parameter_values=runtime["parameter_values"],  # type: ignore[arg-type]
        initial_conditions=runtime["initial_conditions"],  # type: ignore[arg-type]
        input_function=runtime["input_function"],  # type: ignore[arg-type]
        t_span=runtime["t_span"],  # type: ignore[arg-type]
        t_eval=runtime["t_eval"],  # type: ignore[arg-type]
    )
    series_results: list[tuple[str, dict[str, object], str]] = [("ODE", ode_result, "-")]
    simulink_error: str | None = None
    preview_model_params = simulation_model_params(
        t_span=runtime["t_span"],  # type: ignore[arg-type]
        t_eval=runtime["t_eval"],  # type: ignore[arg-type]
    )
    preview_model = graph_to_simulink_model(
        graph,
        name=f"{artifact_dir.name}_simpreview",
        state_names=list(first_order["states"]),
        parameter_values=dict(runtime["parameter_values"]),  # type: ignore[arg-type]
        input_values=dict(runtime_override.get("input_values", {})),  # type: ignore[arg-type]
        initial_conditions=dict(runtime["initial_conditions"]),  # type: ignore[arg-type]
        model_params=preview_model_params,
        input_mode="constant",
    )
    try:
        eng = start_engine(retries=1, retry_delay_seconds=1.0)
        try:
            simulink_result = simulate_simulink_model(
                eng,
                preview_model,
                output_dir=artifact_dir / "_preview_models",
            )
            series_results.append(("Simulink", simulink_result, "--"))
        finally:
            eng.quit()
    except Exception as exc:
        simulink_error = f"Simulink overlay preview failed: {exc}"

    plot_result = render_state_trajectory_comparison_preview(series_results)
    plot_path, data_path = _simulation_artifact_paths(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if plot_result.svg:
        plot_path.write_text(plot_result.svg, encoding="utf-8")

    reference_result = series_results[0][1]
    time_values = [float(value) for value in reference_result["t"].tolist()]  # type: ignore[index]
    state_names = list(reference_result["state_names"])  # type: ignore[index]
    data_payload = {
        "source": "comparison",
        "t_span": [float(time_values[0]), float(time_values[-1])] if time_values else [0.0, 0.0],
        "state_names": state_names,
        "series": [
            {
                "label": label,
                "t": [float(value) for value in result["t"].tolist()],  # type: ignore[index]
                "states": {
                    state_name: [float(row[index]) for row in result["states"].tolist()]  # type: ignore[index]
                    for index, state_name in enumerate(state_names)
                },
            }
            for label, result, _style in series_results
        ],
        "simulink_error": simulink_error,
    }
    data_path.write_text(json.dumps(data_payload, indent=2), encoding="utf-8")
    context = _load_state_trajectory_artifacts(artifact_dir)
    if plot_result.error:
        context["state_trajectory_error"] = plot_result.error
    return context


def _generate_simulink_artifact(metadata: GuiModelMetadata, artifact_dir: Path) -> dict[str, str]:
    from ir.graph_lowering import lower_first_order_system_graph
    from simulink.engine import start_engine

    compiled = _compile_first_order_system(metadata)
    first_order = compiled["first_order"]
    graph = lower_first_order_system_graph(first_order, name=artifact_dir.name)
    build_values = build_model_symbol_values_from_gui(metadata.symbols, metadata.initial_conditions)

    from backend.graph_to_simulink import graph_to_simulink_model

    simulink_model = graph_to_simulink_model(
        graph,
        name=f"{artifact_dir.name}_simulink",
        state_names=list(first_order["states"]),
        parameter_values=dict(build_values["parameter_values"]),
        input_values=dict(build_values["input_values"]),
        initial_conditions=dict(build_values["initial_conditions"]),
        input_mode=str(build_values["input_mode"]),
    )
    model_dict_path = artifact_dir / "simulink_model_dict.json"
    model_dict_path.write_text(json.dumps(simulink_model, indent=2), encoding="utf-8")

    eng = start_engine(retries=1, retry_delay_seconds=1.0)
    try:
        from backend.builder import build_simulink_model

        build_info = build_simulink_model(eng, simulink_model, output_dir=artifact_dir)
    finally:
        eng.quit()

    return {
        "model_dict_path": str(model_dict_path),
        "model_file": str(build_info["model_file"]),
    }


def _write_validated_spec(artifact_dir: Path, metadata: GuiModelMetadata) -> Path:
    path = artifact_dir / "validated_model_spec.json"
    path.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")
    return path
