from __future__ import annotations

import builtins
import importlib
import sys
import types

import pytest


def _reload_engine_module():
    sys.modules.pop("simulink.engine", None)
    return importlib.import_module("simulink.engine")


class _CompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_detect_matlab_root_prefers_environment_variable(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    matlab_root = tmp_path / "MATLAB_R2025a"
    (matlab_root / "extern/engines/python").mkdir(parents=True)
    monkeypatch.setenv("MATLABROOT", str(matlab_root))
    monkeypatch.setattr(module.shutil, "which", lambda _: None)

    assert module.detect_matlab_root() == matlab_root.resolve()


def test_detect_matlab_root_uses_binary_path(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    monkeypatch.delenv("MATLABROOT", raising=False)
    matlab_root = tmp_path / "MATLAB_R2025a"
    binary_dir = matlab_root / "bin"
    binary_dir.mkdir(parents=True)
    (matlab_root / "extern/engines/python").mkdir(parents=True)
    monkeypatch.setattr(module.shutil, "which", lambda _: str(binary_dir / "matlab"))

    assert module.detect_matlab_root() == matlab_root.resolve()


def test_detect_architecture_name_covers_supported_platforms(monkeypatch) -> None:
    module = _reload_engine_module()
    monkeypatch.setattr(module.sys, "platform", "darwin", raising=False)
    monkeypatch.setattr(module.platform, "machine", lambda: "arm64")
    assert module._detect_architecture_name() == "maca64"

    monkeypatch.setattr(module.platform, "machine", lambda: "x86_64")
    assert module._detect_architecture_name() == "maci64"

    monkeypatch.setattr(module.sys, "platform", "linux", raising=False)
    assert module._detect_architecture_name() == "glnxa64"


def test_detect_architecture_name_rejects_unsupported_platform(monkeypatch) -> None:
    module = _reload_engine_module()
    monkeypatch.setattr(module.sys, "platform", "mystery", raising=False)
    monkeypatch.setattr(module.os, "name", "posix", raising=False)
    with pytest.raises(RuntimeError, match="Unsupported platform"):
        module._detect_architecture_name()


def test_write_arch_file_writes_expected_contents(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    monkeypatch.setattr(module, "_detect_architecture_name", lambda: "glnxa64")

    module._write_arch_file(tmp_path)

    arch_file = tmp_path / "extern/engines/python/dist/matlab/engine/_arch.txt"
    assert arch_file.exists()
    contents = arch_file.read_text(encoding="utf-8")
    assert "glnxa64" in contents
    assert str((tmp_path / "bin" / "glnxa64").resolve()) in contents


def test_install_engine_package_uses_fallback_command(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    install_dir = tmp_path / "extern/engines/python"
    install_dir.mkdir(parents=True)
    calls: list[list[str]] = []

    def fake_run(command, cwd, capture_output, text):
        calls.append(command)
        if len(calls) == 1:
            return _CompletedProcess(1, stdout="pip failed", stderr="boom")
        return _CompletedProcess(0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._install_engine_package(tmp_path)

    assert calls == [
        [module.sys.executable, "-m", "pip", "install", "."],
        [module.sys.executable, "setup.py", "install"],
    ]


def test_install_engine_package_raises_with_command_log(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    install_dir = tmp_path / "extern/engines/python"
    install_dir.mkdir(parents=True)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, cwd, capture_output, text: _CompletedProcess(1, stdout="nope", stderr="still nope"),
    )

    with pytest.raises(RuntimeError, match="Failed to install the MATLAB engine"):
        module._install_engine_package(tmp_path)


def test_bootstrap_engine_from_matlab_root_adds_dist_path(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    dist_dir = tmp_path / "extern/engines/python/dist"
    dist_dir.mkdir(parents=True)
    monkeypatch.setattr(module, "_write_arch_file", lambda _: None)

    module._bootstrap_engine_from_matlab_root(tmp_path)

    assert str(dist_dir.resolve()) in module.sys.path


def test_import_matlab_engine_returns_cached_module(monkeypatch) -> None:
    module = _reload_engine_module()
    cached = types.ModuleType("matlab")
    module._MATLAB_MODULE = cached
    assert module.import_matlab_engine() is cached


def test_import_matlab_engine_bootstraps_after_initial_import_miss(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    module._MATLAB_MODULE = None
    monkeypatch.delitem(sys.modules, "matlab", raising=False)
    monkeypatch.delitem(sys.modules, "matlab.engine", raising=False)

    fake_matlab = types.ModuleType("matlab")
    fake_matlab.__path__ = []
    fake_engine_module = types.ModuleType("matlab.engine")
    fake_matlab.engine = types.SimpleNamespace(start_matlab=lambda *args: "eng")

    monkeypatch.setattr(module, "detect_matlab_root", lambda: tmp_path)
    monkeypatch.setattr(module, "_install_engine_package", lambda root: None)
    real_import = builtins.__import__
    import_attempts = {"matlab": 0}

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("matlab") and import_attempts["matlab"] < 4:
            import_attempts["matlab"] += 1
            raise ModuleNotFoundError(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    def fake_bootstrap(root) -> None:
        sys.modules["matlab"] = fake_matlab
        sys.modules["matlab.engine"] = fake_engine_module

    monkeypatch.setattr(module, "_bootstrap_engine_from_matlab_root", fake_bootstrap)

    assert module.import_matlab_engine() is fake_matlab


def test_import_matlab_engine_reports_install_failure_context(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    module._MATLAB_MODULE = None
    monkeypatch.delitem(sys.modules, "matlab", raising=False)
    monkeypatch.delitem(sys.modules, "matlab.engine", raising=False)
    monkeypatch.setattr(module, "detect_matlab_root", lambda: tmp_path)
    monkeypatch.setattr(module, "_install_engine_package", lambda root: (_ for _ in ()).throw(RuntimeError("broken install")))
    monkeypatch.setattr(module, "_bootstrap_engine_from_matlab_root", lambda root: None)
    monkeypatch.setattr(module.importlib, "import_module", lambda name: (_ for _ in ()).throw(ModuleNotFoundError(name)))
    real_import = builtins.__import__
    import_attempts = {"matlab": 0}

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("matlab") and import_attempts["matlab"] < 4:
            import_attempts["matlab"] += 1
            raise ModuleNotFoundError(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="Install failure: broken install"):
        module.import_matlab_engine()


def test_start_engine_uses_startup_options_and_retries(monkeypatch) -> None:
    module = _reload_engine_module()
    attempts: list[tuple[object, ...]] = []

    class _FakeMatlab:
        class engine:
            @staticmethod
            def start_matlab(*args):
                attempts.append(args)
                if len(attempts) == 1:
                    raise RuntimeError("temporary")
                return "engine-object"

    monkeypatch.setattr(module, "import_matlab_engine", lambda matlab_root=None: _FakeMatlab)
    sleep_calls: list[float] = []
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = module.start_engine(startup_options="-nojvm", retries=2, retry_delay_seconds=0.5)

    assert result == "engine-object"
    assert attempts == [("-nojvm",), ("-nojvm",)]
    assert sleep_calls == [0.5]
