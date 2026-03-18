"""Signal extraction helpers for engine-driven Simulink simulations."""

from __future__ import annotations

import numpy as np

from latex_frontend.symbols import DeterministicCompileError


def _to_numpy(array_like) -> np.ndarray:
    return np.asarray(array_like, dtype=float)


def extract_simulink_signals(
    eng,
    sim_output,
    *,
    output_names: list[str],
    workspace_var: str = "simOutPy",
) -> dict[str, object]:
    """Extract time and output signals from a SimulationOutput object."""
    eng.workspace[workspace_var] = sim_output
    num_signals = int(eng.eval(f"numel({workspace_var}.yout.signals)", nargout=1))
    if num_signals != len(output_names):
        raise DeterministicCompileError(
            f"Expected {len(output_names)} Simulink outputs, found {num_signals}."
        )

    time = _to_numpy(eng.eval(f"{workspace_var}.yout.time", nargout=1)).reshape(-1)
    if time.size == 0:
        raise DeterministicCompileError("Simulink simulation returned an empty time vector.")

    signal_columns: list[np.ndarray] = []
    signal_map: dict[str, np.ndarray] = {}
    for index, name in enumerate(output_names, start=1):
        values = _to_numpy(eng.eval(f"{workspace_var}.yout.signals({index}).values", nargout=1)).reshape(-1)
        if values.shape[0] != time.shape[0]:
            raise DeterministicCompileError(
                f"Signal {name!r} has {values.shape[0]} samples but time has {time.shape[0]}."
            )
        signal_columns.append(values)
        signal_map[name] = values

    states = np.column_stack(signal_columns) if signal_columns else np.zeros((time.shape[0], 0))
    return {
        "t": time,
        "states": states,
        "state_names": list(output_names),
        "signals": signal_map,
    }
