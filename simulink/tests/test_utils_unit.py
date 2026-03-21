from __future__ import annotations

import pytest

from simulink.utils import (
    ensure_output_dir,
    format_port,
    format_position,
    matlab_param_value,
    sanitize_block_name,
    validate_library_path,
)


def test_sanitize_block_name_normalizes_invalid_characters_and_digit_prefix() -> None:
    assert sanitize_block_name("  gain block 1  ") == "gain_block_1"
    assert sanitize_block_name("123-start") == "blk_123_start"


@pytest.mark.parametrize("name", ["", "   ", "!!!"])
def test_sanitize_block_name_rejects_invalid_names(name: str) -> None:
    with pytest.raises(ValueError):
        sanitize_block_name(name)


def test_format_port_accepts_integers_and_strings() -> None:
    assert format_port(2) == "2"
    assert format_port("  out ") == "out"


@pytest.mark.parametrize("value", [0, -1, "   "])
def test_format_port_rejects_invalid_values(value) -> None:
    with pytest.raises(ValueError):
        format_port(value)


def test_validate_library_path_accepts_expected_simulink_paths() -> None:
    assert validate_library_path("simulink/Sources/Constant") == "simulink/Sources/Constant"


@pytest.mark.parametrize("path", ["", "Constant"])
def test_validate_library_path_rejects_invalid_values(path: str) -> None:
    with pytest.raises(ValueError):
        validate_library_path(path)


def test_format_position_requires_exactly_four_values() -> None:
    assert format_position([1, 2, 3, 4]) == "[1 2 3 4]"
    with pytest.raises(ValueError):
        format_position([1, 2, 3])


def test_matlab_param_value_formats_supported_types() -> None:
    assert matlab_param_value(True) == "on"
    assert matlab_param_value(False) == "off"
    assert matlab_param_value(3.5) == "3.5"
    assert matlab_param_value("abc") == "abc"
    assert matlab_param_value([1, 2, 3]) == "[1 2 3]"
    with pytest.raises(TypeError):
        matlab_param_value({"bad": "type"})


def test_ensure_output_dir_creates_missing_directory(tmp_path) -> None:
    directory = ensure_output_dir(tmp_path / "nested" / "output")
    assert directory.exists()
    assert directory.is_dir()
