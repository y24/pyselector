import json
from argparse import Namespace

import pytest

from pyselector import inspect_runner
from pyselector.cli import build_parser
from pyselector.model.element_info import ElementInfo
from pyselector.model.rectangle import RectangleInfo
from pyselector.wait import poll_until, poll_until_stable


class FakeClock:
    """時刻と sleep を差し替え、実際には待たずに待機の挙動だけを見る。"""

    def __init__(self):
        self.value = 0.0
        self.slept = []

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.value += seconds


def test_a_single_attempt_happens_even_without_a_timeout():
    clock = FakeClock()
    calls = []

    result, outcome = poll_until(
        lambda: calls.append(1) or "done",
        lambda _: False,
        timeout=None,
        now=clock.now,
        sleep=clock.sleep,
    )

    assert result == "done"
    assert outcome.attempts == 1
    assert outcome.timed_out is False
    assert clock.slept == []


def test_polling_stops_as_soon_as_the_condition_holds():
    clock = FakeClock()
    values = iter([0, 0, 7])

    result, outcome = poll_until(
        lambda: next(values),
        lambda value: value == 7,
        timeout=10,
        poll_interval=1,
        now=clock.now,
        sleep=clock.sleep,
    )

    assert result == 7
    assert outcome.attempts == 3
    assert outcome.timed_out is False


def test_a_timeout_returns_the_last_result_rather_than_failing():
    """タイムアウトは失敗ではない。判断は呼び出し側に委ねる。"""
    clock = FakeClock()

    result, outcome = poll_until(
        lambda: "まだ",
        lambda _: False,
        timeout=2,
        poll_interval=1,
        now=clock.now,
        sleep=clock.sleep,
    )

    assert result == "まだ"
    assert outcome.timed_out is True
    assert outcome.waited >= 2


def test_polling_never_sleeps_past_the_timeout():
    clock = FakeClock()

    poll_until(
        lambda: None,
        lambda _: False,
        timeout=0.5,
        poll_interval=10,
        now=clock.now,
        sleep=clock.sleep,
    )

    assert clock.slept == [0.5]


def test_stability_returns_once_two_observations_match():
    clock = FakeClock()
    values = iter(["a", "b", "c", "c"])

    result, outcome = poll_until_stable(
        lambda: next(values),
        timeout=10,
        poll_interval=1,
        now=clock.now,
        sleep=clock.sleep,
    )

    assert result == "c"
    assert outcome.attempts == 4
    assert outcome.timed_out is False


def test_a_still_screen_settles_on_the_second_observation():
    clock = FakeClock()

    _, outcome = poll_until_stable(
        lambda: "same",
        timeout=10,
        poll_interval=1,
        now=clock.now,
        sleep=clock.sleep,
    )

    assert outcome.attempts == 2


def test_a_screen_that_keeps_changing_times_out():
    clock = FakeClock()
    counter = iter(range(100))

    _, outcome = poll_until_stable(
        lambda: next(counter),
        timeout=3,
        poll_interval=1,
        now=clock.now,
        sleep=clock.sleep,
    )

    assert outcome.timed_out is True


class FakeWaitInspector:
    """走査のたびに違う結果を返すインスペクター。"""

    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = 0

    def find_window_by_handle(self, handle):
        return ElementInfo(backend="uia", window_text="root", handle=handle, ref="root")

    def walk_elements(self, root, depth, max_items, only_visible, progress_callback=None):
        batch = self.batches[min(self.calls, len(self.batches) - 1)]
        self.calls += 1
        return list(batch), False


def _element(ref="e"):
    return ElementInfo(
        backend="uia",
        window_text="ダイアログ",
        control_type="Window",
        depth=1,
        rectangle=RectangleInfo(left=0, top=0, right=10, bottom=10),
        ref=ref,
    )


def _find_args(**overrides):
    values = dict(
        command="find",
        window_handle=0x10,
        window_title=None,
        at=None,
        ref=None,
        title_re=False,
        text=None,
        text_re=None,
        auto_id=None,
        control_type=None,
        class_name=None,
        enabled_only=False,
        backend="uia",
        scope="window",
        depth=8,
        max_items=200,
        limit=20,
        timeout=5,
        with_selectors=False,
        selector_limit=3,
        with_state=False,
        wait=None,
        wait_gone=None,
        poll_interval=0.0,
        only_visible=True,
        detail=False,
        compact=False,
        json=True,
    )
    values.update(overrides)
    return Namespace(**values)


def _run_find(monkeypatch, capsys, inspector, **overrides):
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(inspect_runner, "setup_dpi_awareness", lambda: None)
    exit_code = inspect_runner.run_find(_find_args(**overrides))
    return exit_code, json.loads(capsys.readouterr().out)


def test_find_without_wait_scans_once(monkeypatch, capsys):
    inspector = FakeWaitInspector([[], [_element()]])

    exit_code, payload = _run_find(monkeypatch, capsys, inspector)

    assert inspector.calls == 1
    assert exit_code == 1
    assert "waited" in payload
    assert payload["attempts"] == 1


def test_find_wait_retries_until_something_appears(monkeypatch, capsys):
    inspector = FakeWaitInspector([[], [], [_element()]])

    exit_code, payload = _run_find(monkeypatch, capsys, inspector, wait=5)

    assert exit_code == 0
    assert inspector.calls == 3
    assert payload["attempts"] == 3
    assert payload["timed_out"] is False


def test_find_wait_gone_retries_until_nothing_matches(monkeypatch, capsys):
    inspector = FakeWaitInspector([[_element()], []])

    exit_code, payload = _run_find(monkeypatch, capsys, inspector, wait_gone=5)

    assert inspector.calls == 2
    assert payload["timed_out"] is False
    # 一致が無いことが目的でも、find の終了コードは「一致 0 件」の 1 のまま。
    assert exit_code == 1


def test_wait_and_wait_gone_are_exclusive():
    from pyselector import cli

    parser = build_parser()
    args = parser.parse_args(["find", "--window-handle", "0x10", "--wait", "1", "--wait-gone", "1"])

    with pytest.raises(SystemExit):
        cli._validate_wait_options(args, parser)


class FakeSettleInspector:
    """クリック後、しばらくツリーが変化し続けるインスペクター。"""

    def __init__(self, trees):
        self.trees = list(trees)
        self.tree_calls = 0

    def find_window_by_handle(self, handle):
        return ElementInfo(backend="uia", window_text="電卓", handle=handle, ref="root")

    def walk_elements(self, root, depth, max_items, only_visible, progress_callback=None):
        return [_element("target")], False

    def walk_tree(self, root, depth, max_items, only_visible, progress_callback=None):
        from pyselector.model.hierarchy import HierarchyNode

        index = min(self.tree_calls, len(self.trees) - 1)
        self.tree_calls += 1
        return [HierarchyNode(depth=1, window_text=self.trees[index])], False

    def get_target_window(self, element):
        from pyselector.model.target_window import TargetWindowInfo

        return TargetWindowInfo(backend="uia", title="電卓", handle=100)

    def perform_action(self, element, action, value=None):
        return "click_input"

    def refresh_element(self, element):
        return element


def _act_args(**overrides):
    values = dict(
        backend="uia",
        action="click",
        value=None,
        window_handle=100,
        window_title=None,
        title_re=False,
        at=None,
        ref=None,
        text=None,
        text_re=None,
        auto_id=None,
        control_type=None,
        class_name=None,
        enabled_only=False,
        index=None,
        depth=8,
        max_items=200,
        only_visible=True,
        allow_actions=True,
        env_allow_actions=True,
        dry_run=False,
        diff=False,
        settle=None,
        poll_interval=0.0,
        json=True,
    )
    values.update(overrides)
    return Namespace(**values)


def test_act_without_settle_does_not_poll_the_tree(monkeypatch, capsys):
    inspector = FakeSettleInspector(["a", "b", "c"])
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(inspect_runner, "setup_dpi_awareness", lambda: None)

    inspect_runner.run_act(_act_args())
    payload = json.loads(capsys.readouterr().out)

    assert inspector.tree_calls == 0
    assert "settle" not in payload


def test_settle_waits_until_the_tree_stops_changing(monkeypatch, capsys):
    inspector = FakeSettleInspector(["a", "b", "b"])
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(inspect_runner, "setup_dpi_awareness", lambda: None)

    inspect_runner.run_act(_act_args(settle=5))
    payload = json.loads(capsys.readouterr().out)

    assert payload["settle"]["timed_out"] is False
    assert payload["settle"]["attempts"] == 3


def test_settle_reuses_its_last_snapshot_for_the_diff(monkeypatch, capsys):
    """待った後にもう一度取り直すと、待った意味が薄れるうえ走査が 1 回増える。"""
    inspector = FakeSettleInspector(["before", "after", "after"])
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(inspect_runner, "setup_dpi_awareness", lambda: None)

    inspect_runner.run_act(_act_args(settle=5, diff=True))
    payload = json.loads(capsys.readouterr().out)

    # 操作前に 1 回 + 安定判定で 2 回。diff のための取り直しは行われない。
    assert inspector.tree_calls == 3
    assert payload["diff"]["has_differences"] is True


def _expect_args(**overrides):
    values = dict(
        command="expect",
        window_handle=0x10,
        window_title=None,
        at=None,
        ref=None,
        title_re=False,
        text=None,
        text_re=None,
        auto_id=None,
        control_type=None,
        class_name=None,
        enabled_only=False,
        index=None,
        backend="uia",
        scope="window",
        depth=8,
        max_items=200,
        limit=20,
        wait=None,
        poll_interval=0.0,
        only_visible=True,
        compact=False,
        json=True,
        expectation="exists",
        expected=None,
    )
    values.update(overrides)
    return Namespace(**values)


def test_expect_wait_retries_until_the_expectation_holds(monkeypatch, capsys):
    inspector = FakeWaitInspector([[], [], [_element()]])
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(inspect_runner, "setup_dpi_awareness", lambda: None)

    exit_code = inspect_runner.run_expect(_expect_args(wait=5))
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["satisfied"] is True
    assert payload["attempts"] == 3


def test_expect_wait_stops_retrying_a_search_that_cannot_run(monkeypatch, capsys):
    """判定できない状態を待ち続けても好転しない。"""

    class Broken(FakeWaitInspector):
        def walk_elements(self, *args, **kwargs):
            raise RuntimeError("ウィンドウがありません")

    inspector = Broken([[]])
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(inspect_runner, "setup_dpi_awareness", lambda: None)

    exit_code = inspect_runner.run_expect(_expect_args(wait=5))
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["attempts"] == 1
