from __future__ import annotations

import argparse
import sys

from pyselector import __version__
from pyselector.inspect_runner import run_inspect, run_tree
from pyselector.utils.errors import EXIT_ARGUMENT_ERROR, EXIT_INTERRUPTED, EXIT_UNEXPECTED, PySelectorError


class PySelectorArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"[ERROR] invalid argument: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ARGUMENT_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = PySelectorArgumentParser(prog="pyselector")
    subparsers = parser.add_subparsers(dest="command")

    inspect = subparsers.add_parser("inspect", help="Inspect UI element under cursor")
    _add_inspect_options(inspect)

    tree = subparsers.add_parser("tree", help="Show UI element tree")
    tree.add_argument("--cursor", action="store_true")
    tree.add_argument("--window-title")
    tree.add_argument("--title-re", action="store_true")
    tree.add_argument("--backend", choices=["win32", "uia"], default="win32")
    tree.add_argument("--depth", type=_non_negative_int, default=3)
    tree.add_argument("--max-items", type=_positive_int, default=200)
    tree.add_argument("--only-visible", action="store_true", default=False)
    tree.add_argument("--include-hidden", action="store_true")
    tree.add_argument("--detail", action="store_true")
    tree.add_argument("--delay", type=_non_negative_int, default=5)

    subparsers.add_parser("version", help="Show version")
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or (args_list[0].startswith("-") and args_list[0] not in ("-h", "--help")):
        args_list.insert(0, "inspect")
    parser = build_parser()
    try:
        args = parser.parse_args(args_list)
        if args.command == "version":
            print(f"pyselector {__version__}")
            return 0
        if args.command == "tree":
            _validate_visible_options(args, parser)
            if args.cursor == bool(args.window_title):
                parser.error("tree requires exactly one of --cursor or --window-title")
            args.only_visible = False if args.include_hidden else True
            return run_tree(args)
        _validate_visible_options(args, parser)
        args.only_visible = False if args.include_hidden else True
        return run_inspect(args)
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except PySelectorError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return exc.exit_code
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_ARGUMENT_ERROR
        return code
    except Exception as exc:
        print(f"[ERROR] unexpected error: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED


def _add_inspect_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--delay", type=_non_negative_int, default=5)
    parser.add_argument("--backend", choices=["win32", "uia", "both"], default="both")
    parser.add_argument("--scope", choices=["window", "desktop"], default="window")
    parser.add_argument("--detail", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--timeout", type=_positive_int, default=5)
    parser.add_argument("--max-items", type=_positive_int)
    parser.add_argument("--only-visible", action="store_true", default=False)
    parser.add_argument("--include-hidden", action="store_true")


def _validate_visible_options(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.only_visible and args.include_hidden:
        parser.error("--only-visible and --include-hidden cannot be used together")


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
