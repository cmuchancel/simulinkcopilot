"""Compatibility facade to the organized v2 implementation."""

from simulink_v2.test_basic_model import *  # noqa: F401,F403

if __name__ == "__main__":
    from simulink_v2.test_basic_model import main
    raise SystemExit(main())
