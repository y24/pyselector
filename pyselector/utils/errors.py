from __future__ import annotations


EXIT_OK = 0
EXIT_ELEMENT_NOT_FOUND = 1
EXIT_TARGET_WINDOW_NOT_FOUND = 2
EXIT_UIA_FAILED = 3
EXIT_WIN32_FAILED = 4
EXIT_SELECTOR_EVALUATION_FAILED = 5
EXIT_AMBIGUOUS_TARGET = 6
EXIT_ACTION_NOT_ALLOWED = 7
EXIT_ACTION_FAILED = 8
EXIT_STALE_REF = 9
EXIT_ARGUMENT_ERROR = 10
EXIT_SERVER_UNAVAILABLE = 11
#: expect の判定が成立しなかった。判定そのものは正常に実行できている。
#: 「判定が動かなかった」（status=error）とは別物として扱う（設計 11 §6.3）。
EXIT_EXPECTATION_FAILED = 12
#: 画像の取得や保存に失敗した。
EXIT_SCREENSHOT_FAILED = 13
EXIT_UNEXPECTED = 100
EXIT_INTERRUPTED = 130


class PySelectorError(Exception):
    exit_code = EXIT_UNEXPECTED


class ArgumentError(PySelectorError):
    exit_code = EXIT_ARGUMENT_ERROR


class CursorError(PySelectorError):
    exit_code = EXIT_ELEMENT_NOT_FOUND


class BackendError(PySelectorError):
    exit_code = EXIT_ELEMENT_NOT_FOUND


class ElementNotFoundError(BackendError):
    exit_code = EXIT_ELEMENT_NOT_FOUND


class TargetWindowNotFoundError(BackendError):
    exit_code = EXIT_TARGET_WINDOW_NOT_FOUND


class SelectorEvaluationError(PySelectorError):
    exit_code = EXIT_SELECTOR_EVALUATION_FAILED


class SelectorEvaluationTimeout(SelectorEvaluationError):
    pass


class AmbiguousTargetError(PySelectorError):
    """操作対象の候補が複数あり、1 つに絞れなかった。"""

    exit_code = EXIT_AMBIGUOUS_TARGET


class ActionNotAllowedError(PySelectorError):
    """UI 操作が明示的に許可されていない。"""

    exit_code = EXIT_ACTION_NOT_ALLOWED


class ActionFailedError(PySelectorError):
    """UI 操作の実行そのものが失敗した。"""

    exit_code = EXIT_ACTION_FAILED


class StaleRefError(PySelectorError):
    """要素参照（ref）が無効になっている。

    サーバーを再起動した、参照表から追い出された、あるいは画面が変わって
    要素そのものが消えた場合に送出する。act では操作を行う前に判定する。
    """

    exit_code = EXIT_STALE_REF


class ServerUnavailableError(PySelectorError):
    """--server require が指定されたが常駐サーバーに接続できなかった。"""

    exit_code = EXIT_SERVER_UNAVAILABLE
