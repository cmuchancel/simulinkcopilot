"""Compatibility facade to the organized v2 implementation."""

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_v2.run_pipeline import *  # noqa: F401,F403

if __name__ == "__main__":
    from pipeline_v2.run_pipeline import main
    raise SystemExit(main())
