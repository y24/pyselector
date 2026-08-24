import json
from argparse import Namespace

import pytest

from pyselector import inspect_runner
from pyselector.commands import common as command_common
from pyselector.cli import build_parser
from pyselector.model.element_info import ElementInfo
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.target_window import TargetWindowInfo
from pyselector.utils.errors import (
    EXIT_EXPECTATION_FAILED,
    AmbiguousTargetError,
    ElementNotFoundError,
)


class FakeExpectInspector:
    """walk_elements で要素を返し、read_element_state で状態を足すインスペクター。"""

    def __init__(self, elements=None, states=None, error=None):
        self.elements = elements if elements is not None else []
        self.states = states or {}
        self.error = error
        self.state_reads = []

    def find_window_by_handle(self, handle):
        return ElementInfo(backend="uia", window_text="root", handle=handle, ref="root")

    def find_window_by_title(self, title, use_regex):
        return ElementInfo(backend="uia", window_text=title, ref="root")

    def element_from_point(self, x, y):
        return ElementInfo(backend="uia", window_text="root", ref="root")

    def element_from_ref(self, ref):
        return ElementInfo(backend="uia", window_text="root", ref=ref)

    def walk_elements(self, root, depth, max_items, only_visible, progress_callback=None):
        if self.error is not None:
            raise self.error
        return list(self.elements), False

    def read_element_state(self, element):
        self.state_reads.append(element.ref)
        values = self.states.get(element.ref)
        if not values:
            return element
        from dataclasses import replace

        return replace(element, **values)

    def get_target_window(self, element):
        return TargetWindowInfo(backend="uia", title="親ウィンドウ", handle=999)


def _element(ref="e", text="ボタン", **overrides):
    values = dict(
        backend="uia",
        window_text=text,
        control_type="Button",
        depth=1,
        rectangle=RectangleInfo(left=0, top=0, right=20, bottom=10),
        is_enabled=True,
        is_visible=True,
        ref=ref,
    )
    values.update(overrides)
    return ElementInfo(**values)


def _args(**overrides):
    values = dict(
        command="expect",
        window_handle=0x1234,
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
        only_visible=True,
        compact=False,
        json=True,
        expectation="exists",
        expected=None,
    )
    values.update(overrides)
    return Namespace(**values)


def _run(monkeypatch, capsys, inspector, **overrides):
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)
    exit_code = inspect_runner.run_expect(_args(**overrides))
    return exit_code, json.loads(capsys.readouterr().out)


def test_exists_is_satisfied_when_something_matches(monkeypatch, capsys):
    inspector = FakeExpectInspector(elements=[_element()])

    exit_code, payload = _run(monkeypatch, capsys, inspector, expectation="exists")

    assert exit_code == 0
    assert payload["command"] == "expect"
    assert payload["status"] == "success"
    assert payload["satisfied"] is True
    assert payload["matched"] == 1


def test_a_failed_expectation_is_not_an_error(monkeypatch, capsys):
    """判定が成立しないことと、判定を実行できないことは別物（設計 11 §6.3）。"""
    inspector = FakeExpectInspector(elements=[])

    exit_code, payload = _run(monkeypatch, capsys, inspector, expectation="exists")

    assert exit_code == EXIT_EXPECTATION_FAILED
    assert payload["status"] == "success"
    assert payload["satisfied"] is False


def test_a_broken_search_is_an_error(monkeypatch, capsys):
    inspector = FakeExpectInspector(error=RuntimeError("ウィンドウがありません"))

    exit_code, payload = _run(monkeypatch, capsys, inspector, expectation="exists")

    assert exit_code == 1
    assert payload["status"] == "error"
    assert payload["satisfied"] is False


def test_not_exists_is_satisfied_when_nothing_matches(monkeypatch, capsys):
    inspector = FakeExpectInspector(elements=[])

    exit_code, payload = _run(monkeypatch, capsys, inspector, expectation="not_exists")

    assert exit_code == 0
    assert payload["satisfied"] is True


def test_count_compares_the_total_not_the_listed_matches(monkeypatch, capsys):
    inspector = FakeExpectInspector(elements=[_element(ref=f"e{i}") for i in range(3)])

    exit_code, payload = _run(monkeypatch, capsys, inspector, expectation="count", expected=3, limit=1)

    assert exit_code == 0
    assert payload["satisfied"] is True
    assert payload["expectation"]["actual"] == 3


def test_value_equals_reads_the_element_state(monkeypatch, capsys):
    inspector = FakeExpectInspector(
        elements=[_element(ref="edit", control_type="Edit")],
        states={"edit": {"value": "山田"}},
    )

    exit_code, payload = _run(monkeypatch, capsys, inspector, expectation="value_equals", expected="山田")

    assert exit_code == 0
    assert payload["satisfied"] is True
    assert inspector.state_reads == ["edit"]
    assert payload["results"][0]["matches"][0]["element"]["state"]["value"] == "山田"


def test_value_contains_matches_a_substring(monkeypatch, capsys):
    inspector = FakeExpectInspector(
        elements=[_element(ref="edit")],
        states={"edit": {"value": "表示は 8"}},
    )

    exit_code, _ = _run(monkeypatch, capsys, inspector, expectation="value_contains", expected="8")

    assert exit_code == 0


def test_checked_needs_a_true_toggle(monkeypatch, capsys):
    inspector = FakeExpectInspector(
        elements=[_element(ref="box", control_type="CheckBox")],
        states={"box": {"is_checked": False}},
    )

    exit_code, payload = _run(monkeypatch, capsys, inspector, expectation="checked")

    assert exit_code == EXIT_EXPECTATION_FAILED
    assert payload["expectation"]["actual"] is False


def test_an_indeterminate_toggle_satisfies_neither_checked_nor_unchecked(monkeypatch, capsys):
    """不定を False として報告すると、チェックが外れていることを確かめたテストが誤って通る。"""
    inspector = FakeExpectInspector(
        elements=[_element(ref="box", control_type="CheckBox")],
        states={"box": {"is_checked": None}},
    )

    checked, _ = _run(monkeypatch, capsys, inspector, expectation="checked")
    unchecked, _ = _run(monkeypatch, capsys, inspector, expectation="unchecked")

    assert checked == EXIT_EXPECTATION_FAILED
    assert unchecked == EXIT_EXPECTATION_FAILED


def test_disabled_uses_is_enabled_without_reading_state(monkeypatch, capsys):
    inspector = FakeExpectInspector(elements=[_element(ref="btn", is_enabled=False)])

    exit_code, _ = _run(monkeypatch, capsys, inspector, expectation="disabled")

    assert exit_code == 0
    assert inspector.state_reads == []


def test_several_matches_stop_a_state_expectation(monkeypatch, capsys):
    inspector = FakeExpectInspector(elements=[_element(ref="a"), _element(ref="b")])

    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)
    with pytest.raises(AmbiguousTargetError):
        inspect_runner.run_expect(_args(expectation="checked"))


def test_several_matches_are_fine_for_exists(monkeypatch, capsys):
    inspector = FakeExpectInspector(elements=[_element(ref="a"), _element(ref="b")])

    exit_code, payload = _run(monkeypatch, capsys, inspector, expectation="exists")

    assert exit_code == 0
    assert payload["matched"] == 2


def test_index_out_of_range_is_a_targeting_error(monkeypatch, capsys):
    inspector = FakeExpectInspector(elements=[_element(ref="a")])

    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)
    with pytest.raises(ElementNotFoundError):
        inspect_runner.run_expect(_args(expectation="checked", index=5))


def test_a_missing_element_reports_no_actual_value(monkeypatch, capsys):
    inspector = FakeExpectInspector(elements=[])

    exit_code, payload = _run(monkeypatch, capsys, inspector, expectation="value_equals", expected="山田")

    assert exit_code == EXIT_EXPECTATION_FAILED
    assert payload["matched"] == 0
    assert payload["expectation"]["actual"] is None


def test_expect_requires_exactly_one_expectation():
    from pyselector import cli

    parser = build_parser()
    args = parser.parse_args(["expect", "--window-handle", "0x10", "--exists", "--count", "3"])

    with pytest.raises(SystemExit):
        cli._resolve_expectation(args, parser)


def test_expect_requires_at_least_one_expectation():
    from pyselector import cli

    parser = build_parser()
    args = parser.parse_args(["expect", "--window-handle", "0x10"])

    with pytest.raises(SystemExit):
        cli._resolve_expectation(args, parser)


def test_a_valued_expectation_carries_its_expected_value():
    from pyselector import cli

    parser = build_parser()
    args = parser.parse_args(["expect", "--window-handle", "0x10", "--value-equals", "山田"])
    cli._resolve_expectation(args, parser)

    assert args.expectation == "value_equals"
    assert args.expected == "山田"


def test_expect_requires_exactly_one_target():
    parser = build_parser()
    args = parser.parse_args(["expect", "--window-handle", "0x10", "--at", "1,2", "--exists"])

    from pyselector import cli

    with pytest.raises(SystemExit):
        cli._validate_find_target(args, parser, command="expect")


def test_expect_backend_does_not_accept_both():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["expect", "--window-handle", "0x10", "--exists", "--backend", "both"])
