import json
from argparse import Namespace

import pytest

from pyselector import inspect_runner
from pyselector.commands import common as command_common
from pyselector.commands.record import run_record
from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo
from pyselector.record import store
from pyselector.record.codegen import emit_plain, emit_pytest
from pyselector.record.model import Recording, RecordedSelector, RecordedStep
from pyselector.utils.errors import ArgumentError


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch, tmp_path):
    monkeypatch.setenv("PYSELECTOR_STATE_DIR", str(tmp_path / "state"))


def _step(**overrides):
    values = dict(
        seq=1,
        kind="act",
        timestamp="2026-08-25T10:00:00",
        backend="uia",
        action="click",
        method="click_input",
        selector=RecordedSelector(text='dlg.child_window(auto_id="num5Button")', kind="uia_auto_id", hits=1),
        element={"window_text": "5", "control_type": "Button"},
        target_window={"title": "電卓"},
    )
    values.update(overrides)
    return RecordedStep(**values)


def _recording(*steps, name="保存フロー"):
    return Recording(name=name, started_at="2026-08-25T10:00:00", version="0.2.0", steps=list(steps))


# --- store -------------------------------------------------------------------


def test_nothing_is_recorded_until_start():
    assert store.is_recording() is False
    assert store.load() is None


def test_start_then_append_then_clear():
    store.start("試し")

    assert store.is_recording() is True
    store.append(lambda seq: _step(seq=seq))
    store.append(lambda seq: _step(seq=seq, action="double_click"))

    recording = store.load()
    assert [step.seq for step in recording.steps] == [1, 2]
    assert store.clear() is True
    assert store.is_recording() is False


def test_appending_without_a_recording_does_nothing():
    called = []

    assert store.append(lambda seq: called.append(seq) or _step()) is None
    assert called == []


def test_a_recording_survives_a_round_trip():
    store.start("往復")
    store.append(lambda seq: _step(seq=seq, note="メモ", wait={"timeout": 5}))

    step = store.load().steps[0]

    assert step.note == "メモ"
    assert step.wait == {"timeout": 5}
    assert step.selector.text == 'dlg.child_window(auto_id="num5Button")'


# --- codegen -----------------------------------------------------------------


def test_generated_code_does_not_import_pyselector():
    """生成物は素の pywinauto。テストの実行時に pyselector は要らない（設計 11 §2.2）。"""
    code = emit_pytest(_recording(_step()))

    executable = [line for line in code.splitlines() if not line.strip().startswith("#")]
    assert not any("import pyselector" in line or "pyselector." in line for line in executable)
    assert "from pywinauto import" in code


def test_the_selector_prefix_becomes_the_window_variable():
    code = emit_pytest(_recording(_step()))

    assert 'window.child_window(auto_id="num5Button").click_input()' in code
    assert "dlg." not in code


def test_the_recorded_method_is_what_gets_generated():
    """推測ではなく、記録時に実際に成功したメソッドをそのまま書き出す。"""
    code = emit_pytest(_recording(_step(action="send_keys", method="type_keys", value="{ENTER}")))

    assert '.type_keys(\'{ENTER}\', with_spaces=True)' in code


def test_set_text_carries_its_value():
    code = emit_pytest(_recording(_step(action="set_text", method="set_edit_text", value="山田")))

    assert ".set_edit_text('山田')" in code


def test_expectations_become_asserts():
    code = emit_pytest(
        _recording(
            _step(seq=1, kind="expect", action="value_equals", method=None, expected="8"),
            _step(seq=2, kind="expect", action="checked", method=None),
            _step(seq=3, kind="expect", action="not_exists", method=None),
        )
    )

    assert '.get_value() == "8"' in code
    assert ".get_toggle_state() == 1" in code
    assert "assert not window.child_window" in code


def test_a_waited_existence_check_becomes_a_wait_not_an_assert():
    """wait は成立しなければ例外を投げる。それ自体が検証なので assert は要らない。"""
    code = emit_pytest(
        _recording(_step(kind="expect", action="exists", method=None, wait={"timeout": 5}))
    )

    assert '.wait("exists", timeout=5)' in code
    assert ".exists()" not in code


def test_an_unresolved_selector_is_not_guessed():
    code = emit_pytest(_recording(_step(selector=None, selector_warning="候補がありません")))

    assert "NotImplementedError" in code
    assert "候補がありません" in code


def test_selector_warnings_are_carried_into_the_code():
    step = _step(
        selector=RecordedSelector(
            text='dlg.child_window(control_type="Button", found_index=2)',
            kind="uia_found_index",
            hits=1,
            warnings=["found_index は画面構成や表示順の変更に弱い可能性があります"],
        )
    )

    assert "# warning: found_index" in emit_pytest(_recording(step))


def test_a_launch_step_becomes_the_fixture():
    launch = _step(
        seq=1,
        kind="launch",
        action="launch",
        method=None,
        selector=None,
        launch={"exe": "calc.exe", "args": [], "window_title_re": "^電卓$", "timeout": 20},
    )
    code = emit_pytest(_recording(launch, _step(seq=2)))

    assert 'Application(backend="uia").start(r"calc.exe")' in code
    assert 'connect(title_re="^電卓$", timeout=20)' in code
    # launch は前提であって手順ではないので、テスト本体には現れない。
    assert code.count("# 1.") == 0


def test_without_a_launch_the_fixture_connects_to_an_open_window():
    code = emit_pytest(_recording(_step()))

    assert 'Desktop(backend="uia").window(title="電卓")' in code
    assert "既に起動している前提" in code


def test_the_recording_name_becomes_the_test_name():
    assert "def test_保存フロー(window):" in emit_pytest(_recording(_step()))


def test_an_awkward_name_is_turned_into_an_identifier():
    code = emit_pytest(_recording(_step(), name="save flow #2!"))

    assert "def test_save_flow_2(window):" in code


def test_plain_output_needs_no_pytest():
    code = emit_plain(_recording(_step()))

    assert "import pytest" not in code
    assert "def main():" in code
    assert '__name__ == "__main__"' in code


def test_generated_code_is_valid_python():
    code = emit_pytest(
        _recording(
            _step(seq=1),
            _step(seq=2, kind="expect", action="value_contains", method=None, expected="8"),
            _step(seq=3, selector=None, selector_warning="なし"),
        )
    )

    compile(code, "<generated>", "exec")


# --- command -----------------------------------------------------------------


def _record_args(record_command, **overrides):
    values = dict(record_command=record_command, json=True, force=False)
    values.update(overrides)
    return Namespace(**values)


def test_start_reports_the_recording(capsys):
    assert run_record(_record_args("start", name="流れ")) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "record"
    assert payload["recording"]["name"] == "流れ"


def test_starting_twice_refuses_to_discard_silently():
    run_record(_record_args("start", name="最初"))

    with pytest.raises(ArgumentError):
        run_record(_record_args("start", name="次"))

    assert store.load().name == "最初"


def test_force_replaces_the_recording():
    run_record(_record_args("start", name="最初"))
    run_record(_record_args("start", name="次", force=True))

    assert store.load().name == "次"


def test_status_without_a_recording_is_exit_one(capsys):
    assert run_record(_record_args("status")) == 1

    assert json.loads(capsys.readouterr().out)["recording"] is None


def test_stop_writes_the_file_and_ends_the_recording(capsys, tmp_path):
    run_record(_record_args("start", name="書き出し"))
    store.append(lambda seq: _step(seq=seq))
    target = tmp_path / "tests" / "test_generated.py"

    assert run_record(_record_args("stop", emit="pytest", out=str(target))) == 0

    assert "def test_書き出し(window):" in target.read_text(encoding="utf-8")
    assert store.is_recording() is False


def test_stop_does_not_overwrite_silently(tmp_path):
    run_record(_record_args("start", name="上書き"))
    store.append(lambda seq: _step(seq=seq))
    target = tmp_path / "existing.py"
    target.write_text("# 手を入れた後かもしれない\n", encoding="utf-8")

    with pytest.raises(ArgumentError):
        run_record(_record_args("stop", emit="pytest", out=str(target)))

    assert target.read_text(encoding="utf-8") == "# 手を入れた後かもしれない\n"
    # 生成に失敗したのだから、記録は残っていなければならない。
    assert store.is_recording() is True


def test_stop_without_out_returns_the_code_in_the_payload(capsys):
    run_record(_record_args("start", name="標準出力"))
    store.append(lambda seq: _step(seq=seq))
    capsys.readouterr()

    run_record(_record_args("stop", emit="pytest", out=None))

    assert "def test_標準出力" in json.loads(capsys.readouterr().out)["code"]


def test_cancel_discards_without_generating(capsys):
    run_record(_record_args("start", name="破棄"))

    assert run_record(_record_args("cancel")) == 0
    assert store.is_recording() is False


# --- act / expect hooks ------------------------------------------------------


class FakeRecordInspector:
    def __init__(self, elements):
        self.elements = elements
        self.hierarchy_calls = 0

    def find_window_by_handle(self, handle):
        return ElementInfo(backend="uia", window_text="電卓", handle=handle, ref="root")

    def walk_elements(self, root, depth, max_items, only_visible, progress_callback=None):
        return list(self.elements), False

    def walk_tree(self, root, depth, max_items, only_visible, progress_callback=None):
        return [], False

    def get_target_window(self, element):
        return TargetWindowInfo(backend="uia", title="電卓", handle=100)

    def get_hierarchy(self, element):
        self.hierarchy_calls += 1
        return [HierarchyNode(depth=0, window_text="電卓")]

    def perform_action(self, element, action, value=None):
        return "click_input"

    def refresh_element(self, element):
        return element

    def read_element_state(self, element):
        return element

    def find_elements(self, scope, condition):
        return [], False

    def find_elements_chain(self, scope, steps, max_items):
        return [], False, None


def _target(ref="btn"):
    return ElementInfo(
        backend="uia",
        window_text="5",
        control_type="Button",
        automation_id="num5Button",
        depth=5,
        rectangle=RectangleInfo(left=0, top=0, right=20, bottom=10),
        is_enabled=True,
        ref=ref,
    )


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
        auto_id="num5Button",
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
        note=None,
        json=True,
    )
    values.update(overrides)
    return Namespace(**values)


def _stub_selector(monkeypatch):
    candidate = SelectorCandidate(
        backend="uia",
        selector_text='dlg.child_window(auto_id="num5Button", control_type="Button")',
        selector_kind="uia_auto_id_control_type",
        condition={},
    )
    monkeypatch.setattr(command_common, "generate_candidates", lambda *args, **kwargs: [candidate])
    monkeypatch.setattr(
        command_common,
        "evaluate_candidates",
        lambda *args, **kwargs: [SelectorEvaluation(candidate=candidate, hits=1)],
    )
    monkeypatch.setattr(command_common, "append_found_index_candidates", lambda candidates, *a: candidates)
    monkeypatch.setattr(command_common, "attach_warnings", lambda *args, **kwargs: None)
    monkeypatch.setattr(command_common, "build_code_snippet", lambda *args, **kwargs: None)


def test_act_records_the_evaluated_selector_not_the_cli_condition(monkeypatch, capsys):
    """--text のような条件は表示文言に依存する。記録するのは評価済みのセレクター。"""
    inspector = FakeRecordInspector([_target()])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)
    _stub_selector(monkeypatch)
    store.start("操作")

    inspect_runner.run_act(_act_args(auto_id=None, text="5"))
    payload = json.loads(capsys.readouterr().out)

    step = store.load().steps[0]
    assert step.kind == "act"
    assert step.method == "click_input"
    assert step.selector.text == 'dlg.child_window(auto_id="num5Button", control_type="Button")'
    assert payload["recorded"]["seq"] == 1


def test_act_does_not_evaluate_selectors_when_not_recording(monkeypatch, capsys):
    """記録していないときの act の速度は変わらないこと。"""
    inspector = FakeRecordInspector([_target()])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)

    inspect_runner.run_act(_act_args())
    payload = json.loads(capsys.readouterr().out)

    assert inspector.hierarchy_calls == 0
    assert payload["recorded"] is None


def test_a_dry_run_is_not_recorded(monkeypatch, capsys):
    inspector = FakeRecordInspector([_target()])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)
    _stub_selector(monkeypatch)
    store.start("操作")

    inspect_runner.run_act(_act_args(dry_run=True, allow_actions=False, env_allow_actions=False))

    assert store.load().steps == []


def _expect_args(**overrides):
    values = dict(
        command="expect",
        window_handle=100,
        window_title=None,
        at=None,
        ref=None,
        title_re=False,
        text=None,
        text_re=None,
        auto_id="num5Button",
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
        note=None,
        json=True,
        expectation="exists",
        expected=None,
    )
    values.update(overrides)
    return Namespace(**values)


def test_a_satisfied_expectation_is_recorded(monkeypatch, capsys):
    inspector = FakeRecordInspector([_target()])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)
    _stub_selector(monkeypatch)
    store.start("判定")

    inspect_runner.run_expect(_expect_args())
    capsys.readouterr()

    step = store.load().steps[0]
    assert step.kind == "expect"
    assert step.action == "exists"


def test_a_failed_expectation_is_not_recorded(monkeypatch, capsys):
    """落ちると分かっている assert を生成コードに残しても意味がない。"""
    inspector = FakeRecordInspector([])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)
    store.start("判定")

    inspect_runner.run_expect(_expect_args())
    capsys.readouterr()

    assert store.load().steps == []


def test_a_zero_match_expectation_records_a_selector_from_its_conditions(monkeypatch, capsys):
    """0 件を確かめる判定には対象要素が無いので、探索条件から組み立てる。"""
    inspector = FakeRecordInspector([])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)
    store.start("判定")

    inspect_runner.run_expect(_expect_args(expectation="not_exists", auto_id="dialog"))
    capsys.readouterr()

    step = store.load().steps[0]
    assert step.selector.source == "conditions"
    assert step.selector.text == 'dlg.child_window(auto_id="dialog")'
    # 生成コードが接続先を書けるよう、起点だったウィンドウは残しておく。
    assert step.target_window["title"] == "電卓"


def test_a_substring_condition_stays_a_substring(monkeypatch, capsys):
    inspector = FakeRecordInspector([])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)
    store.start("判定")

    inspect_runner.run_expect(_expect_args(expectation="not_exists", auto_id=None, text="保存"))
    capsys.readouterr()

    assert store.load().steps[0].selector.text == 'dlg.child_window(title_re=".*保存.*")'
