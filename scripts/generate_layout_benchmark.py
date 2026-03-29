"""Generate layout readability benchmark artifacts."""

from __future__ import annotations

import argparse

from backend.layout_visual_corrector import resolve_visual_repair_config
from simulate.layout_benchmark import run_layout_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-visual-repair", action="store_true", help="Run the OpenAI-backed visual repair stage.")
    parser.add_argument("--output-dir", default=None, help="Optional benchmark output directory.")
    parser.add_argument(
        "--render-backend",
        choices=("matlab", "proxy"),
        default="matlab",
        help="How to generate benchmark images. 'matlab' exports real Simulink canvases.",
    )
    args = parser.parse_args()

    config = resolve_visual_repair_config(artifact_dir=args.output_dir) if args.with_visual_repair else None
    report = run_layout_benchmark(
        output_dir=args.output_dir,
        visual_repair=args.with_visual_repair,
        visual_repair_config=config,
        render_backend=args.render_backend,
    )
    print(f"Wrote layout benchmark for {len(report['cases'])} cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
