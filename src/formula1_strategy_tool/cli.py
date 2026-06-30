import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Formula 1 Live Strategy Tool",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    parser.parse_args(list(argv) if argv is not None else None)
    print("Formula 1 Live Strategy Tool — ready for development.")


if __name__ == "__main__":
    main()
