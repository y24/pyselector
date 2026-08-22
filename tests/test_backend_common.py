from pyselector.backends import common
from pyselector.backends.common import PywinautoInspectorMixin
from pyselector.model.element_info import ElementInfo


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


class ChildrenErrorWrapper(FakeWrapper):
    def children(self):
        raise AssertionError("children() should not be called")


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


def test_find_elements_does_not_fetch_children_count_for_matches():
    root = FakeWrapper(children=[ChildrenErrorWrapper(class_name="Button")])
    inspector = FakeInspector(root)

    matches, reached_limit = inspector.find_elements({}, {"class_name": "Button"})

    assert len(matches) == 1
    assert matches[0].children_count is None
    assert reached_limit is False


def test_walk_tree_reports_progress():
    root = FakeWrapper(
        text="root",
        children=[
            FakeWrapper(text="child1"),
            FakeWrapper(text="child2"),
        ],
    )
    inspector = FakeInspector(root)
    inspector._last_wrapper = root
    progress = []

    nodes, reached_limit = inspector.walk_tree(
        ElementInfo(backend="uia"),
        depth=1,
        max_items=10,
        only_visible=False,
        progress_callback=lambda done, total: progress.append((done, total)),
    )

    assert reached_limit is False
    assert len(nodes) == 3
    assert progress == [(1, 10), (2, 10), (3, 10)]


def test_walk_tree_does_not_resolve_process_name_per_node(monkeypatch):
    root = FakeWrapper(
        text="root",
        children=[
            FakeWrapper(text="child1"),
            FakeWrapper(text="child2"),
        ],
    )
    inspector = FakeInspector(root)
    inspector._last_wrapper = root
    calls = []

    monkeypatch.setattr(common, "get_process_name", lambda process_id: calls.append(process_id) or "app.exe")

    nodes, reached_limit = inspector.walk_tree(
        ElementInfo(backend="uia"),
        depth=1,
        max_items=10,
        only_visible=False,
    )

    assert reached_limit is False
    assert len(nodes) == 3
    assert calls == []


def test_walk_elements_returns_elements_with_depth_and_ref():
    root = FakeWrapper(text="root", children=[FakeWrapper(text="child1"), FakeWrapper(text="child2")])
    inspector = FakeInspector(root)
    inspector._last_wrapper = root

    elements, reached_limit = inspector.walk_elements(
        ElementInfo(backend="uia"),
        depth=1,
        max_items=10,
        only_visible=False,
    )

    assert reached_limit is False
    assert [element.window_text for element in elements] == ["root", "child1", "child2"]
    assert [element.depth for element in elements] == [0, 1, 1]
    assert len({element.ref for element in elements}) == 3


def test_walk_elements_stops_at_max_items():
    root = FakeWrapper(text="root", children=[FakeWrapper(text="child1"), FakeWrapper(text="child2")])
    inspector = FakeInspector(root)
    inspector._last_wrapper = root

    elements, reached_limit = inspector.walk_elements(
        ElementInfo(backend="uia"),
        depth=1,
        max_items=2,
        only_visible=False,
    )

    assert reached_limit is True
    assert len(elements) == 2


def test_wrapper_for_resolves_each_walked_element_without_handles():
    """handle を持たない UIA 要素でも、要素ごとに正しい wrapper を解決できること。"""
    children = [FakeWrapper(text="child1"), FakeWrapper(text="child2")]
    root = FakeWrapper(text="root", children=children)
    inspector = FakeInspector(root)
    inspector._last_wrapper = root

    elements, _ = inspector.walk_elements(
        ElementInfo(backend="uia"),
        depth=1,
        max_items=10,
        only_visible=False,
    )

    assert [inspector._wrapper_for(element) for element in elements] == [root, children[0], children[1]]


def test_wrapper_for_falls_back_to_the_last_wrapper_without_a_ref():
    root = FakeWrapper(text="root")
    inspector = FakeInspector(root)
    inspector._last_wrapper = root

    assert inspector._wrapper_for(ElementInfo(backend="uia")) is root
