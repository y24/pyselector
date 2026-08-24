from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pyselector import __version__
from pyselector.config import AppConfig, load_config
from pyselector.install import SKILL_LABELS, install_skill
from pyselector.inspect_runner import (
    run_act,
    run_diff,
    run_expect,
    run_find,
    run_inspect,
    run_tree,
    run_windows,
)
from pyselector.output.json_output import format_error_json, format_version_json
from pyselector.utils.errors import (
    EXIT_ARGUMENT_ERROR,
    EXIT_INTERRUPTED,
    EXIT_UNEXPECTED,
    ActionFailedError,
    ActionNotAllowedError,
    AmbiguousTargetError,
    ArgumentError,
    BackendError,
    CursorError,
    ElementNotFoundError,
    PySelectorError,
    SelectorEvaluationError,
    SelectorEvaluationTimeout,
    ServerUnavailableError,
    StaleRefError,
    TargetWindowNotFoundError,
)
from pyselector.utils.runtime_warnings import configure_runtime_warnings


#: --server の選択肢。pyselector.server.client と同じ値を、import を伴わずに使うために置く。
#: 薄いクライアントの起動コストを増やさないための措置で、値の一致はテストで固定している。
SERVER_MODES = ("auto", "off", "require")

_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.txt"
_RESET = "\033[0m"
_LOGO_GRADIENT_START = (36, 210, 255)
_LOGO_GRADIENT_END = (106, 130, 255)


class ArgumentParseExit(SystemExit):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(code)
        self.message = message


class PySelectorArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"[ERROR] invalid argument: {message}", file=sys.stderr)
        raise ArgumentParseExit(EXIT_ARGUMENT_ERROR, message)


def build_parser(config: AppConfig | None = None) -> argparse.ArgumentParser:
    config = config or AppConfig()
    parser = PySelectorArgumentParser(prog="pyselector")
    subparsers = parser.add_subparsers(dest="command")

    inspect = subparsers.add_parser("inspect", help="Inspect UI element under cursor")
    _add_inspect_options(inspect, config)

    tree = subparsers.add_parser("tree", help="Show UI element tree")
    tree.add_argument("--cursor", action="store_true")
    _add_ref_option(tree)
    tree.add_argument("--window-title")
    tree.add_argument("--window-handle", type=_handle, help="Target window handle (from the windows command)")
    tree.add_argument("--title-re", action="store_true")
    tree.add_argument("--backend", choices=["win32", "uia", "both"], default=config.tree.backend)
    tree.add_argument("--depth", type=_non_negative_int, default=config.tree.depth)
    tree.add_argument("--max-items", type=_positive_int, default=config.tree.max_items)
    tree.add_argument("--only-visible", action="store_true", default=None)
    tree.add_argument("--include-hidden", action="store_true")
    tree.add_argument("--detail", action="store_true")
    tree.add_argument("--summary", action="store_true", help="Show element counts instead of every node")
    tree.add_argument("--compact", action="store_true", help="Reduce fields per node")
    tree.add_argument("--delay", type=_non_negative_int, default=config.tree.delay)
    tree.add_argument("--json", action="store_true")

    windows = subparsers.add_parser("windows", help="List top-level windows")
    _add_windows_options(windows, config)

    find = subparsers.add_parser("find", help="Search UI elements by condition")
    _add_find_options(find, config)

    act = subparsers.add_parser("act", help="Perform a UI action on a single element (disabled by default)")
    _add_act_options(act, config)

    expect = subparsers.add_parser("expect", help="Check a condition about the UI and report whether it holds")
    _add_expect_options(expect, config)

    diff = subparsers.add_parser("diff", help="Compare two tree --json outputs")
    diff.add_argument("before", type=Path, help="tree --json output taken before")
    diff.add_argument("after", type=Path, help="tree --json output taken after")
    diff.add_argument("--compact", action="store_true", help="Reduce fields per node")
    diff.add_argument("--json", action="store_true")

    install_skills = subparsers.add_parser("install-skills", help="Install AI agent skill files into the current directory")
    install_skills.add_argument("--copilot", action="store_true", help="Install the GitHub Copilot skill")
    install_skills.add_argument("--claude", action="store_true", help="Install the Claude Code skill")

    serve = subparsers.add_parser("serve", help="Run the resident server (optional speed-up and element refs)")
    _add_serve_options(serve, config)

    version = subparsers.add_parser("version", help="Show version")
    version.add_argument("--json", action="store_true")

    for name, subparser in subparsers.choices.items():
        if name not in ("serve", "install-skills"):
            _add_server_option(subparser)
    return parser


def _add_ref_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ref",
        metavar="REF",
        help="Target the element with this reference id (only valid while the server holds it)",
    )


def _add_server_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--server",
        choices=list(SERVER_MODES),
        default=None,
        help="auto: use the resident server when reachable, off: never, require: fail when unreachable",
    )


def _add_serve_options(parser: argparse.ArgumentParser, config: AppConfig) -> None:
    parser.add_argument("--idle-timeout", type=_non_negative_int, default=config.server.idle_timeout)
    parser.add_argument("--max-refs", type=_positive_int, default=config.server.max_refs)
    parser.add_argument(
        "--allow-actions",
        action="store_true",
        help="Let this server run act. A resident process keeps that door open, so it is opt-in",
    )
    parser.add_argument("--status", action="store_true", help="Report whether a server is running")
    parser.add_argument("--stop", action="store_true", help="Ask the running server to stop")
    parser.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    configure_runtime_warnings()
    args_list = list(sys.argv[1:] if argv is None else argv)
    json_output = "--json" in args_list
    if not json_output:
        _print_startup_logo()
    if not args_list or (args_list[0].startswith("-") and args_list[0] not in ("-h", "--help")):
        args_list.insert(0, "inspect")
    command = args_list[0] if not args_list[0].startswith("-") else None
    try:
        config = load_config()
        parser = build_parser(config)
        args = parser.parse_args(args_list)
        command = args.command or command
        served = _try_server(args_list, args, config, json_output)
        if served is not None:
            return served
        if args.command == "serve":
            from pyselector.serve_command import run_serve

            return run_serve(args)
        if args.command == "version":
            if args.json:
                print(format_version_json(__version__), end="")
            else:
                print(f"pyselector {__version__}")
            return 0
        if args.command == "install-skills":
            return _run_install_skills(args, parser)
        if args.command == "diff":
            return run_diff(args)
        if args.command == "act":
            _validate_visible_options(args, parser)
            _validate_act_target(args, parser)
            _resolve_act_action(args, parser)
            args.only_visible = _resolve_only_visible(args.only_visible, args.include_hidden, config.act.only_visible)
            args.env_allow_actions = config.act.allow_actions
            return run_act(args)
        if args.command == "tree":
            _validate_visible_options(args, parser)
            _validate_tree_target(args, parser)
            args.only_visible = _resolve_only_visible(args.only_visible, args.include_hidden, config.tree.only_visible)
            args.found_index_trial_count = config.selector.found_index_trial_count
            return run_tree(args)
        if args.command == "windows":
            _validate_visible_options(args, parser)
            args.only_visible = _resolve_only_visible(args.only_visible, args.include_hidden, config.windows.only_visible)
            return run_windows(args)
        if args.command == "find":
            _validate_visible_options(args, parser)
            _validate_find_target(args, parser)
            args.only_visible = _resolve_only_visible(args.only_visible, args.include_hidden, config.find.only_visible)
            args.selector_evaluation_max_items = config.selector.evaluation_max_items
            args.found_index_trial_count = config.selector.found_index_trial_count
            return run_find(args)
        if args.command == "expect":
            _validate_visible_options(args, parser)
            _validate_find_target(args, parser, command="expect")
            _resolve_expectation(args, parser)
            args.only_visible = _resolve_only_visible(args.only_visible, args.include_hidden, config.expect.only_visible)
            return run_expect(args)
        _validate_visible_options(args, parser)
        _validate_inspect_target(args, parser)
        args.only_visible = _resolve_only_visible(args.only_visible, args.include_hidden, config.inspect.only_visible)
        args.selector_evaluation_max_items = config.selector.evaluation_max_items
        args.found_index_trial_count = config.selector.found_index_trial_count
        args.config_path = config.loaded_path
        return run_inspect(args)
    except KeyboardInterrupt:
        _print_error_json(command, json_output, "interrupted", EXIT_INTERRUPTED, "処理を中断しました")
        return EXIT_INTERRUPTED
    except PySelectorError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        _print_error_json(command, json_output, _error_code(exc), exc.exit_code, str(exc))
        return exc.exit_code
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_ARGUMENT_ERROR
        if code != 0:
            message = getattr(exc, "message", "invalid argument")
            _print_error_json(command, json_output, "argument_error", code, message)
        return code
    except Exception as exc:
        print(f"[ERROR] unexpected error: {exc}", file=sys.stderr)
        _print_error_json(command, json_output, "unexpected_error", EXIT_UNEXPECTED, str(exc))
        return EXIT_UNEXPECTED


def _try_server(
    args_list: list[str],
    args: argparse.Namespace,
    config: AppConfig,
    json_output: bool,
) -> int | None:
    """常駐サーバーに丸ごと委ねられるなら委ねる。

    送るのは引数解析済みの内容ではなく argv そのもの。サーバー側も同じ ``main()`` を
    通るので、ローカル実行と挙動が分岐する余地が構造的に無くなる（設計 3）。
    委ねなかった場合は None を返し、呼び出し側がそのままローカル実行に進む。
    """
    from pyselector.server import client as server_client
    from pyselector.server import session as server_session

    if server_session.is_serving():
        # 既にサーバー内で実行している。argv には --server require がそのまま入って
        # いるが、ここから更に投げれば再帰する。要求は既に満たされている。
        return None

    mode = server_client.resolve_mode(getattr(args, "server", None), config.server.enabled)
    decision = server_client.decide(mode, args, json_output)
    if not decision.use_server:
        if mode == "require":
            raise ServerUnavailableError(f"--server require ですが送信できません: {decision.reason}")
        return None

    response = server_client.ServerClient().request(args_list, os.getcwd(), config.server.connect_timeout)
    if response is not None and not response.rejected:
        sys.stdout.write(response.stdout)
        sys.stderr.write(response.stderr)
        return response.exit_code

    if response is not None:
        # サーバーは居たが要求を突き返した（版数違いなど）。理由を伝えてローカルへ。
        reason = response.message or response.error or "unknown"
        if mode == "require":
            raise ServerUnavailableError(f"常駐サーバーが要求を拒否しました: {reason}")
        print(f"[WARN] 常駐サーバーを使えませんでした（{reason}）。ローカルで実行します", file=sys.stderr)
        return None

    if mode == "require":
        raise ServerUnavailableError(
            "常駐サーバーに接続できませんでした。pyselector serve で起動してください"
        )
    if config.server.enabled and config.server.auto_start:
        # 起動は待たない。この 1 回はローカルで返し、次のコマンドから常駐を使う（設計 5.2）。
        server_client.start_server_detached(config.server.idle_timeout, config.act.allow_actions)
    return None


def _run_install_skills(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    kinds = [kind for kind in ("copilot", "claude") if getattr(args, kind)]
    if not kinds:
        parser.error("install-skills requires --copilot or --claude")
    for kind in kinds:
        print(f"[INFO] {SKILL_LABELS[kind]} skill installed: {install_skill(kind)}")
    return 0


_ERROR_CODES: list[tuple[type[PySelectorError], str]] = [
    (ArgumentError, "argument_error"),
    (StaleRefError, "stale_ref"),
    (ServerUnavailableError, "server_unavailable"),
    (ActionNotAllowedError, "action_not_allowed"),
    (ActionFailedError, "action_failed"),
    (AmbiguousTargetError, "ambiguous_target"),
    (SelectorEvaluationTimeout, "selector_evaluation_timeout"),
    (SelectorEvaluationError, "selector_evaluation_failed"),
    (TargetWindowNotFoundError, "target_window_not_found"),
    (ElementNotFoundError, "element_not_found"),
    (CursorError, "cursor_error"),
    (BackendError, "backend_error"),
]


def _error_code(exc: PySelectorError) -> str:
    for error_type, code in _ERROR_CODES:
        if isinstance(exc, error_type):
            return code
    return "error"


def _print_error_json(command: str | None, json_output: bool, code: str, exit_code: int, message: str) -> None:
    if json_output:
        print(format_error_json(command, code, exit_code, message), end="")


def _add_inspect_options(parser: argparse.ArgumentParser, config: AppConfig) -> None:
    parser.add_argument(
        "--delay",
        nargs="?",
        type=_non_negative_int,
        const=5,
        default=None,
        help="Use countdown selection and inspect the cursor position after N seconds",
    )
    parser.add_argument(
        "--at",
        type=_point,
        default=None,
        metavar="X,Y",
        help="Inspect the element at the given screen coordinate without any interaction",
    )
    parser.add_argument(
        "--handle",
        type=_handle,
        default=None,
        help="Inspect the element identified by a window handle",
    )
    _add_ref_option(parser)
    parser.add_argument("--backend", choices=["win32", "uia", "both"], default=config.inspect.backend)
    parser.add_argument("--scope", choices=["window", "desktop"], default=config.inspect.scope)
    parser.add_argument("--detail", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--timeout", type=_positive_int, default=config.inspect.timeout)
    parser.add_argument("--max-items", type=_positive_int, default=config.inspect.max_items)
    parser.add_argument("--only-visible", action="store_true", default=None)
    parser.add_argument("--include-hidden", action="store_true")


def _add_windows_options(parser: argparse.ArgumentParser, config: AppConfig) -> None:
    parser.add_argument("--title", help="Filter by window title (case-insensitive substring)")
    parser.add_argument("--title-re", action="store_true", help="Treat --title as a regular expression")
    parser.add_argument("--process", help="Filter by process name (case-insensitive substring)")
    parser.add_argument("--pid", type=_positive_int, help="Filter by process id")
    parser.add_argument(
        "--include-untitled",
        action="store_true",
        help="Include windows without a title (helper windows are hidden by default)",
    )
    parser.add_argument("--backend", choices=["win32", "uia", "both"], default=config.windows.backend)
    parser.add_argument("--max-items", type=_positive_int, default=config.windows.max_items)
    parser.add_argument("--only-visible", action="store_true", default=None)
    parser.add_argument("--include-hidden", action="store_true")
    parser.add_argument("--compact", action="store_true", help="Reduce fields per window")
    parser.add_argument("--json", action="store_true")


def _add_search_condition_options(parser: argparse.ArgumentParser) -> None:
    """探索の起点と絞り込み条件。find / expect が共有する。"""
    parser.add_argument("--window-title", help="Search inside the window matched by title")
    parser.add_argument("--window-handle", type=_handle, help="Search inside the window with this handle")
    parser.add_argument("--at", type=_point, default=None, metavar="X,Y", help="Search below the element at this coordinate")
    _add_ref_option(parser)
    parser.add_argument("--title-re", action="store_true", help="Treat --window-title as a regular expression")
    parser.add_argument("--text", help="Match window_text (case-insensitive substring)")
    parser.add_argument("--text-re", help="Match window_text by regular expression")
    parser.add_argument("--auto-id", help="Match automation_id exactly")
    parser.add_argument("--control-type", help="Match control_type (case-insensitive)")
    parser.add_argument("--class-name", help="Match class_name exactly")
    parser.add_argument("--enabled-only", action="store_true", help="Keep only enabled elements")


def _add_find_options(parser: argparse.ArgumentParser, config: AppConfig) -> None:
    _add_search_condition_options(parser)
    parser.add_argument("--backend", choices=["win32", "uia", "both"], default=config.find.backend)
    parser.add_argument("--scope", choices=["window", "desktop"], default=config.find.scope)
    parser.add_argument("--depth", type=_non_negative_int, default=config.find.depth)
    parser.add_argument("--max-items", type=_positive_int, default=config.find.max_items)
    parser.add_argument("--limit", type=_positive_int, default=config.find.limit)
    parser.add_argument("--timeout", type=_positive_int, default=config.find.timeout)
    parser.add_argument("--with-selectors", action="store_true", help="Generate selector candidates for the matches")
    parser.add_argument("--selector-limit", type=_positive_int, default=config.find.selector_limit)
    parser.add_argument(
        "--with-state",
        action="store_true",
        help="Read value / checked / selected state for the matches (costs one UIA call per element)",
    )
    parser.add_argument("--only-visible", action="store_true", default=None)
    parser.add_argument("--include-hidden", action="store_true")
    parser.add_argument("--detail", action="store_true")
    parser.add_argument("--compact", action="store_true", help="Reduce fields per element")
    parser.add_argument("--json", action="store_true")


def _add_act_options(parser: argparse.ArgumentParser, config: AppConfig) -> None:
    parser.add_argument("--window-title", help="Search inside the window matched by title")
    parser.add_argument("--window-handle", type=_handle, help="Search inside the window with this handle")
    parser.add_argument("--at", type=_point, default=None, metavar="X,Y", help="Act on the element at this coordinate")
    _add_ref_option(parser)
    parser.add_argument("--title-re", action="store_true", help="Treat --window-title as a regular expression")
    parser.add_argument("--text", help="Match window_text (case-insensitive substring)")
    parser.add_argument("--text-re", help="Match window_text by regular expression")
    parser.add_argument("--auto-id", help="Match automation_id exactly")
    parser.add_argument("--control-type", help="Match control_type (case-insensitive)")
    parser.add_argument("--class-name", help="Match class_name exactly")
    parser.add_argument("--enabled-only", action="store_true", help="Keep only enabled elements")
    parser.add_argument("--index", type=_non_negative_int, help="Pick this match when several elements match")

    actions = parser.add_argument_group("actions")
    actions.add_argument("--click", dest="action", action="store_const", const="click")
    actions.add_argument("--double-click", dest="action", action="store_const", const="double_click")
    actions.add_argument("--right-click", dest="action", action="store_const", const="right_click")
    actions.add_argument("--invoke", dest="action", action="store_const", const="invoke", help="Use the UIA invoke pattern instead of a physical click")
    actions.add_argument("--focus", dest="action", action="store_const", const="focus")
    actions.add_argument("--set-text", dest="set_text", metavar="TEXT", help="Replace the text of an edit control")
    actions.add_argument("--send-keys", dest="send_keys", metavar="KEYS", help="Type keys into the element")

    parser.add_argument("--allow-actions", action="store_true", help="Required to actually perform the action")
    parser.add_argument("--dry-run", action="store_true", help="Resolve the target and report it without acting")
    parser.add_argument("--diff", action="store_true", help="Report what changed in the window around the action")
    parser.add_argument("--backend", choices=["win32", "uia"], default=config.act.backend)
    parser.add_argument("--depth", type=_non_negative_int, default=config.act.depth)
    parser.add_argument("--max-items", type=_positive_int, default=config.act.max_items)
    parser.add_argument("--only-visible", action="store_true", default=None)
    parser.add_argument("--include-hidden", action="store_true")
    parser.add_argument("--json", action="store_true")


def _add_expect_options(parser: argparse.ArgumentParser, config: AppConfig) -> None:
    _add_search_condition_options(parser)
    parser.add_argument("--index", type=_non_negative_int, help="Pick this match when several elements match")
    # 判定はひとつのバックエンドで下す。both を許すと「どちらで満たされたのか」が
    # 曖昧になり、検証の意味が薄れる。act と同じ方針。
    parser.add_argument("--backend", choices=["win32", "uia"], default=config.expect.backend)
    parser.add_argument("--scope", choices=["window", "desktop"], default=config.expect.scope)
    parser.add_argument("--depth", type=_non_negative_int, default=config.expect.depth)
    parser.add_argument("--max-items", type=_positive_int, default=config.expect.max_items)
    parser.add_argument("--limit", type=_positive_int, default=config.expect.limit)
    parser.add_argument("--only-visible", action="store_true", default=None)
    parser.add_argument("--include-hidden", action="store_true")
    parser.add_argument("--compact", action="store_true", help="Reduce fields per element")
    parser.add_argument("--json", action="store_true")

    checks = parser.add_argument_group("expectations")
    checks.add_argument("--exists", dest="expectation", action="store_const", const="exists")
    checks.add_argument("--not-exists", dest="expectation", action="store_const", const="not_exists")
    checks.add_argument("--count", type=_non_negative_int, metavar="N", help="Expect exactly N matches")
    checks.add_argument("--value-equals", metavar="TEXT", help="Expect the element value to equal TEXT")
    checks.add_argument("--value-contains", metavar="TEXT", help="Expect the element value to contain TEXT")
    checks.add_argument("--checked", dest="expectation", action="store_const", const="checked")
    checks.add_argument("--unchecked", dest="expectation", action="store_const", const="unchecked")
    checks.add_argument("--enabled", dest="expectation", action="store_const", const="enabled")
    checks.add_argument("--disabled", dest="expectation", action="store_const", const="disabled")


#: 値を伴う判定。CLI 上の引数名と、内部の判定種別の対応。
_VALUED_EXPECTATIONS = (("count", "count"), ("value_equals", "value_equals"), ("value_contains", "value_contains"))


def _resolve_expectation(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """判定をちょうど 1 つに確定させる。act の操作指定と同じ形にする。"""
    chosen = [kind for name, kind in _VALUED_EXPECTATIONS if getattr(args, name) is not None]
    expected = [getattr(args, name) for name, _ in _VALUED_EXPECTATIONS if getattr(args, name) is not None]
    if args.expectation is not None:
        chosen.append(args.expectation)
        expected.append(None)
    if len(chosen) != 1:
        parser.error(
            "expect requires exactly one expectation "
            "(--exists, --not-exists, --count, --value-equals, --value-contains, "
            "--checked, --unchecked, --enabled or --disabled)"
        )
    args.expectation = chosen[0]
    args.expected = expected[0]


def _resolve_act_action(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    chosen = [name for name in ("set_text", "send_keys") if getattr(args, name) is not None]
    if args.action is not None:
        chosen.append(args.action)
    if len(chosen) != 1:
        parser.error(
            "act requires exactly one action "
            "(--click, --double-click, --right-click, --invoke, --focus, --set-text or --send-keys)"
        )
    action = chosen[0]
    args.action = action
    args.value = getattr(args, action) if action in ("set_text", "send_keys") else None


def _validate_act_target(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    targets = [
        args.at is not None,
        args.window_title is not None,
        args.window_handle is not None,
        args.ref is not None,
    ]
    if sum(1 for target in targets if target) != 1:
        parser.error("act requires exactly one of --at, --ref, --window-title or --window-handle")
    if args.at is not None and _has_element_conditions(args):
        parser.error("--at selects the target directly and cannot be combined with element conditions")


def _has_element_conditions(args: argparse.Namespace) -> bool:
    named = ("text", "text_re", "auto_id", "control_type", "class_name")
    return any(getattr(args, name) is not None for name in named) or args.enabled_only or args.index is not None


def _validate_visible_options(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.only_visible and args.include_hidden:
        parser.error("--only-visible and --include-hidden cannot be used together")


def _validate_inspect_target(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    targets = [args.at is not None, args.handle is not None, args.ref is not None]
    if sum(1 for target in targets if target) > 1:
        parser.error("--at, --handle and --ref cannot be used together")
    if args.delay is not None and any(targets):
        parser.error("--delay cannot be used with --at, --handle or --ref")


def _validate_tree_target(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    targets = [args.cursor, args.window_title is not None, args.window_handle is not None, args.ref is not None]
    if sum(1 for target in targets if target) != 1:
        parser.error("tree requires exactly one of --cursor, --ref, --window-title or --window-handle")


def _validate_find_target(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    command: str = "find",
) -> None:
    targets = [
        args.at is not None,
        args.window_title is not None,
        args.window_handle is not None,
        args.ref is not None,
    ]
    if sum(1 for target in targets if target) != 1:
        parser.error(f"{command} requires exactly one of --at, --ref, --window-title or --window-handle")


def _resolve_only_visible(only_visible_arg: bool | None, include_hidden: bool, config_default: bool) -> bool:
    if include_hidden:
        return False
    if only_visible_arg is not None:
        return only_visible_arg
    return config_default


def _print_startup_logo() -> None:
    """対話的な端末で実行されたときだけロゴを表示する。

    AI エージェントのようにパイプやリダイレクト経由で実行された場合は、
    ロゴが解析対象の出力に混ざるノイズになるため表示しない。
    """
    if not _is_interactive_stdout():
        return
    try:
        logo = _LOGO_PATH.read_text(encoding="utf-8").rstrip()
    except OSError:
        return
    if logo:
        if _use_logo_color():
            logo = _format_logo_gradient(logo)
        print(logo)


def _is_interactive_stdout() -> bool:
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _use_logo_color() -> bool:
    return _is_interactive_stdout() and "NO_COLOR" not in os.environ


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


def _point(value: str) -> tuple[int, int]:
    parts = value.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("must be in X,Y format")
    try:
        return (int(parts[0].strip()), int(parts[1].strip()))
    except ValueError:
        raise argparse.ArgumentTypeError("must be in X,Y format") from None


def _handle(value: str) -> int:
    text = value.strip()
    try:
        parsed = int(text, 16) if text.lower().startswith("0x") else int(text, 10)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer or a 0x-prefixed hex value") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
