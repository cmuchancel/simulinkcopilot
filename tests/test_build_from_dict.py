"""Round-trip test for building a Simulink model from a Python dictionary."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ir.simulink_dict import example_model
from simulink.builder import build_model
from simulink.engine import start_engine
from simulink.utils import sanitize_block_name


def _connection_exists(eng, model_name: str, src_block: str, src_port: str, dst_block: str, dst_port: str) -> bool:
    src_name = sanitize_block_name(src_block)
    dst_name = sanitize_block_name(dst_block)
    eng.eval(
        f"pc_tmp = get_param('{model_name}/{dst_name}', 'PortConnectivity');",
        nargout=0,
    )
    return bool(
        eng.eval(
            f"isequal(pc_tmp({int(dst_port)}).SrcBlock, get_param('{model_name}/{src_name}', 'Handle'))",
            nargout=1,
        )
    )


def main() -> int:
    eng = start_engine(retries=3, retry_delay_seconds=3.0)
    model_dict = example_model("dict_round_trip_model")
    output_dir = Path(__file__).resolve().parents[1] / "generated_models"

    try:
        build_result = build_model(
            eng,
            model_dict,
            output_dir=output_dir,
            open_after_build=True,
            run_simulation=True,
        )
        model_name = build_result["model_name"]
        model_file = Path(build_result["model_file"])

        assert model_file.exists(), f"Expected Simulink file to exist: {model_file}"
        assert bool(eng.eval(f"bdIsLoaded('{model_name}')", nargout=1)), f"Model {model_name} is not loaded."

        line_count = int(eng.eval(f"numel(get_param('{model_name}', 'Lines'))", nargout=1))
        assert line_count == len(model_dict["connections"]), (
            f"Expected {len(model_dict['connections'])} connections, found {line_count}."
        )

        for src_block, src_port, dst_block, dst_port in model_dict["connections"]:
            assert _connection_exists(eng, model_name, src_block, src_port, dst_block, dst_port), (
                f"Missing connection {src_block}/{src_port} -> {dst_block}/{dst_port}"
            )

        print(f"Built and verified {model_file}")
        return 0
    finally:
        eng.quit()


if __name__ == "__main__":
    raise SystemExit(main())
