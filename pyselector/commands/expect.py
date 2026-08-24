from __future__ import annotations

from argparse import Namespace
from typing import Callable

from pyselector.commands import common
from pyselector.commands.common import (
    _build_backend_inspection,
    _candidate_hint,
    _element_center,
    _info_logger,
    _selector_options_from_args,
    _use_color,
)
from pyselector.commands.find import search_elements
from pyselector.model.element_info import ElementInfo
from pyselector.model.expect_result import (
    STATE_KINDS,
    UNIQUE_TARGET_KINDS,
    Expectation,
    ExpectResult,
)
from pyselector.model.find_result import FindResult
from pyselector.output.json_output import format_expect_result_json
from pyselector.output.text_output import format_expect_result
from pyselector.record import capture as record_capture
from pyselector.record import store as record_store
from pyselector.server.refs import ref_backend
from pyselector.utils.errors import EXIT_EXPECTATION_FAILED, AmbiguousTargetError, ElementNotFoundError
from pyselector.utils.logging import info_log
from pyselector.wait import DEFAULT_POLL_INTERVAL, poll_until


def run_expect(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    common.setup_dpi_awareness()

    inspectors: dict[str, object] = {}
    result, outcome = poll_until(
        lambda: evaluate_expectation(args, log, progress=None if json_output else color, inspectors=inspectors),
        # 判定できなかった（status=error）ものを待ち続けても好転しないため、
        # 成立したときと同じく打ち切る。
        lambda item: item.satisfied or item.status != "success",
        timeout=getattr(args, "wait", None),
        poll_interval=getattr(args, "poll_interval", DEFAULT_POLL_INTERVAL),
    )
    if outcome.attempts > 1:
        log(f"待機しました。{outcome.rounded}秒 / {outcome.attempts}回")

    recorded = None
    if result.satisfied:
        recorded = _record(args, result, log, inspectors)
        if recorded is not None:
            log(f"記録しました。手順 {recorded.seq}")

    output = (
        format_expect_result_json(
            result, compact=getattr(args, "compact", False), outcome=outcome, recorded=recorded
        )
        if json_output
        else format_expect_result(result, color)
    )
    print(output, end="")
    if result.status != "success":
        return 1
    return 0 if result.satisfied else EXIT_EXPECTATION_FAILED


def _record(
    args: Namespace,
    result: ExpectResult,
    log: Callable[[str], None],
    inspectors: dict[str, object],
):
    """成立した判定を記録する。対象が定まっていればそこからセレクターを起こす。

    記録していないときに対象ウィンドウを引き直す無駄を避けるため、真っ先に
    記録の有無を見る。
    """
    if not record_store.is_recording():
        return None
    backend = ref_backend(args.ref) if getattr(args, "ref", None) is not None else args.backend
    target = result.target
    inspector = inspectors.get(backend)
    target_window = None
    build_inspection = None
    if target is not None and inspector is not None:
        target_window = inspector.get_target_window(target)
        build_inspection = lambda: _build_backend_inspection(  # noqa: E731
            backend, inspector, target, _element_center(target), _selector_options_from_args(args), log
        )
    if target_window is None:
        # 0 件を確かめた判定には対象要素が無い。探索の起点だったウィンドウを使う。
        # ここを空のままにすると、生成コードが接続先を書けなくなる。
        target_window = _root_window(result)
    return record_capture.record_expect(args, backend, target, target_window, build_inspection, log)


def _root_window(result: ExpectResult):
    for item in result.results:
        if item.root is not None:
            return item.root
    return None


def evaluate_expectation(
    args: Namespace,
    log: Callable[[str], None],
    progress: bool | None = None,
    inspectors: dict[str, object] | None = None,
) -> ExpectResult:
    """1 回だけ探索し、判定を下す。"""
    kind = args.expectation
    backend = ref_backend(args.ref) if getattr(args, "ref", None) is not None else args.backend
    results = search_elements(
        args,
        log,
        backends=[backend],
        with_state=kind in STATE_KINDS,
        progress=progress,
        inspectors=inspectors,
    )
    result = results[0]
    if result.status != "success":
        return ExpectResult(
            expectation=Expectation(kind=kind, expected=getattr(args, "expected", None)),
            satisfied=False,
            matched=0,
            results=results,
            status="error",
            message=result.message,
        )

    matched = result.total_matched
    if kind not in UNIQUE_TARGET_KINDS:
        expectation = _judge_by_count(kind, matched, args)
        return ExpectResult(
            expectation=expectation,
            satisfied=_is_satisfied(expectation),
            matched=matched,
            results=results,
            # 件数の判定でも、対象が 1 件に定まっていればその要素からセレクターを
            # 起こせる。0 件のときは None のままで、探索条件から組み立てる。
            target=result.matches[0].element if len(result.matches) == 1 else None,
        )

    target = _pick_unique_target(result, args)
    expectation = _judge_by_state(kind, target, args)
    return ExpectResult(
        expectation=expectation,
        satisfied=_is_satisfied(expectation),
        matched=matched,
        results=results,
        target=target,
    )


def _judge_by_count(kind: str, matched: int, args: Namespace) -> Expectation:
    if kind == "exists":
        return Expectation(kind=kind, expected="1 件以上", actual=matched)
    if kind == "not_exists":
        return Expectation(kind=kind, expected="0 件", actual=matched)
    return Expectation(kind=kind, expected=getattr(args, "expected", None), actual=matched)


def _judge_by_state(kind: str, target: ElementInfo | None, args: Namespace) -> Expectation:
    expected = getattr(args, "expected", None)
    if target is None:
        # 対象が見つからなかった。「値が違う」ではなく「そもそも無い」ことが
        # 分かるように actual を None のままにし、matched=0 と併せて読ませる。
        return Expectation(kind=kind, expected=expected, actual=None)
    actual = {
        "value_equals": target.value,
        "value_contains": target.value,
        "checked": target.is_checked,
        "unchecked": target.is_checked,
        "enabled": target.is_enabled,
        "disabled": target.is_enabled,
    }[kind]
    return Expectation(kind=kind, expected=expected, actual=actual)


def _is_satisfied(expectation: Expectation) -> bool:
    kind = expectation.kind
    actual = expectation.actual
    if kind == "exists":
        return isinstance(actual, int) and actual >= 1
    if kind == "not_exists":
        return actual == 0
    if kind == "count":
        return actual == expectation.expected
    if kind == "value_equals":
        return actual is not None and actual == expectation.expected
    if kind == "value_contains":
        return isinstance(actual, str) and str(expectation.expected) in actual
    if kind == "checked":
        return actual is True
    if kind == "unchecked":
        return actual is False
    if kind == "enabled":
        return actual is True
    if kind == "disabled":
        return actual is False
    return False


def _pick_unique_target(result: FindResult, args: Namespace) -> ElementInfo | None:
    """一意に定まる対象を返す。定まらなければ act と同じ扱いで止める。"""
    matches = result.matches
    index = getattr(args, "index", None)
    if index is not None:
        if index >= len(matches):
            raise ElementNotFoundError(f"条件に一致した要素は {len(matches)} 件で、index={index} は範囲外です")
        return matches[index].element
    if not matches:
        return None
    if result.total_matched > 1:
        raise AmbiguousTargetError(
            f"条件に一致する要素が {result.total_matched} 件あります。"
            f"条件を絞るか --index で選んでください"
            f"{_candidate_hint([match.element for match in matches])}"
        )
    return matches[0].element
