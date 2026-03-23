# Distribution Setup

This repo is now structured so a recipient can install and run it without editing machine-specific paths.

## Python Quick Start

From the repo root:

```bash
python3 -m scripts.bootstrap_distribution --install-runtime --editable
```

This will:

1. install runtime Python dependencies from `requirements.txt`
2. install the repo in editable mode
3. check whether MATLAB can be discovered on the local machine

If you want a read-only check without installing anything:

```bash
python3 -m scripts.bootstrap_distribution
```

## GUI

Launch the local GUI with either of these:

```bash
eqn2sim-gui
```

or

```bash
python3 run_eqn2sim_gui.py
```

or

```bash
python3 -m scripts.run_eqn2sim_gui
```

Then open:

```text
http://127.0.0.1:5001
```

If you want raw-text drafting in the GUI, copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

## MATLAB

Inside MATLAB, from the repo root:

```matlab
run(fullfile(pwd, "matlab", "setupEqn2Sim.m"))
```

This adds the bridge functions to the MATLAB path without requiring a hardcoded machine-specific path.

The bridge then derives the repo root automatically and calls the shared Python backend from there.

## What A Recipient Still Needs

- Python 3.11 or newer
- MATLAB + Simulink for `.slx` generation and Simulink-backed validation
- the required Python packages
- an OpenAI API key only if they want raw-text drafting in the GUI
