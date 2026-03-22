from __future__ import annotations

import builtins
import importlib
from pathlib import Path as StdPath
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


def test_detect_matlab_root_skips_duplicate_candidates_and_raises_when_missing(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    matlab_root = tmp_path / "MATLAB_R2025a"
    binary_dir = matlab_root / "bin"
    binary_dir.mkdir(parents=True)
    (matlab_root / "extern/engines/python").mkdir(parents=True)
    monkeypatch.setenv("MATLABROOT", str(matlab_root))
    monkeypatch.setattr(module.shutil, "which", lambda _: str(binary_dir / "matlab"))

    assert module.detect_matlab_root() == matlab_root.resolve()

    missing_applications = tmp_path / "Applications"

    def fake_path(value):
        if value == "/Applications":
            return missing_applications
        return StdPath(value)

    monkeypatch.delenv("MATLABROOT", raising=False)
    monkeypatch.setattr(module, "Path", fake_path)
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="Unable to locate MATLAB"):
        module.detect_matlab_root()


def test_detect_matlab_root_skips_missing_and_duplicate_candidates_before_application_hit(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    missing_root = tmp_path / "missing_matlab"
    binary_dir = missing_root / "bin"
    binary_dir.mkdir(parents=True)
    applications_dir = tmp_path / "Applications"
    app_root = applications_dir / "MATLAB_R2025b.app"
    (app_root / "extern/engines/python").mkdir(parents=True)

    def fake_path(value):
        if value == "/Applications":
            return applications_dir
        return StdPath(value)

    monkeypatch.setenv("MATLABROOT", str(missing_root))
    monkeypatch.setattr(module, "Path", fake_path)
    monkeypatch.setattr(module.shutil, "which", lambda _: str(binary_dir / "matlab"))

    assert module.detect_matlab_root() == app_root.resolve()


def test_detect_architecture_name_covers_supported_platforms(monkeypatch) -> None:
    module = _reload_engine_module()
    monkeypatch.setattr(module.sys, "platform", "darwin", raising=False)
    monkeypatch.setattr(module.platform, "machine", lambda: "arm64")
    assert module._detect_architecture_name() == "maca64"

    monkeypatch.setattr(module.platform, "machine", lambda: "x86_64")
    assert module._detect_architecture_name() == "maci64"

    monkeypatch.setattr(module.sys, "platform", "linux", raising=False)
    assert module._detect_architecture_name() == "glnxa64"

    monkeypatch.setattr(module.os, "name", "nt", raising=False)
    monkeypatch.setattr(module.sys, "platform", "win32", raising=False)
    assert module._detect_architecture_name() == "win64"


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


def test_write_arch_file_skips_rewrite_when_contents_match(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    monkeypatch.setattr(module, "_detect_architecture_name", lambda: "glnxa64")
    module._write_arch_file(tmp_path)

    monkeypatch.setattr(module.Path, "write_text", lambda self, *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected write")))
    module._write_arch_file(tmp_path)


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


def test_install_engine_package_rejects_missing_install_directory(tmp_path) -> None:
    module = _reload_engine_module()
    with pytest.raises(RuntimeError, match="install directory not found"):
        module._install_engine_package(tmp_path)


def test_bootstrap_engine_from_matlab_root_adds_dist_path(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    dist_dir = tmp_path / "extern/engines/python/dist"
    dist_dir.mkdir(parents=True)
    monkeypatch.setattr(module, "_write_arch_file", lambda _: None)

    module._bootstrap_engine_from_matlab_root(tmp_path)

    assert str(dist_dir.resolve()) in module.sys.path


def test_bootstrap_engine_from_matlab_root_rejects_missing_dist_and_preserves_existing_path(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    monkeypatch.setattr(module, "_write_arch_file", lambda _: None)
    with pytest.raises(RuntimeError, match="source directory not found"):
        module._bootstrap_engine_from_matlab_root(tmp_path)

    dist_dir = tmp_path / "extern/engines/python/dist"
    dist_dir.mkdir(parents=True)
    dist_path = str(dist_dir.resolve())
    module.sys.path.insert(0, dist_path)
    original_count = module.sys.path.count(dist_path)
    module._bootstrap_engine_from_matlab_root(tmp_path)
    assert module.sys.path.count(dist_path) == original_count
    while dist_path in module.sys.path:
        module.sys.path.remove(dist_path)


def test_configure_logging_calls_basic_config_when_root_has_no_handlers(monkeypatch) -> None:
    module = _reload_engine_module()
    class _FakeRootLogger:
        def __init__(self) -> None:
            self.handlers: list[object] = []

        def addHandler(self, _handler) -> None:  # pragma: no cover - pytest may call this via monkeypatch window
            pass

        def removeHandler(self, _handler) -> None:  # pragma: no cover - pytest may call this via monkeypatch window
            pass

    root_logger = _FakeRootLogger()
    basic_config_calls: list[dict[str, object]] = []
    monkeypatch.setattr(module.logging, "getLogger", lambda *args, **kwargs: root_logger)
    monkeypatch.setattr(module.logging, "basicConfig", lambda **kwargs: basic_config_calls.append(kwargs))

    module._configure_logging()

    assert basic_config_calls


def test_import_matlab_engine_succeeds_immediately_when_module_available(monkeypatch) -> None:
    module = _reload_engine_module()
    module._MATLAB_MODULE = None
    fake_matlab = types.ModuleType("matlab")
    fake_engine = types.ModuleType("matlab.engine")
    fake_matlab.__path__ = []
    sys.modules["matlab"] = fake_matlab
    sys.modules["matlab.engine"] = fake_engine
    try:
        assert module.import_matlab_engine() is fake_matlab
    finally:
        sys.modules.pop("matlab", None)
        sys.modules.pop("matlab.engine", None)


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


def test_import_matlab_engine_succeeds_after_install_without_bootstrap(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    module._MATLAB_MODULE = None
    monkeypatch.delitem(sys.modules, "matlab", raising=False)
    monkeypatch.delitem(sys.modules, "matlab.engine", raising=False)
    fake_matlab = types.ModuleType("matlab")
    fake_engine_module = types.ModuleType("matlab.engine")
    fake_matlab.__path__ = []
    fake_engine_module.start_matlab = lambda *args: "eng"
    fake_matlab.engine = fake_engine_module
    monkeypatch.setattr(module, "detect_matlab_root", lambda: tmp_path)

    def fake_install(_root) -> None:
        sys.modules["matlab"] = fake_matlab
        sys.modules["matlab.engine"] = fake_engine_module

    monkeypatch.setattr(module, "_install_engine_package", fake_install)
    monkeypatch.setattr(
        module,
        "_bootstrap_engine_from_matlab_root",
        lambda _root: (_ for _ in ()).throw(AssertionError("bootstrap should not run")),
    )
    real_import = builtins.__import__
    import_attempts = {"matlab": 0}

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("matlab") and import_attempts["matlab"] < 1:
            import_attempts["matlab"] += 1
            raise ModuleNotFoundError(name)
        if name == "matlab":
            return fake_matlab
        if name == "matlab.engine":
            return fake_matlab
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    try:
        assert module.import_matlab_engine() is fake_matlab
    finally:
        sys.modules.pop("matlab", None)
        sys.modules.pop("matlab.engine", None)


def test_import_matlab_engine_reports_failure_without_install_context(monkeypatch, tmp_path) -> None:
    module = _reload_engine_module()
    module._MATLAB_MODULE = None
    monkeypatch.delitem(sys.modules, "matlab", raising=False)
    monkeypatch.delitem(sys.modules, "matlab.engine", raising=False)
    monkeypatch.setattr(module, "detect_matlab_root", lambda: tmp_path)
    monkeypatch.setattr(module, "_install_engine_package", lambda root: None)
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

    with pytest.raises(RuntimeError, match="Unable to import matlab.engine"):
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


def test_start_engine_uses_default_start_matlab_and_reports_exhausted_retries(monkeypatch) -> None:
    module = _reload_engine_module()
    attempts: list[tuple[object, ...]] = []

    class _FailingMatlab:
        class engine:
            @staticmethod
            def start_matlab(*args):
                attempts.append(args)
                raise RuntimeError("still failing")

    monkeypatch.setattr(module, "import_matlab_engine", lambda matlab_root=None: _FailingMatlab)
    sleep_calls: list[float] = []
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    with pytest.raises(RuntimeError, match="Failed to start MATLAB after 2 attempts"):
        module.start_engine(retries=2, retry_delay_seconds=0.25)

    assert attempts == [(), ()]
    assert sleep_calls == [0.25]
