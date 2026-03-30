"""MATLAB Engine bootstrap helpers for Python-driven Simulink workflows."""

from __future__ import annotations

import importlib
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

LOGGER = logging.getLogger(__name__)

_MATLAB_MODULE: ModuleType | None = None


def _configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )


def detect_matlab_root() -> Path:
    """Locate a local MATLAB installation."""
    candidates: list[Path] = []

    env_root = os.environ.get("MATLABROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())

    matlab_binary = shutil.which("matlab")
    if matlab_binary:
        binary_path = Path(matlab_binary).resolve()
        candidates.extend(
            [
                binary_path.parents[1],
                binary_path.parents[2] if len(binary_path.parents) > 2 else binary_path.parents[1],
            ]
        )

    candidates.extend(_platform_matlab_install_candidates())

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        engine_dir = resolved / "extern/engines/python"
        if engine_dir.exists():
            return resolved

    raise RuntimeError(
        "Unable to locate MATLAB. Set the MATLABROOT environment variable, add 'matlab' to PATH, "
        "or install MATLAB in a standard platform location."
    )


def _platform_matlab_install_candidates() -> list[Path]:
    """Return standard platform-specific MATLAB installation candidates."""
    candidates: list[Path] = []

    if sys.platform == "darwin":
        applications_dir = Path("/Applications")
        if applications_dir.exists():
            candidates.extend(sorted(applications_dir.glob("MATLAB_R*.app"), reverse=True))
        return candidates

    if sys.platform.startswith("linux"):
        for root in (Path("/usr/local/MATLAB"), Path("/opt/MATLAB")):
            if root.exists():
                candidates.extend(sorted(root.glob("R*"), reverse=True))
        return candidates

    if os.name == "nt":
        base_dirs: list[Path] = []
        for env_name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
            value = os.environ.get(env_name)
            if value:
                base_dirs.append(Path(value) / "MATLAB")
        for root in base_dirs:
            if root.exists():
                candidates.extend(sorted(root.glob("R*"), reverse=True))
        return candidates

    return candidates


def _detect_architecture_name() -> str:
    if sys.platform == "darwin":
        return "maca64" if platform.machine() == "arm64" else "maci64"
    if sys.platform.startswith("linux"):
        return "glnxa64"
    if os.name == "nt":
        return "win64"
    raise RuntimeError(f"Unsupported platform for MATLAB engine bootstrap: {sys.platform}")


def _write_arch_file(matlab_root: Path) -> None:
    arch = _detect_architecture_name()
    arch_file = matlab_root / "extern/engines/python/dist/matlab/engine/_arch.txt"
    arch_file.parent.mkdir(parents=True, exist_ok=True)
    arch_contents = "\n".join(
        [
            arch,
            str((matlab_root / "bin" / arch).resolve()),
            str((matlab_root / "extern/engines/python/dist/matlab/engine" / arch).resolve()),
            str((matlab_root / "extern/bin" / arch).resolve()),
        ]
    )
    if not arch_file.exists() or arch_file.read_text(encoding="utf-8").strip() != arch_contents.strip():
        arch_file.write_text(arch_contents + "\n", encoding="utf-8")


def _install_engine_package(matlab_root: Path) -> None:
    install_dir = matlab_root / "extern/engines/python"
    if not install_dir.exists():
        raise RuntimeError(f"MATLAB engine install directory not found: {install_dir}")

    commands = [
        [sys.executable, "-m", "pip", "install", "."],
        [sys.executable, "setup.py", "install"],
    ]

    failures: list[str] = []
    for command in commands:
        LOGGER.info("Attempting MATLAB engine install with: %s", " ".join(command))
        result = subprocess.run(
            command,
            cwd=install_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            LOGGER.info("MATLAB engine install command succeeded: %s", " ".join(command))
            return
        failures.append(
            f"$ {' '.join(command)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}".strip()
        )

    raise RuntimeError(
        "Failed to install the MATLAB engine with the bundled installers.\n" + "\n\n".join(failures)
    )


def _bootstrap_engine_from_matlab_root(matlab_root: Path) -> None:
    _write_arch_file(matlab_root)
    dist_dir = matlab_root / "extern/engines/python/dist"
    if not dist_dir.exists():
        raise RuntimeError(f"Bundled MATLAB engine source directory not found: {dist_dir}")
    dist_path = str(dist_dir.resolve())
    if dist_path not in sys.path:
        sys.path.insert(0, dist_path)


def _purge_matlab_modules() -> None:
    """Drop partially imported MATLAB modules before retrying another bootstrap path."""
    for module_name in ("matlab.engine", "matlab"):
        sys.modules.pop(module_name, None)


def import_matlab_engine(matlab_root: str | Path | None = None) -> ModuleType:
    """Import matlab.engine, installing or bootstrapping it if needed."""
    global _MATLAB_MODULE

    if _MATLAB_MODULE is not None:
        return _MATLAB_MODULE

    initial_import_error: Exception | None = None
    initial_import_missing = False
    try:
        import matlab  # type: ignore[import-not-found]
        import matlab.engine  # type: ignore[import-not-found]

        _MATLAB_MODULE = matlab
        return matlab
    except ModuleNotFoundError:
        initial_import_missing = True
    except Exception as exc:
        # A broken wheel in the venv should not block the bundled MATLAB dist fallback.
        initial_import_error = exc
        _purge_matlab_modules()

    _configure_logging()
    resolved_root = Path(matlab_root).expanduser().resolve() if matlab_root else detect_matlab_root()
    LOGGER.info("Using MATLAB root: %s", resolved_root)

    install_error: Exception | None = None
    if initial_import_missing:
        try:
            _install_engine_package(resolved_root)
        except Exception as exc:  # pragma: no cover - exercised only on broken installs
            install_error = exc
            LOGGER.warning("Bundled MATLAB engine installation failed: %s", exc)

    try:
        import matlab  # type: ignore[import-not-found]
        import matlab.engine  # type: ignore[import-not-found]

        _MATLAB_MODULE = matlab
        return matlab
    except Exception:
        _purge_matlab_modules()
        _bootstrap_engine_from_matlab_root(resolved_root)

    try:
        matlab = importlib.import_module("matlab")
        importlib.import_module("matlab.engine")
    except Exception as exc:
        message = (
            "Unable to import matlab.engine after attempting installation and source bootstrap. "
            f"MATLAB root: {resolved_root}."
        )
        if initial_import_error is not None:
            message += f" Initial import failure: {initial_import_error}"
        if install_error is not None:
            message += f" Install failure: {install_error}"
        raise RuntimeError(message) from exc

    _MATLAB_MODULE = matlab
    return matlab


def start_engine(
    startup_options: str | None = None,
    retries: int = 3,
    retry_delay_seconds: float = 2.0,
    matlab_root: str | Path | None = None,
):
    """Start a MATLAB engine session with retry logic and clear failure messages."""
    _configure_logging()
    matlab = import_matlab_engine(matlab_root=matlab_root)

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            LOGGER.info("Starting MATLAB engine (attempt %s/%s)", attempt, retries)
            if startup_options:
                eng = matlab.engine.start_matlab(startup_options)
            else:
                eng = matlab.engine.start_matlab()
            LOGGER.info("MATLAB engine started successfully.")
            return eng
        except Exception as exc:  # pragma: no cover - depends on local MATLAB state
            last_error = exc
            LOGGER.exception("MATLAB engine failed to start on attempt %s.", attempt)
            if attempt < retries:
                time.sleep(retry_delay_seconds * attempt)

    raise RuntimeError(
        "Failed to start MATLAB after "
        f"{retries} attempts. Check MATLAB licensing, sign-in state, and desktop startup. "
        f"Last error: {last_error}"
    ) from last_error
