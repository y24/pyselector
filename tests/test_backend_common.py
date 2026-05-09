from pyselector.backends.common import PywinautoInspectorMixin


class FakeElementInfo:
    def __init__(self, name=None, class_name=None, control_id=None, control_type=None, automation_id=None):
        self.name = name
        self.class_name = class_name
        self.control_id = control_id
        self.control_type = control_type
        self.automation_id = automation_id


class FakeWrapper:
    def __init__(self, *, text="", class_name="", children=None):
        self.element_info = FakeElementInfo(name=text, class_name=class_name)
        self._text = text
        self._class_name = class_name
        self._children = children or []

    def window_text(self):
        return self._text

    def class_name(self):
        return self._class_name

    def children(self):
        return self._children

    def descendants(self, **condition):
        matches = []
        for child in self._children:
            if not condition or child.class_name() == condition.get("class_name"):
                matches.append(child)
        return matches


class FakeInspector(PywinautoInspectorMixin):
    backend_name = "uia"

    def __init__(self, root):
        super().__init__()
        self.root = root

    def _scope_root(self, scope):
        return self.root


def test_find_elements_stops_after_limit():
    root = FakeWrapper(
        children=[
            FakeWrapper(class_name="Button"),
            FakeWrapper(class_name="Button"),
            FakeWrapper(class_name="Button"),
        ]
    )
    inspector = FakeInspector(root)

    matches, reached_limit = inspector.find_elements({}, {"class_name": "Button", "_max_items": 2})

    assert len(matches) == 2
    assert reached_limit is True
