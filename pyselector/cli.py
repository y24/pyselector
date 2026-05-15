from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pyselector import __version__
from pyselector.config import AppConfig, load_config
from pyselector.install import install_roo_skill
from pyselector.inspect_runner import run_inspect, run_tree
from pyselector.utils.errors import EXIT_ARGUMENT_ERROR, EXIT_INTERRUPTED, EXIT_UNEXPECTED, PySelectorError
from pyselector.utils.runtime_warnings import configure_runtime_warnings


_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.txt"
_RESET = "\033[0m"
_LOGO_GRADIENT_START = (36, 210, 255)
_LOGO_GRADIENT_END = (106, 130, 255)


class PySelectorArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"[ERROR] invalid argument: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ARGUMENT_ERROR)


def build_parser(config: AppConfig | None = None) -> argparse.ArgumentParser:
    config = config or AppConfig()
    parser = PySelectorArgumentParser(prog="pyselector")
    subparsers = parser.add_subparsers(dest="command")

    inspect = subparsers.add_parser("inspect", help="Inspect UI element under cursor")
    _add_inspect_options(inspect, config)

    tree = subparsers.add_parser("tree", help="Show UI element tree")
    tree.add_argument("--cursor", action="store_true")
    tree.add_argument("--window-title")
    tree.add_argument("--title-re", action="store_true")
    tree.add_argument("--backend", choices=["win32", "uia", "both"], default=config.tree.backend)
    tree.add_argument("--depth", type=_non_negative_int, default=config.tree.depth)
    tree.add_argument("--max-items", type=_positive_int, default=config.tree.max_items)
    tree.add_argument("--only-visible", action="store_true", default=None)
    tree.add_argument("--include-hidden", action="store_true")
    tree.add_argument("--detail", action="store_true")
    tree.add_argument("--delay", type=_non_negative_int, default=config.tree.delay)
    tree.add_argument("--json", action="store_true")

    install = subparsers.add_parser("install", help="Install helper files for AI agents")
    install.add_argument("--roo", action="store_true", help="Install the Roo Code skill into the current directory")

    subparsers.add_parser("version", help="Show version")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_runtime_warnings()
    args_list = list(sys.argv[1:] if argv is None else argv)
    if "--json" not in args_list:
        _print_startup_logo()
    if not args_list or (args_list[0].startswith("-") and args_list[0] not in ("-h", "--help")):
        args_list.insert(0, "inspect")
    try:
        config = load_config()
        parser = build_parser(config)
        args = parser.parse_args(args_list)
        if args.command == "version":
            print(f"pyselector {__version__}")
            return 0
        if args.command == "install":
            if not args.roo:
                parser.error("install requires --roo")
            path = install_roo_skill()
            print(f"[INFO] Roo Code skill installed: {path}")
            return 0
        if args.command == "tree":
            _validate_visible_options(args, parser)
            if args.cursor == bool(args.window_title):
                parser.error("tree requires exactly one of --cursor or --window-title")
            args.only_visible = _resolve_only_visible(args.only_visible, args.include_hidden, config.tree.only_visible)
            args.found_index_trial_count = config.selector.found_index_trial_count
            return run_tree(args)
        _validate_visible_options(args, parser)
        args.only_visible = _resolve_only_visible(args.only_visible, args.include_hidden, config.inspect.only_visible)
        args.selector_evaluation_max_items = config.selector.evaluation_max_items
        args.found_index_trial_count = config.selector.found_index_trial_count
        args.config_path = config.loaded_path
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


def _add_inspect_options(parser: argparse.ArgumentParser, config: AppConfig) -> None:
    parser.add_argument("--delay", type=_non_negative_int, default=config.inspect.delay, help=argparse.SUPPRESS)
    parser.add_argument("--backend", choices=["win32", "uia", "both"], default=config.inspect.backend)
    parser.add_argument("--scope", choices=["window", "desktop"], default=config.inspect.scope)
    parser.add_argument("--detail", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--timeout", type=_positive_int, default=config.inspect.timeout)
    parser.add_argument("--max-items", type=_positive_int, default=config.inspect.max_items)
    parser.add_argument("--only-visible", action="store_true", default=None)
    parser.add_argument("--include-hidden", action="store_true")


def _validate_visible_options(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.only_visible and args.include_hidden:
        parser.error("--only-visible and --include-hidden cannot be used together")


def _resolve_only_visible(only_visible_arg: bool | None, include_hidden: bool, config_default: bool) -> bool:
    if include_hidden:
        return False
    if only_visible_arg is not None:
        return only_visible_arg
    return config_default


def _print_startup_logo() -> None:
    try:
        logo = _LOGO_PATH.read_text(encoding="utf-8").rstrip()
    except OSError:
        return
    if logo:
        if _use_logo_color():
            logo = _format_logo_gradient(logo)
        print(logo)


def _use_logo_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _format_logo_gradient(logo: str) -> str:
    lines = logo.splitlines()
    width = max((len(line) for line in lines), default=0)
    return "\n".join(_format_logo_line_gradient(line, width) for line in lines)


def _format_logo_line_gradient(line: str, width: int) -> str:
    if not line:
        return line
    denominator = max(width - 1, 1)
    parts = []
    for index, char in enumerate(line):
        if char == " ":
            parts.append(char)
            continue
        ratio = index / denominator
        red = _interpolate(_LOGO_GRADIENT_START[0], _LOGO_GRADIENT_END[0], ratio)
        green = _interpolate(_LOGO_GRADIENT_START[1], _LOGO_GRADIENT_END[1], ratio)
        blue = _interpolate(_LOGO_GRADIENT_START[2], _LOGO_GRADIENT_END[2], ratio)
        parts.append(f"\033[38;2;{red};{green};{blue}m{char}")
    parts.append(_RESET)
    return "".join(parts)


def _interpolate(start: int, end: int, ratio: float) -> int:
    return round(start + (end - start) * ratio)


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
