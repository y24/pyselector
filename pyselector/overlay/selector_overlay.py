from __future__ import annotations

import ctypes
import os
import sys


def select_point_with_overlay() -> tuple[int, int] | None:
    """
    Show a full-desktop overlay and return the clicked screen coordinate.

    Returns:
        (x, y): left-click position in screen coordinates
        None: canceled with Esc
    """
    _configure_qt_logging()
    try:
        from PySide6.QtCore import QEventLoop, Qt, QTimer
        from PySide6.QtGui import QColor, QCursor, QKeyEvent, QMouseEvent, QPainter, QPen
        from PySide6.QtWidgets import QApplication, QWidget
    except ImportError as exc:
        raise RuntimeError("PySide6 is required for overlay inspect. Install dependencies with `pip install .`.") from exc

    class OverlayController:
        def __init__(self, loop: QEventLoop) -> None:
            self.selected_point: tuple[int, int] | None = None
            self._loop = loop
            self._overlays: list[SelectorOverlay] = []
            self._finished = False

        def add_overlay(self, overlay: "SelectorOverlay") -> None:
            self._overlays.append(overlay)

        def select(self, point: tuple[int, int]) -> None:
            self.selected_point = point
            self.close_all()

        def cancel(self) -> None:
            self.close_all()

        def close_all(self) -> None:
            if self._finished:
                return
            self._finished = True
            for overlay in list(self._overlays):
                overlay.close()
            QTimer.singleShot(0, self._loop.quit)

        def overlay_closed(self, overlay: "SelectorOverlay") -> None:
            if overlay in self._overlays:
                self._overlays.remove(overlay)
            if self._finished:
                return
            self.close_all()

    class SelectorOverlay(QWidget):
        def __init__(self, screen, controller: OverlayController) -> None:
            super().__init__()
            self._controller = controller
            self._cursor_pos = QCursor.pos()
            self.setScreen(screen)
            self.setGeometry(screen.geometry())
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._update_cursor_position)
            self._timer.start(16)

        def _update_cursor_position(self) -> None:
            pos = QCursor.pos()
            if pos != self._cursor_pos:
                self._cursor_pos = pos
                self.update()

        def paintEvent(self, event) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 92))
            local = self.mapFromGlobal(self._cursor_pos)
            if not self.rect().contains(local):
                return
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
            painter.drawLine(local.x(), 0, local.x(), self.height())
            painter.drawLine(0, local.y(), self.width(), local.y())
            painter.setPen(QPen(QColor(36, 210, 255, 240), 1))
            painter.drawEllipse(local, 6, 6)

        def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            self._cursor_pos = _event_global_pos(event)
            self.update()

        def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() != Qt.MouseButton.LeftButton:
                return
            self._controller.select(_get_physical_cursor_position())

        def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
            if event.key() == Qt.Key.Key_Escape:
                self._controller.cancel()

        def closeEvent(self, event) -> None:  # noqa: N802
            self._controller.overlay_closed(self)
            super().closeEvent(event)

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(_qt_application_args())

    loop = QEventLoop()
    controller = OverlayController(loop)
    overlays = [SelectorOverlay(screen, controller) for screen in _screens(app)]
    if not overlays:
        if owns_app:
            app.quit()
        return None
    for overlay in overlays:
        controller.add_overlay(overlay)
        overlay.show()
        overlay.raise_()
    if overlays:
        overlays[0].activateWindow()
        overlays[0].setFocus()
    loop.exec()
    if owns_app:
        app.quit()
    return controller.selected_point


def _event_global_pos(event) -> "QPoint":
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()


def _screens(app):
    screens = app.screens()
    if not screens:
        primary = app.primaryScreen()
        return [primary] if primary is not None else []
    return screens


def _get_physical_cursor_position() -> tuple[int, int]:
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    point = POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        raise RuntimeError("cursor position could not be read")
    return point.x, point.y


def _qt_application_args() -> list[str]:
    executable = sys.argv[0] if sys.argv else "pyselector"
    return [executable]


def _configure_qt_logging() -> None:
    rules = os.environ.get("QT_LOGGING_RULES")
    qpa_window_rule = "qt.qpa.window=false"
    if not rules:
        os.environ["QT_LOGGING_RULES"] = qpa_window_rule
    elif qpa_window_rule not in rules:
        os.environ["QT_LOGGING_RULES"] = f"{rules};{qpa_window_rule}"
