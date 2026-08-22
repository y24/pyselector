from __future__ import annotations

from typing import Any, Callable

from pyselector.utils.errors import ActionFailedError

# 値を必要とする操作。CLI 側の検証にも使う。
ACTIONS_WITH_VALUE = ("set_text", "send_keys")

ACTION_NAMES = (
    "click",
    "double_click",
    "right_click",
    "invoke",
    "focus",
    "set_text",
    "send_keys",
)


def perform_action(wrapper: Any, action: str, value: str | None = None) -> str:
    """wrapper に対して 1 つの操作を実行し、実際に使われた手段の名前を返す。

    pywinauto のバックエンドやコントロール種別によって使えるメソッドが違うため、
    候補を順に試し、最初に成功したものを採用する。
    """
    handlers = _HANDLERS.get(action)
    if handlers is None:
        raise ActionFailedError(f"未対応の操作です: {action}")
    if action in ACTIONS_WITH_VALUE and value is None:
        raise ActionFailedError(f"{action} には値の指定が必要です")

    errors: list[str] = []
    for name, call in handlers:
        method = getattr(wrapper, name, None)
        if method is None:
            errors.append(f"{name}: 未対応")
            continue
        try:
            call(method, value)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            continue
        return name
    raise ActionFailedError(f"操作を実行できませんでした（{'; '.join(errors)}）")


def _no_arg(method: Callable[..., Any], value: str | None) -> None:
    method()


def _with_text(method: Callable[..., Any], value: str | None) -> None:
    method(value)


def _type_keys(method: Callable[..., Any], value: str | None) -> None:
    method(value, with_spaces=True, set_foreground=True)


# 操作名 -> (試す wrapper メソッド名, 呼び出し方) の優先順リスト。
_HANDLERS: dict[str, tuple[tuple[str, Callable[..., Any]], ...]] = {
    "click": (("click_input", _no_arg), ("click", _no_arg)),
    "double_click": (("double_click_input", _no_arg), ("double_click", _no_arg)),
    "right_click": (("right_click_input", _no_arg), ("right_click", _no_arg)),
    "invoke": (("invoke", _no_arg), ("click", _no_arg), ("click_input", _no_arg)),
    "focus": (("set_focus", _no_arg),),
    "set_text": (("set_edit_text", _with_text), ("set_text", _with_text)),
    "send_keys": (("type_keys", _type_keys),),
}
