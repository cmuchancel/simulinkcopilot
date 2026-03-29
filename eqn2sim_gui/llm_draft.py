"""LLM-assisted drafting of structured model specs from raw text."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import time
from typing import Literal

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import BaseModel, Field

from latex_frontend.symbols import DeterministicCompileError


load_dotenv()

GUI_ROLE = Literal["state", "input", "parameter", "known_constant", "independent_variable"]
INPUT_KIND = Literal["inport", "constant"]
DRAFT_MODE = Literal["llm"]
DEFAULT_DRAFT_MODEL = "gpt-5-mini"
DEFAULT_DRAFT_TIMEOUT_SECONDS = 21.0
DEFAULT_DRAFT_MAX_RETRIES = 0
_DISPLAY_EQUATION_RE = re.compile(r"\\\[(?P<bracket>.*?)\\\]|\$\$(?P<dollar>.*?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"\\\((?P<body>.*?)\\\)")


class DraftSymbol(BaseModel):
    """LLM-proposed symbol metadata."""

    name: str = Field(min_length=1)
    role: GUI_ROLE
    description: str = ""
    units: str = ""
    value: float | None = None
    input_kind: INPUT_KIND = "inport"


class DraftModelSpec(BaseModel):
    """Structured draft produced from free-form user text."""

    equations: list[str] = Field(min_length=1)
    symbols: list[DraftSymbol] = Field(default_factory=list)


class DraftEquationSpec(BaseModel):
    """Lean LLM output schema used during raw-text drafting."""

    equations: list[str] = Field(min_length=1)


@dataclass(frozen=True)
class DraftDiagnostics:
    """Minimal timing and routing details for GUI draft generation."""

    mode: DRAFT_MODE
    elapsed_seconds: float
    model: str | None = None
    timeout_seconds: float | None = None
    prepared_input_chars: int = 0
    discarded_equation_count: int = 0


@dataclass(frozen=True)
class DraftGenerationResult:
    """Structured draft plus diagnostics for GUI display."""

    spec: DraftModelSpec
    diagnostics: DraftDiagnostics


@dataclass(frozen=True)
class _SectionedEquation:
    section_title: str
    latex: str


SYSTEM_PROMPT = """
You convert informal engineering descriptions into a structured dynamical-system draft.

Output only the provided schema.

Rules:
- Preserve the user's symbol names exactly when possible.
- Do not rename symbols to canonical substitutes like q or w.
- Return only LaTeX equations, one equation string per list entry.
- Put the primary governing equation first, then any direct supporting definitions.
- Prefer the primary governing dynamics equations and direct supporting definitions.
- Do not return approximate numeric notes, unit annotations, or prose bullets as equations.
- Ignore optional relations, natural-frequency formulas, and explanatory commentary unless they are clearly part of the governing model.
- Do not include assumptions or commentary.
- Use deterministic, concise equation strings suitable for later user review.
""".strip()


def resolve_draft_model(model: str | None = None) -> str:
    """Return the configured draft model name."""
    return model or os.getenv("EQN2SIM_OPENAI_MODEL", DEFAULT_DRAFT_MODEL)


def resolve_draft_timeout_seconds() -> float:
    """Return the configured draft timeout in seconds."""
    return float(os.getenv("EQN2SIM_OPENAI_TIMEOUT_SECONDS", str(DEFAULT_DRAFT_TIMEOUT_SECONDS)))


def resolve_draft_max_retries() -> int:
    """Return the configured max-retry count for draft requests."""
    return int(os.getenv("EQN2SIM_OPENAI_MAX_RETRIES", str(DEFAULT_DRAFT_MAX_RETRIES)))


def _compact_display_equation(block: str) -> str:
    return " ".join(line.strip() for line in block.splitlines() if line.strip())


def _strip_inline_math_delimiters(text: str) -> str:
    return _INLINE_MATH_RE.sub(lambda match: match.group("body"), text)


def _section_is_optional(section_title: str | None) -> bool:
    title = (section_title or "").strip().lower()
    return any(token in title for token in ("optional", "natural frequency", "linearized"))


def _looks_like_raw_equation_lines(raw_text: str) -> bool:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return False
    return all("=" in line for line in lines)


def _extract_relevant_display_blocks(raw_text: str) -> list[_SectionedEquation]:
    blocks: list[_SectionedEquation] = []
    current_section = ""
    current_block: list[str] | None = None

    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            continue
        if stripped == r"\[":
            current_block = []
            continue
        if stripped == r"\]" and current_block is not None:
            block = _compact_display_equation("\n".join(current_block))
            if block and not _section_is_optional(current_section):
                blocks.append(_SectionedEquation(section_title=current_section, latex=block))
            current_block = None
            continue
        if current_block is not None:
            current_block.append(line)

    if blocks:
        return blocks
    return [
        _SectionedEquation(
            section_title="",
            latex=_compact_display_equation(match.group("bracket") or match.group("dollar") or ""),
        )
        for match in _DISPLAY_EQUATION_RE.finditer(raw_text)
    ]


def _prepare_raw_text_for_llm(raw_text: str) -> str:
    if _looks_like_raw_equation_lines(raw_text):
        candidate_lines = [" ".join(line.split()) for line in raw_text.splitlines() if line.strip()]
        return (
            "Candidate equations provided directly:\n"
            + "\n".join(f"- {line}" for line in candidate_lines)
            + "\n\nClean and normalize these equations only. "
            "Do not infer extra equations, definitions, or numeric value notes."
        )

    display_blocks = _extract_relevant_display_blocks(raw_text)
    if any("expanded" in block.section_title.lower() for block in display_blocks):
        display_blocks = [block for block in display_blocks if "governing" not in block.section_title.lower()]

    assignment_bullets = [
        _strip_inline_math_delimiters(line.strip()[1:].strip())
        for line in raw_text.splitlines()
        if line.strip().startswith("- ")
        and ("=" in line or r"\approx" in line)
    ]
    descriptive_bullets = [
        _strip_inline_math_delimiters(line.strip()[1:].strip())
        for line in raw_text.splitlines()
        if line.strip().startswith("- ")
        and ("=" not in line and r"\approx" not in line)
    ]
    bullet_lines = assignment_bullets or descriptive_bullets[:4]
    if not display_blocks and len(bullet_lines) < 3:
        return raw_text.strip()

    sections: list[str] = []
    if display_blocks:
        sections.append("Display equations:\n" + "\n".join(f"- {block.latex}" for block in display_blocks[:4]))
    if bullet_lines:
        sections.append("Variable and parameter notes:\n" + "\n".join(f"- {line}" for line in bullet_lines))
    return "\n\n".join(sections).strip() or raw_text.strip()


def _sanitize_drafted_equations(equations: list[str]) -> tuple[list[str], int]:
    sanitized: list[str] = []
    discarded = 0
    seen: set[str] = set()

    for equation in equations:
        candidate = " ".join(equation.split()).strip()
        if not candidate:
            discarded += 1
            continue
        if r"\approx" in candidate or " approx " in candidate:
            discarded += 1
            continue
        if "=" not in candidate:
            discarded += 1
            continue
        if candidate in seen:
            discarded += 1
            continue
        seen.add(candidate)
        sanitized.append(candidate)

    return sanitized, discarded


def draft_model_spec_from_raw_text_with_diagnostics(
    raw_text: str,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
) -> DraftGenerationResult:
    """Draft a structured model spec from free-form text and return timing diagnostics."""
    start = time.perf_counter()
    if not raw_text.strip():
        raise DeterministicCompileError("Raw text input is empty.")

    api_key = os.getenv("OPENAI_API_KEY")
    if client is None and not api_key:
        raise DeterministicCompileError(
            "OPENAI_API_KEY was not found. Add it to your environment or .env file before using raw-text drafting."
        )

    timeout_seconds = resolve_draft_timeout_seconds()
    max_retries = resolve_draft_max_retries()
    resolved_model = resolve_draft_model(model)
    prepared_raw_text = _prepare_raw_text_for_llm(raw_text)
    llm_client = client or OpenAI(api_key=api_key)
    request_client = (
        llm_client.with_options(timeout=timeout_seconds, max_retries=max_retries)
        if hasattr(llm_client, "with_options")
        else llm_client
    )
    try:
        response = request_client.responses.parse(
            model=resolved_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prepared_raw_text},
            ],
            text_format=DraftEquationSpec,
        )
    except APITimeoutError as exc:
        raise DeterministicCompileError(
            f"OpenAI draft request timed out after {timeout_seconds:.0f} seconds. "
            "This input is still too large or noisy for the current draft settings. "
            "Try removing optional or derived relations and retry."
        ) from exc
    except APIConnectionError as exc:
        raise DeterministicCompileError(
            "Could not reach OpenAI for raw-text drafting. Check your network connection and API key, then try again."
        ) from exc
    except APIStatusError as exc:
        raise DeterministicCompileError(
            f"OpenAI returned an API error while drafting equations ({exc.status_code})."
        ) from exc
    parsed = response.output_parsed
    if parsed is None:
        raise DeterministicCompileError("The OpenAI draft response did not contain a parsed structured output.")
    sanitized_equations, discarded_equation_count = _sanitize_drafted_equations(parsed.equations)
    if not sanitized_equations:
        raise DeterministicCompileError(
            "The OpenAI draft response did not contain any deterministic equations after filtering notes and approximations."
        )
    return DraftGenerationResult(
        spec=DraftModelSpec(equations=sanitized_equations, symbols=[]),
        diagnostics=DraftDiagnostics(
            mode="llm",
            elapsed_seconds=time.perf_counter() - start,
            model=resolved_model,
            timeout_seconds=timeout_seconds,
            prepared_input_chars=len(prepared_raw_text),
            discarded_equation_count=discarded_equation_count,
        ),
    )


def draft_model_spec_from_raw_text(
    raw_text: str,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
) -> DraftModelSpec:
    """Draft a structured model spec from free-form text using OpenAI structured outputs."""
    return draft_model_spec_from_raw_text_with_diagnostics(
        raw_text,
        client=client,
        model=model,
    ).spec


def draft_spec_to_form_defaults(spec: DraftModelSpec) -> tuple[str, dict[str, dict[str, object]]]:
    """Convert a draft spec into GUI form defaults."""
    latex_text = "\n".join(spec.equations)
    symbol_values = {
        symbol.name: {
            "role": symbol.role,
            "description": symbol.description,
            "units": symbol.units,
            "value": "" if symbol.value is None else symbol.value,
            "input_kind": symbol.input_kind,
        }
        for symbol in spec.symbols
    }
    return latex_text, symbol_values


def draft_spec_to_json(spec: DraftModelSpec) -> str:
    """Render a draft spec to formatted JSON for display."""
    return json.dumps(spec.model_dump(), indent=2)
