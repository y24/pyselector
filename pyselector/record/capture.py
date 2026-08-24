from __future__ import annotations

from argparse import Namespace
from datetime import datetime
from typing import Any, Callable

from pyselector.model.element_info import ElementInfo
from pyselector.model.selector_candidate import SelectorEvaluation
from pyselector.record import store
from pyselector.record.codegen import WINDOW_SELF
from pyselector.record.model import RecordedSelector, RecordedStep
from pyselector.selector.snippet import choose_snippet_candidate
from pyselector.utils.text import escape_python_string, escape_regex

#: expect の条件からセレクターを組み立てるときの、CLI 引数 -> child_window の引数。
_CONDITION_KEYS = (
    ("auto_id", "auto_id"),
    ("class_name", "class_name"),
)


def record_act(
    args: Namespace,
    backend: str,
    inspector: Any,
    target: ElementInfo,
    target_window: Any,
    method: str | None,
    build_inspection: Callable[[], Any],
    log: Callable[[str], None],
) -> RecordedStep | None:
    """成功した操作を 1 手順として残す。

    CLI に渡された条件ではなく、**解決済みの要素から生成して評価した**セレクターを
    記録する。``--text "保存"`` のような条件は表示文言に、``--index 2`` は並び順に
    依存しており、そのままコードにしても良いセレクターにならない（設計 11 §8.3）。
    """
    if not store.is_recording():
        return None
    log(f"{backend}: 記録用にセレクターを確定中です...")
    selector, warning = _selector_from_element(build_inspection)
    return store.append(
        lambda seq: RecordedStep(
            seq=seq,
            kind="act",
            timestamp=_now(),
            backend=backend,
            action=args.action,
            method=method,
            value=getattr(args, "value", None),
            selector=selector,
            selector_warning=warning,
            element=_element_summary(target),
            target_window=_window_summary(target_window),
            wait=_wait_from(getattr(args, "settle", None)),
            note=getattr(args, "note", None),
        )
    )


def record_expect(
    args: Namespace,
    backend: str,
    target: ElementInfo | None,
    target_window: Any,
    build_inspection: Callable[[], Any] | None,
    log: Callable[[str], None],
) -> RecordedStep | None:
    """成立した判定を 1 手順として残す。

    成立しなかった判定は記録しない。生成コードに書き出せば必ず落ちる assert に
    なるうえ、エージェントはその後で条件を変えて試し直すのが普通である。
    """
    if not store.is_recording():
        return None
    if target is not None and build_inspection is not None:
        log(f"{backend}: 記録用にセレクターを確定中です...")
        selector, warning = _selector_from_element(build_inspection)
    else:
        # 0 件を確かめる判定には対象要素が無い。探索条件からそのまま組み立てる。
        selector, warning = _selector_from_conditions(args, backend)
    return store.append(
        lambda seq: RecordedStep(
            seq=seq,
            kind="expect",
            timestamp=_now(),
            backend=backend,
            action=args.expectation,
            expected=getattr(args, "expected", None),
            selector=selector,
            selector_warning=warning,
            element=_element_summary(target),
            target_window=_window_summary(target_window),
            wait=_wait_from(getattr(args, "wait", None)),
            note=getattr(args, "note", None),
        )
    )


def record_launch(
    backend: str,
    launch: dict[str, Any],
    target_window: Any,
    note: str | None = None,
) -> RecordedStep | None:
    if not store.is_recording():
        return None
    return store.append(
        lambda seq: RecordedStep(
            seq=seq,
            kind="launch",
            timestamp=_now(),
            backend=backend,
            action="launch",
            launch=dict(launch),
            target_window=_window_summary(target_window),
            note=note,
        )
    )


def record_close(
    backend: str,
    target_window: Any,
    forced: bool,
    note: str | None = None,
) -> RecordedStep | None:
    if not store.is_recording():
        return None
    # close の対象はトップレベルウィンドウそのもの。子要素として探し直させると、
    # 自分と同じタイトルの子を探すコードになって必ず失敗する。
    selector = RecordedSelector(text=WINDOW_SELF, kind="window_itself", source="conditions")
    return store.append(
        lambda seq: RecordedStep(
            seq=seq,
            kind="close",
            timestamp=_now(),
            backend=backend,
            action="force_close" if forced else "close",
            selector=selector,
            target_window=_window_summary(target_window),
            note=note,
        )
    )


def _selector_from_element(build_inspection: Callable[[], Any]) -> tuple[RecordedSelector | None, str | None]:
    inspection = build_inspection()
    evaluation = choose_snippet_candidate(list(inspection.evaluations))
    if evaluation is None:
        # 推測でそれらしいコードを出さない。生成時にコメントとして残し、人に委ねる。
        return None, "評価に通ったセレクター候補がありませんでした"
    return _to_recorded(evaluation), None


def _to_recorded(evaluation: SelectorEvaluation) -> RecordedSelector:
    return RecordedSelector(
        text=evaluation.candidate.selector_text,
        kind=evaluation.candidate.selector_kind,
        hits=evaluation.hits,
        warnings=list(evaluation.warnings),
        source="evaluated",
    )


def _selector_from_conditions(args: Namespace, backend: str) -> tuple[RecordedSelector | None, str | None]:
    parts: list[str] = []
    text = getattr(args, "text", None)
    text_re = getattr(args, "text_re", None)
    if text_re is not None:
        parts.append(f'title_re="{escape_python_string(text_re)}"')
    elif text is not None:
        # --text は部分一致なので、完全一致の title に落とすと意味が変わる。
        parts.append(f'title_re=".*{escape_python_string(escape_regex(text))}.*"')
    for attr, keyword in _CONDITION_KEYS:
        value = getattr(args, attr, None)
        if value is not None:
            parts.append(f'{keyword}="{escape_python_string(value)}"')
    control_type = getattr(args, "control_type", None)
    if control_type is not None and backend == "uia":
        parts.append(f'control_type="{escape_python_string(control_type)}"')
    if not parts:
        return None, "探索条件が空のため、セレクターを組み立てられませんでした"
    return (
        RecordedSelector(
            text=f"dlg.child_window({', '.join(parts)})",
            kind="conditions",
            source="conditions",
        ),
        None,
    )


def _wait_from(timeout: Any) -> dict[str, Any] | None:
    return {"timeout": timeout} if timeout else None


def _element_summary(element: ElementInfo | None) -> dict[str, Any]:
    if element is None:
        return {}
    return {
        "window_text": element.window_text,
        "control_type": element.control_type,
        "automation_id": element.automation_id,
        "class_name": element.class_name,
    }


def _window_summary(target_window: Any) -> dict[str, Any]:
    """TargetWindowInfo でも、探索の起点だった要素でも受け取れるようにする。"""
    if target_window is None:
        return {}
    title = getattr(target_window, "title", None)
    if title is None:
        title = getattr(target_window, "window_text", None)
    return {
        "title": title,
        "class_name": getattr(target_window, "class_name", None),
        "process_name": getattr(target_window, "process_name", None),
    }


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
