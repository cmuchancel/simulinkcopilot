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
    "FromWorkspace": {
        "path": "simulink/Sources/From Workspace",
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
    "exp": "MathFunction",
    "log": "MathFunction",
}
