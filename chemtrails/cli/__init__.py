from __future__ import annotations

import argparse

from chemtrails.cli import show


def main() -> None:
    options = parse_options()
    options.func(options)


def parse_options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trace and profile facility.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="Run in debug mode",
    )

    subparsers = parser.add_subparsers(required=True, dest="command")

    show.register(subparsers)

    return parser.parse_args()
