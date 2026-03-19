"""Benchmark data models for SimuCompileBench."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class BenchmarkSystemSpec:
    """Serializable benchmark system specification."""

    system_id: str
    tier: str
    family: str
    latex: str
    generated_state_count: int
    max_order: int
    depth: int
    includes_trig: bool
    nonlinear: bool
    parameter_values: dict[str, float] = field(default_factory=dict)
    initial_conditions: dict[str, float] = field(default_factory=dict)
    input_values: dict[str, float] = field(default_factory=dict)
    symbol_config: Mapping[str, str] | None = None
    classification_mode: str = "configured"
    t_span: tuple[float, float] = (0.0, 6.0)
    sample_count: int = 240
    tags: tuple[str, ...] = ()
    expected_failure_stage: str | None = None
    expected_failure_substring: str | None = None
    expected_failure_category: str | None = None
    simulink_expected: bool = True
    graph_fault: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def expects_failure(self) -> bool:
        return self.expected_failure_stage is not None

    def to_metadata(self) -> dict[str, object]:
        """Return a JSON-serializable metadata view."""
        return {
            "system_id": self.system_id,
            "tier": self.tier,
            "family": self.family,
            "generated_state_count": self.generated_state_count,
            "max_order": self.max_order,
            "depth": self.depth,
            "includes_trig": self.includes_trig,
            "nonlinear": self.nonlinear,
            "tags": list(self.tags),
            "parameter_values": self.parameter_values,
            "initial_conditions": self.initial_conditions,
            "input_values": self.input_values,
            "symbol_config": dict(self.symbol_config or {}),
            "classification_mode": self.classification_mode,
            "t_span": list(self.t_span),
            "sample_count": self.sample_count,
            "simulink_expected": self.simulink_expected,
            "expected_failure_stage": self.expected_failure_stage,
            "expected_failure_substring": self.expected_failure_substring,
            "expected_failure_category": self.expected_failure_category,
            "graph_fault": self.graph_fault,
            "expected_properties": self.metadata,
        }
