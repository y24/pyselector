from pyselector.overlay import selector_overlay


class FakeApp:
    def __init__(self, screens, primary=None):
        self._screens = screens
        self._primary = primary

    def screens(self):
        return self._screens

    def primaryScreen(self):
        return self._primary


def test_screens_returns_each_available_screen():
    screens = [object(), object(), object()]

    assert selector_overlay._screens(FakeApp(screens)) == screens


def test_screens_falls_back_to_primary_screen():
    primary = object()

    assert selector_overlay._screens(FakeApp([], primary)) == [primary]


def test_screens_returns_empty_when_no_screen_is_available():
    assert selector_overlay._screens(FakeApp([])) == []


def test_qt_application_args_do_not_force_dpi_unaware_mode(monkeypatch):
    monkeypatch.setattr(selector_overlay.sys, "argv", ["pyselector"])

    assert selector_overlay._qt_application_args() == ["pyselector"]
