from __future__ import annotations

from pathlib import Path
from typing import Any

from pyselector.model.rectangle import RectangleInfo
from pyselector.utils.errors import EXIT_SCREENSHOT_FAILED, PySelectorError

#: 注釈の枠と番号の色。明るい画面でも暗い画面でも見えるよう、彩度の高い色を選ぶ。
BOX_COLOR = (255, 64, 64)
LABEL_TEXT_COLOR = (255, 255, 255)
BOX_WIDTH = 2
LABEL_PADDING = 2


class ScreenshotError(PySelectorError):
    """画像の取得や保存に失敗した。"""

    exit_code = EXIT_SCREENSHOT_FAILED


def load_pillow() -> tuple[Any, Any, Any]:
    """Pillow を遅延 import する。

    画像を撮るコマンドだけが Pillow を必要とする。読み取り系のコマンドが Pillow の
    有無で動かなくなることがないよう、モジュールの import 時には触らない。
    """
    try:
        from PIL import Image, ImageDraw, ImageGrab
    except ImportError as exc:
        raise ScreenshotError(
            "shot には pillow が必要です。pip install pillow で導入してください"
        ) from exc
    return Image, ImageDraw, ImageGrab


def capture_screen() -> tuple[Any, tuple[int, int]]:
    """仮想画面全体を撮り、画像と、その左上に対応する画面座標を返す。

    複数モニタでは仮想画面の原点が負になりうる。注釈の座標を合わせるために
    原点を一緒に返す。
    """
    _, _, ImageGrab = load_pillow()
    image = ImageGrab.grab(all_screens=True)
    return image, _virtual_screen_origin()


def capture_wrapper(wrapper: Any, rectangle: RectangleInfo | None) -> tuple[Any, tuple[int, int]]:
    """要素・ウィンドウを撮り、画像と左上の画面座標を返す。"""
    load_pillow()
    try:
        image = wrapper.capture_as_image()
    except Exception as exc:
        raise ScreenshotError(f"画像を取得できませんでした: {exc}") from exc
    if image is None:
        raise ScreenshotError("画像を取得できませんでした（対象が画面外の可能性があります）")
    origin = (rectangle.left, rectangle.top) if rectangle is not None else (0, 0)
    return image, origin


def annotate(image: Any, origin: tuple[int, int], boxes: list[tuple[int, RectangleInfo]]) -> Any:
    """番号付きの枠を描き込んだ画像を返す。

    「画像の 3 番が探しているボタン」という形の対話が成立するようにするのが目的。
    """
    _, ImageDraw, _ = load_pillow()
    canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    for index, rectangle in boxes:
        left = rectangle.left - origin[0]
        top = rectangle.top - origin[1]
        right = rectangle.right - origin[0]
        bottom = rectangle.bottom - origin[1]
        draw.rectangle([left, top, right, bottom], outline=BOX_COLOR, width=BOX_WIDTH)
        _draw_label(draw, str(index), left, top)
    return canvas


def _draw_label(draw: Any, text: str, left: int, top: int) -> None:
    try:
        box = draw.textbbox((0, 0), text)
        width = box[2] - box[0]
        height = box[3] - box[1]
    except Exception:
        width, height = 8 * len(text), 12
    x0 = max(left, 0)
    # 枠の上に置くと画面上端で切れる。入らないときだけ枠の内側に落とす。
    y0 = top - height - LABEL_PADDING * 2
    if y0 < 0:
        y0 = top
    draw.rectangle(
        [x0, y0, x0 + width + LABEL_PADDING * 2, y0 + height + LABEL_PADDING * 2],
        fill=BOX_COLOR,
    )
    draw.text((x0 + LABEL_PADDING, y0 + LABEL_PADDING), text, fill=LABEL_TEXT_COLOR)


def save(image: Any, path: Path, force: bool) -> Path:
    if path.exists() and not force:
        raise ScreenshotError(f"すでに存在します: {path}（上書きするなら --force）")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        image.save(path)
    except OSError as exc:
        raise ScreenshotError(f"保存できませんでした: {path}: {exc}") from exc
    return path


def _virtual_screen_origin() -> tuple[int, int]:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        # SM_XVIRTUALSCREEN = 76, SM_YVIRTUALSCREEN = 77
        return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77))
    except Exception:
        return (0, 0)
