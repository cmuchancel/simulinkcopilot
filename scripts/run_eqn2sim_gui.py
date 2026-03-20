"""Launch the local Eqn2Sim metadata-first GUI."""

from __future__ import annotations

from eqn2sim_gui.app import create_app


def main() -> None:
    app = create_app()
    app.run(debug=False, host="127.0.0.1", port=5001)


if __name__ == "__main__":
    main()
