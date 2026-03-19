"""Common Simulink block library paths and layout defaults."""

CONSTANT_BLOCK = "simulink/Sources/Constant"
GAIN_BLOCK = "simulink/Math Operations/Gain"
SUM_BLOCK = "simulink/Math Operations/Sum"
INTEGRATOR_BLOCK = "simulink/Continuous/Integrator"
SCOPE_BLOCK = "simulink/Sinks/Scope"

COMMON_BLOCK_LIBRARY_PATHS = {
    "constant": CONSTANT_BLOCK,
    "gain": GAIN_BLOCK,
    "sum": SUM_BLOCK,
    "integrator": INTEGRATOR_BLOCK,
    "scope": SCOPE_BLOCK,
}

DEFAULT_BLOCK_POSITION = (40, 40, 120, 80)
DEFAULT_HORIZONTAL_SPACING = 150
DEFAULT_VERTICAL_SPACING = 100
