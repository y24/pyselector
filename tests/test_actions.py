import pytest

from pyselector.actions import perform_action
from pyselector.utils.errors import ActionFailedError


class RecordingWrapper:
    def __init__(self, *, supported=(), failing=()):
        self.calls = []
        self.failing = set(failing)
        for name in supported:
            setattr(self, name, self._make(name))

    def _make(self, name):
        def method(*args, **kwargs):
            if name in self.failing:
                raise RuntimeError(f"{name} failed")
            self.calls.append((name, args, kwargs))

        return method


def test_click_prefers_click_input():
    wrapper = RecordingWrapper(supported=("click_input", "click"))

    method = perform_action(wrapper, "click")

    assert method == "click_input"
    assert [call[0] for call in wrapper.calls] == ["click_input"]


def test_click_falls_back_to_click_when_click_input_is_missing():
    wrapper = RecordingWrapper(supported=("click",))

    assert perform_action(wrapper, "click") == "click"


def test_click_falls_back_when_the_preferred_method_raises():
    wrapper = RecordingWrapper(supported=("click_input", "click"), failing=("click_input",))

    assert perform_action(wrapper, "click") == "click"


def test_invoke_prefers_the_invoke_pattern():
    wrapper = RecordingWrapper(supported=("invoke", "click_input", "click"))

    assert perform_action(wrapper, "invoke") == "invoke"


def test_set_text_passes_the_value():
    wrapper = RecordingWrapper(supported=("set_edit_text",))

    method = perform_action(wrapper, "set_text", "こんにちは")

    assert method == "set_edit_text"
    assert wrapper.calls == [("set_edit_text", ("こんにちは",), {})]


def test_send_keys_types_with_spaces_and_foreground():
    wrapper = RecordingWrapper(supported=("type_keys",))

    perform_action(wrapper, "send_keys", "abc")

    assert wrapper.calls == [("type_keys", ("abc",), {"with_spaces": True, "set_foreground": True})]


def test_value_actions_require_a_value():
    wrapper = RecordingWrapper(supported=("set_edit_text",))

    with pytest.raises(ActionFailedError) as error:
        perform_action(wrapper, "set_text")

    assert "値の指定が必要です" in str(error.value)
    assert wrapper.calls == []


def test_unsupported_action_is_rejected():
    with pytest.raises(ActionFailedError) as error:
        perform_action(RecordingWrapper(), "explode")

    assert "未対応の操作です" in str(error.value)


def test_failure_reports_every_attempted_method():
    wrapper = RecordingWrapper(supported=("click_input",), failing=("click_input",))

    with pytest.raises(ActionFailedError) as error:
        perform_action(wrapper, "click")

    message = str(error.value)
    assert "click_input: click_input failed" in message
    assert "click: 未対応" in message
