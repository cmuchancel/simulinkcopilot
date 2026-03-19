"""Compatibility facade to the organized v2 implementation."""

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulink_v2.test_basic_model import *  # noqa: F401,F403

if __name__ == "__main__":
    from simulink_v2.test_basic_model import main
    raise SystemExit(main())
