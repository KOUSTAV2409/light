"""Entry point for `python -m light`."""

from .app import run


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
