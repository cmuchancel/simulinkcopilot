"""Compatibility facade to the organized v2 implementation."""

from pipeline_v2.run_pipeline import *  # noqa: F401,F403

if __name__ == "__main__":
    from pipeline_v2.run_pipeline import main
    raise SystemExit(main())
