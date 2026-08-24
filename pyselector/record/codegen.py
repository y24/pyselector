from __future__ import annotations

import re

from pyselector.record.model import Recording, RecordedStep
from pyselector.utils.text import escape_python_string

#: 生成コードでウィンドウを受け取る変数名。記録されたセレクターの先頭 ``dlg.`` を
#: これに置き換える。
WINDOW_VAR = "window"
SELECTOR_PREFIX = "dlg."

EMIT_FORMATS = ("pytest", "plain", "none")

#: act の method（実際に成功した pywinauto のメソッド）から、生成する呼び出しへ。
#: 推測ではなく実績を書き出すので、記録時に動いたものがそのまま再現される。
_METHOD_ARGS = {
    "set_edit_text": "{value}",
    "set_text": "{value}",
    "type_keys": "{value}, with_spaces=True",
}


def emit(recording: Recording, emit_format: str) -> str:
    if emit_format == "pytest":
        return emit_pytest(recording)
    if emit_format == "plain":
        return emit_plain(recording)
    raise ValueError(f"unsupported emit format: {emit_format}")


def emit_pytest(recording: Recording) -> str:
    body = _body_lines(recording)
    lines = [
        _docstring(recording),
        "",
        "import pytest",
        "from pywinauto import Application, Desktop",
        "",
        "",
        *_fixture_lines(recording),
        "",
        "",
        f"def test_{_identifier(recording.name)}({WINDOW_VAR}):",
        *(f"    {line}" if line else "" for line in body),
        "",
    ]
    return "\n".join(lines)


def emit_plain(recording: Recording) -> str:
    body = _body_lines(recording)
    connect = _connect_lines(recording)
    lines = [
        _docstring(recording),
        "",
        "from pywinauto import Application, Desktop",
        "",
        "",
        "def main():",
        *(f"    {line}" if line else "" for line in connect),
        "",
        *(f"    {line}" if line else "" for line in body),
        "",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    return "\n".join(lines)


def _docstring(recording: Recording) -> str:
    return "\n".join(
        [
            '"""pyselector record が生成したテスト。',
            "",
            f"記録名: {recording.name}",
            f"記録開始: {recording.started_at}",
            "",
            "このファイルは pyselector に依存しない。pywinauto があれば実行できる。",
            '"""',
        ]
    )


def _fixture_lines(recording: Recording) -> list[str]:
    lines = ['@pytest.fixture(scope="module")', f"def {WINDOW_VAR}():"]
    lines.extend(f"    {line}" for line in _connect_lines(recording))
    lines.append(f"    yield {WINDOW_VAR}")
    return lines


def _connect_lines(recording: Recording) -> list[str]:
    """対象ウィンドウを手に入れるところまで。

    launch が記録されていればアプリの起動から、無ければ既に開いているウィンドウへの
    接続から始める。後者はテストの前提として人がアプリを開いておく必要があるので、
    その旨をコメントに残す。
    """
    launch = next((step for step in recording.steps if step.kind == "launch"), None)
    backend = _backend(recording)
    if launch is not None and launch.launch:
        return _launch_lines(launch, backend)

    title = _window_title(recording)
    if title is None:
        return [
            "# 対象ウィンドウを特定できなかった。接続条件を自分で書くこと。",
            f'{WINDOW_VAR} = Desktop(backend="{backend}").window()',
        ]
    return [
        "# アプリは既に起動している前提。起動から自動化するなら pyselector launch を記録すること。",
        f'{WINDOW_VAR} = Desktop(backend="{backend}").window(title="{escape_python_string(title)}")',
        f'{WINDOW_VAR}.wait("visible enabled", timeout=30)',
    ]


def _launch_lines(step: RecordedStep, backend: str) -> list[str]:
    launch = step.launch or {}
    exe = escape_python_string(str(launch.get("exe") or ""))
    args = launch.get("args") or []
    command = exe if not args else exe + " " + " ".join(str(arg) for arg in args)
    title_re = launch.get("window_title_re")
    timeout = launch.get("timeout") or 30
    lines = [f'Application(backend="{backend}").start(r"{command}")']
    if title_re:
        pattern = escape_python_string(str(title_re))
        lines.extend(
            [
                f'app = Application(backend="{backend}").connect(title_re="{pattern}", timeout={timeout})',
                f'{WINDOW_VAR} = app.window(title_re="{pattern}")',
            ]
        )
    else:
        title = escape_python_string(str(step.target_window.get("title") or ""))
        lines.extend(
            [
                f'app = Application(backend="{backend}").connect(title="{title}", timeout={timeout})',
                f'{WINDOW_VAR} = app.window(title="{title}")',
            ]
        )
    lines.append(f'{WINDOW_VAR}.wait("visible enabled", timeout={timeout})')
    return lines


def _body_lines(recording: Recording) -> list[str]:
    steps = [step for step in recording.steps if step.kind != "launch"]
    if not steps:
        return ["pass  # 記録された手順がない"]
    lines: list[str] = []
    for index, step in enumerate(steps):
        if index:
            lines.append("")
        lines.append(f"# {step.seq}. {_comment(step)}")
        if step.note:
            lines.append(f"# {step.note}")
        lines.extend(_step_lines(step))
    return lines


#: 手順コメントに載せる要素テキストの長さ。文書全体が入る Document のような要素も
#: あるため、識別できる程度に切り詰める。
COMMENT_TEXT_LIMIT = 40


def _comment(step: RecordedStep) -> str:
    label = step.action or step.kind
    text = step.element.get("window_text")
    if not text:
        return f"{step.kind}: {label}"
    return f"{step.kind}: {label} {_shorten(str(text))!r}"


def _shorten(text: str) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= COMMENT_TEXT_LIMIT:
        return single_line
    return single_line[:COMMENT_TEXT_LIMIT] + "…"


def _step_lines(step: RecordedStep) -> list[str]:
    selector = _selector_expression(step)
    if selector is None:
        return [
            f"# セレクターを確定できなかった: {step.selector_warning or '理由不明'}",
            f"# 記録された要素: {step.element}",
            "raise NotImplementedError('セレクターを自分で書くこと')",
        ]
    lines = [f"# warning: {warning}" for warning in (step.selector.warnings if step.selector else [])]
    if step.kind == "act":
        lines.append(f"{selector}.{_call(step)}")
        return lines
    if step.kind == "close":
        lines.append(f"{selector}.close()")
        return lines
    lines.extend(_expect_lines(step, selector))
    return lines


def _call(step: RecordedStep) -> str:
    method = step.method or step.action or "click_input"
    template = _METHOD_ARGS.get(method)
    if template is None:
        return f"{method}()"
    return f"{method}({template.format(value=repr(step.value))})"


def _expect_lines(step: RecordedStep, selector: str) -> list[str]:
    kind = step.action
    timeout = (step.wait or {}).get("timeout")
    lines: list[str] = []
    if timeout and kind == "exists":
        # wait は成立しなければ例外を投げる。それ自体が検証なので assert は要らない。
        return [f'{selector}.wait("exists", timeout={_number(timeout)})']
    if timeout and kind == "not_exists":
        return [f'{selector}.wait_not("exists", timeout={_number(timeout)})']
    if timeout:
        lines.append(f'{selector}.wait("exists", timeout={_number(timeout)})')

    expected = step.expected
    if kind == "exists":
        lines.append(f"assert {selector}.exists()")
    elif kind == "not_exists":
        lines.append(f"assert not {selector}.exists()")
    elif kind == "count":
        lines.append(f"assert len({selector}.wrapper_object().children()) == {expected}")
    elif kind == "value_equals":
        lines.append(f'assert {selector}.get_value() == "{escape_python_string(str(expected))}"')
    elif kind == "value_contains":
        lines.append(f'assert "{escape_python_string(str(expected))}" in {selector}.get_value()')
    elif kind == "checked":
        lines.append(f"assert {selector}.get_toggle_state() == 1")
    elif kind == "unchecked":
        lines.append(f"assert {selector}.get_toggle_state() == 0")
    elif kind == "enabled":
        lines.append(f"assert {selector}.is_enabled()")
    elif kind == "disabled":
        lines.append(f"assert not {selector}.is_enabled()")
    else:
        lines.append(f"# 未対応の判定: {kind}")
    return lines


def _selector_expression(step: RecordedStep) -> str | None:
    if step.selector is None or not step.selector.text:
        return None
    text = step.selector.text
    if text.startswith(SELECTOR_PREFIX):
        return WINDOW_VAR + text[len(SELECTOR_PREFIX) - 1:]
    return text


def _number(value) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def _backend(recording: Recording) -> str:
    for step in recording.steps:
        if step.backend:
            return step.backend
    return "uia"


def _window_title(recording: Recording) -> str | None:
    for step in recording.steps:
        title = step.target_window.get("title")
        if title:
            return str(title)
    return None


def _identifier(name: str) -> str:
    """記録名を Python の識別子にする。

    日本語はそのまま識別子として使えるので、置き換えるのは使えない文字だけにする。
    """
    cleaned = re.sub(r"\W", "_", name, flags=re.UNICODE).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"recorded_{cleaned}" if cleaned else "recorded"
    return cleaned
