import json
from argparse import Namespace

import pytest

from pyselector import screenshot
from pyselector.cli import build_parser
from pyselector.commands import common as command_common
from pyselector.commands import shot as shot_command
from pyselector.model.element_info import ElementInfo
from pyselector.model.rectangle import RectangleInfo
from pyselector.screenshot import ScreenshotError

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


@pytest.fixture(autouse=True)
def no_dpi(monkeypatch):
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)


class FakeWrapper:
    def __init__(self, size=(200, 100)):
        self.size = size

    def capture_as_image(self):
        return Image.new("RGB", self.size, (30, 30, 30))


class FakeShotInspector:
    def __init__(self, window, elements=None, wrapper=None):
        self.window = window
        self.elements = elements or []
        self.wrapper = wrapper or FakeWrapper()

    def find_window_by_handle(self, handle):
        return self.window

    def find_window_by_title(self, title, use_regex):
        return self.window

    def element_from_point(self, x, y):
        return self.window

    def element_from_ref(self, ref):
        return self.window

    def walk_elements(self, root, depth, max_items, only_visible, progress_callback=None):
        return list(self.elements), False

    def _wrapper_for(self, element):
        return self.wrapper


def _window(left=100, top=50, right=300, bottom=150):
    return ElementInfo(
        backend="uia",
        window_text="電卓",
        handle=0x100,
        rectangle=RectangleInfo(left=left, top=top, right=right, bottom=bottom),
        ref="win",
    )


def _element(ref, left, top):
    return ElementInfo(
        backend="uia",
        window_text=f"ボタン{ref}",
        control_type="Button",
        depth=2,
        rectangle=RectangleInfo(left=left, top=top, right=left + 30, bottom=top + 20),
        ref=ref,
    )


def _args(tmp_path, **overrides):
    values = dict(
        command="shot",
        out=str(tmp_path / "shot.png"),
        force=False,
        screen=False,
        window_handle=0x100,
        window_title=None,
        at=None,
        ref=None,
        title_re=False,
        annotate=False,
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
        only_visible=True,
        json=True,
    )
    values.update(overrides)
    return Namespace(**values)


def _run(monkeypatch, capsys, inspector, args):
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    exit_code = shot_command.run_shot(args)
    return exit_code, json.loads(capsys.readouterr().out)


def test_a_window_shot_is_written_to_disk(monkeypatch, capsys, tmp_path):
    inspector = FakeShotInspector(_window())

    exit_code, payload = _run(monkeypatch, capsys, inspector, _args(tmp_path))

    assert exit_code == 0
    assert (tmp_path / "shot.png").exists()
    assert payload["width"] == 200
    assert payload["origin"] == {"x": 100, "y": 50}


def test_an_existing_file_is_not_overwritten_silently(monkeypatch, capsys, tmp_path):
    inspector = FakeShotInspector(_window())
    target = tmp_path / "shot.png"
    target.write_bytes(b"keep me")
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)

    with pytest.raises(ScreenshotError):
        shot_command.run_shot(_args(tmp_path))

    assert target.read_bytes() == b"keep me"


def test_force_overwrites(monkeypatch, capsys, tmp_path):
    inspector = FakeShotInspector(_window())
    (tmp_path / "shot.png").write_bytes(b"old")

    exit_code, _ = _run(monkeypatch, capsys, inspector, _args(tmp_path, force=True))

    assert exit_code == 0
    assert (tmp_path / "shot.png").read_bytes() != b"old"


def test_annotations_are_numbered_from_one(monkeypatch, capsys, tmp_path):
    inspector = FakeShotInspector(
        _window(), elements=[_element("a", 110, 60), _element("b", 150, 60)]
    )

    exit_code, payload = _run(
        monkeypatch, capsys, inspector, _args(tmp_path, annotate=True, control_type="Button")
    )

    assert exit_code == 0
    assert [item["index"] for item in payload["annotations"]] == [1, 2]
    assert payload["annotations"][0]["element"]["window_text"] == "ボタンa"


def test_annotation_boxes_are_placed_relative_to_the_image(tmp_path):
    """要素の矩形は画面座標。画像の原点を引かないと枠がずれる。"""
    image = Image.new("RGB", (200, 100), (0, 0, 0))
    boxes = [(1, RectangleInfo(left=110, top=60, right=140, bottom=80))]

    annotated = screenshot.annotate(image, (100, 50), boxes)

    # 画面座標 (110, 60) は、原点 (100, 50) の画像では (10, 10) に来る。
    assert annotated.getpixel((10, 10)) == screenshot.BOX_COLOR
    assert annotated.getpixel((150, 90)) == (0, 0, 0)


def test_a_missing_pillow_is_reported_plainly(monkeypatch, tmp_path):
    def no_pillow():
        raise ScreenshotError("shot には pillow が必要です")

    monkeypatch.setattr(screenshot, "load_pillow", no_pillow)

    with pytest.raises(ScreenshotError, match="pillow"):
        screenshot.capture_screen()


def test_shot_requires_exactly_one_target():
    from pyselector import cli

    parser = build_parser()

    with pytest.raises(SystemExit):
        cli._validate_shot_target(parser.parse_args(["shot", "--out", "a.png"]), parser)

    both = parser.parse_args(["shot", "--out", "a.png", "--screen", "--window-handle", "0x10"])
    with pytest.raises(SystemExit):
        cli._validate_shot_target(both, parser)


def test_annotate_needs_a_window(capsys):
    from pyselector import cli

    parser = build_parser()
    args = parser.parse_args(["shot", "--out", "a.png", "--screen", "--annotate"])

    with pytest.raises(SystemExit):
        cli._validate_shot_target(args, parser)
