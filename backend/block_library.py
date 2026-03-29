"""Simulink block-library definitions used by the deterministic backend."""

from __future__ import annotations


BLOCK_LIBRARY = {
    "Integrator": {
        "path": "simulink/Continuous/Integrator",
        "ports": ["in", "out"],
    },
    "Gain": {
        "path": "simulink/Math Operations/Gain",
        "ports": ["in", "out"],
    },
    "Sum": {
        "path": "simulink/Math Operations/Sum",
        "ports": ["in", "out"],
    },
    "Product": {
        "path": "simulink/Math Operations/Product",
        "ports": ["in", "out"],
    },
    "Divide": {
        "path": "simulink/Math Operations/Divide",
        "ports": ["in", "out"],
    },
    "Constant": {
        "path": "simulink/Sources/Constant",
        "ports": ["out"],
    },
    "Step": {
        "path": "simulink/Sources/Step",
        "ports": ["out"],
    },
    "Ramp": {
        "path": "simulink/Sources/Ramp",
        "ports": ["out"],
    },
    "PulseGenerator": {
        "path": "simulink/Sources/Pulse Generator",
        "ports": ["out"],
    },
    "SineWave": {
        "path": "simulink/Sources/Sine Wave",
        "ports": ["out"],
    },
    "MATLABFunction": {
        "path": "simulink/User-Defined Functions/MATLAB Function",
        "ports": ["in", "out"],
    },
    "FromWorkspace": {
        "path": "simulink/Sources/From Workspace",
        "ports": ["out"],
    },
    "Clock": {
        "path": "simulink/Sources/Clock",
        "ports": ["out"],
    },
    "SignalGenerator": {
        "path": "simulink/Sources/Signal Generator",
        "ports": ["out"],
    },
    "RepeatingSequence": {
        "path": "simulink/Sources/Repeating Sequence",
        "ports": ["out"],
    },
    "RandomNumber": {
        "path": "simulink/Sources/Random Number",
        "ports": ["out"],
    },
    "UniformRandomNumber": {
        "path": "simulink/Sources/Uniform Random Number",
        "ports": ["out"],
    },
    "BandLimitedWhiteNoise": {
        "path": "simulink/Sources/Band-Limited White Noise",
        "ports": ["out"],
    },
    "Inport": {
        "path": "simulink/Sources/In1",
        "ports": ["out"],
    },
    "Outport": {
        "path": "simulink/Sinks/Out1",
        "ports": ["in"],
    },
    "Scope": {
        "path": "simulink/Sinks/Scope",
        "ports": ["in"],
    },
    "ToWorkspace": {
        "path": "simulink/Sinks/To Workspace",
        "ports": ["in"],
    },
    "TrigonometricFunction": {
        "path": "simulink/Math Operations/Trigonometric Function",
        "ports": ["in", "out"],
    },
    "MathFunction": {
        "path": "simulink/Math Operations/Math Function",
        "ports": ["in", "out"],
    },
    "AlgebraicConstraint": {
        "path": "simulink/Math Operations/Algebraic Constraint",
        "ports": ["in", "out"],
    },
    "Abs": {
        "path": "simulink/Math Operations/Abs",
        "ports": ["in", "out"],
    },
    "MinMax": {
        "path": "simulink/Math Operations/MinMax",
        "ports": ["in", "out"],
    },
    "Saturation": {
        "path": "simulink/Discontinuities/Saturation",
        "ports": ["in", "out"],
    },
    "DeadZone": {
        "path": "simulink/Discontinuities/Dead Zone",
        "ports": ["in", "out"],
    },
    "Relay": {
        "path": "simulink/Discontinuities/Relay",
        "ports": ["in", "out"],
    },
    "TransportDelay": {
        "path": "simulink/Continuous/Transport Delay",
        "ports": ["in", "out"],
    },
    "Switch": {
        "path": "simulink/Signal Routing/Switch",
        "ports": ["in", "out"],
    },
    "RelationalOperator": {
        "path": "simulink/Logic and Bit Operations/Relational Operator",
        "ports": ["in", "out"],
    },
    "LogicOperator": {
        "path": "simulink/Logic and Bit Operations/Logical Operator",
        "ports": ["in", "out"],
    },
    "Sign": {
        "path": "simulink/Math Operations/Sign",
        "ports": ["in", "out"],
    },
    "Subsystem": {
        "path": "simulink/Ports & Subsystems/Subsystem",
        "ports": ["in", "out"],
    },
}


GRAPH_OP_TO_BLOCK = {
    "integrator": "Integrator",
    "add": "Sum",
    "sum": "Sum",
    "mul": "Product",
    "gain": "Product",
    "div": "Divide",
    "constant": "Constant",
    "symbol_input": "Constant",
    "negate": "Gain",
    "sin": "TrigonometricFunction",
    "cos": "TrigonometricFunction",
    "tan": "TrigonometricFunction",
    "asin": "TrigonometricFunction",
    "acos": "TrigonometricFunction",
    "atan": "TrigonometricFunction",
    "sinh": "TrigonometricFunction",
    "cosh": "TrigonometricFunction",
    "tanh": "TrigonometricFunction",
    "asinh": "TrigonometricFunction",
    "acosh": "TrigonometricFunction",
    "atanh": "TrigonometricFunction",
    "atan2": "TrigonometricFunction",
    "abs": "Abs",
    "min": "MinMax",
    "max": "MinMax",
    "sat": "Saturation",
    "exp": "MathFunction",
    "log": "MathFunction",
    "sqrt": "MathFunction",
}
