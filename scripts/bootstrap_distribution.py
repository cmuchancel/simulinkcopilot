"""Bootstrap and validate a distributable Eqn2Sim installation."""

from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from pathlib import Path


RUNTIME_IMPORTS = {
    "flask": "Flask",
    "matplotlib": "matplotlib",
    "numpy": "numpy",
    "openai": "openai",
    "pydantic": "pydantic",
    "dotenv": "python-dotenv",
    "scipy": "scipy",
    "sympy": "sympy",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install-runtime",
        action="store_true",
        help="Install runtime Python dependencies from requirements.txt before running checks.",
    )
    parser.add_argument(
        "--editable",
        action="store_true",
        help="Install the repo in editable mode after installing runtime dependencies.",
    )
    parser.add_argument(
        "--skip-matlab-check",
        action="store_true",
        help="Skip MATLAB discovery checks.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    requirements_path = repo_root / "requirements.txt"

    if args.install_runtime:
        install_runtime_dependencies(requirements_path)
        if args.editable:
            install_editable(repo_root)

    missing = missing_runtime_dependencies()
    python_ok = sys.version_info >= (3, 11)
    matlab_summary = None if args.skip_matlab_check else matlab_discovery_summary()

    print("Eqn2Sim distribution check")
    print(f"  repo root: {repo_root}")
    print(f"  python executable: {sys.executable}")
    print(f"  python version: {sys.version.split()[0]}")
    print(f"  python >= 3.11: {'yes' if python_ok else 'no'}")
    print(f"  runtime dependencies installed: {'yes' if not missing else 'no'}")
    if missing:
        print("  missing packages:")
        for package in missing:
            print(f"    - {package}")

    if matlab_summary is not None:
        print(f"  matlab detected: {'yes' if matlab_summary['detected'] else 'no'}")
        if matlab_summary["detected"]:
            print(f"  matlab root: {matlab_summary['root']}")
        else:
            print(f"  matlab detection note: {matlab_summary['message']}")

    print()
    print("Next steps")
    print("  1. Copy .env.example to .env if you want raw-text LLM drafting in the GUI.")
    print("  2. Launch the GUI with: eqn2sim-gui")
    print("  3. In MATLAB, run: run(fullfile(pwd, 'matlab', 'setupEqn2Sim.m'))")

    if not python_ok or missing:
        return 1
    return 0


def install_runtime_dependencies(requirements_path: Path) -> None:
    command = [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)]
    print("Installing runtime dependencies:", " ".join(command))
    subprocess.run(command, check=True)


def install_editable(repo_root: Path) -> None:
    command = [sys.executable, "-m", "pip", "install", "-e", str(repo_root)]
    print("Installing editable package:", " ".join(command))
    subprocess.run(command, check=True)


def missing_runtime_dependencies() -> list[str]:
    missing: list[str] = []
    for module_name, package_name in RUNTIME_IMPORTS.items():
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(package_name)
    return missing


def matlab_discovery_summary() -> dict[str, object]:
    try:
        from simulink.engine import detect_matlab_root

        root = detect_matlab_root()
        return {"detected": True, "root": str(root), "message": ""}
    except Exception as exc:
        return {"detected": False, "root": None, "message": str(exc)}


if __name__ == "__main__":
    raise SystemExit(main())
