import json
from argparse import Namespace

from pyselector import inspect_runner
from pyselector.commands import common as command_common
from pyselector.backends.common import read_state_values
from pyselector.model.element_info import ElementInfo
from pyselector.model.rectangle import RectangleInfo


class FakeWrapper:
    def __init__(self, **values):
        self._values = values

    def __getattr__(self, name):
        if name not in self._values:
            raise AttributeError(name)
        value = self._values[name]
        if isinstance(value, Exception):
            def raiser(*args):
                raise value

            return raiser
        return lambda *args: value


def test_uia_reads_value_from_the_value_pattern():
    state = read_state_values(FakeWrapper(get_value="山田"), "uia")

    assert state["value"] == "山田"


def test_uia_falls_back_to_legacy_properties():
    wrapper = FakeWrapper(get_value=RuntimeError("no pattern"), legacy_properties={"Value": "予備"})

    assert read_state_values(wrapper, "uia")["value"] == "予備"


def test_win32_does_not_report_a_value():
    """win32 の「値」は表示テキストと区別が付かず、誤って通るアサーションを誘発する。"""
    state = read_state_values(FakeWrapper(get_value="ラベル文字列"), "win32")

    assert state["value"] is None


def test_toggle_states_map_to_bool():
    assert read_state_values(FakeWrapper(get_toggle_state=0), "uia")["is_checked"] is False
    assert read_state_values(FakeWrapper(get_toggle_state=1), "uia")["is_checked"] is True


def test_an_indeterminate_toggle_stays_unknown():
    assert read_state_values(FakeWrapper(get_toggle_state=2), "uia")["is_checked"] is None


def test_win32_reads_the_check_state_instead():
    assert read_state_values(FakeWrapper(get_check_state=1), "win32")["is_checked"] is True
    assert read_state_values(FakeWrapper(get_toggle_state=1), "win32")["is_checked"] is None


def test_unavailable_state_is_none_not_false():
    state = read_state_values(FakeWrapper(), "uia")

    assert state == {
        "value": None,
        "is_checked": None,
        "is_selected": None,
        "is_offscreen": None,
        "has_keyboard_focus": None,
    }


def test_a_raising_property_is_treated_as_unavailable():
    wrapper = FakeWrapper(is_selected=RuntimeError("no pattern"))

    assert read_state_values(wrapper, "uia")["is_selected"] is None


class FakeStateInspector:
    def __init__(self, elements):
        self.elements = elements
        self.state_reads = []

    def find_window_by_handle(self, handle):
        return ElementInfo(backend="uia", window_text="root", handle=handle, ref="root")

    def walk_elements(self, root, depth, max_items, only_visible, progress_callback=None):
        return list(self.elements), False

    def read_element_state(self, element):
        from dataclasses import replace

        self.state_reads.append(element.ref)
        return replace(element, value="読んだ")


def _element(ref):
    return ElementInfo(
        backend="uia",
        window_text="ボタン",
        control_type="Button",
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
        only_visible=True,
        detail=False,
        compact=False,
        json=True,
    )
    values.update(overrides)
    return Namespace(**values)


def test_find_does_not_read_state_by_default(monkeypatch, capsys):
    inspector = FakeStateInspector([_element("a"), _element("b")])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)

    inspect_runner.run_find(_find_args())
    payload = json.loads(capsys.readouterr().out)

    assert inspector.state_reads == []
    assert "state" not in payload["results"][0]["matches"][0]["element"]


def test_with_state_reads_only_the_listed_matches(monkeypatch, capsys):
    """状態の取得コストは走査量ではなく出力量に比例させる（設計 11 §3.2）。"""
    inspector = FakeStateInspector([_element(f"e{index}") for index in range(5)])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)

    inspect_runner.run_find(_find_args(with_state=True, limit=2))
    payload = json.loads(capsys.readouterr().out)

    assert inspector.state_reads == ["e0", "e1"]
    assert payload["results"][0]["matches"][0]["element"]["state"]["value"] == "読んだ"
