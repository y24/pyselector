from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.selector.generator import generate_candidates


def test_win32_candidates_do_not_use_unstable_native_ids():
    element = ElementInfo(
        backend="win32",
        window_text="OK",
        class_name="Button",
        control_id=1,
        handle=0x123456,
    )

    candidates = generate_candidates(element)

    assert [candidate.selector_kind for candidate in candidates] == [
        "win32_title_class_name",
        "win32_class_name",
        "win32_title",
    ]
    assert candidates[0].condition == {"title": "OK", "class_name": "Button"}
    assert all("control_id" not in candidate.condition for candidate in candidates)
    assert all("handle" not in candidate.condition for candidate in candidates)


def test_uia_candidates_use_auto_id_and_control_type_first():
    element = ElementInfo(
        backend="uia",
        window_text="1",
        automation_id="num1Button",
        control_type="Button",
    )

    candidates = generate_candidates(element)

    assert candidates[0].selector_text == 'dlg.child_window(auto_id="num1Button", control_type="Button")'
    assert candidates[1].selector_text == 'dlg.child_window(title="1", auto_id="num1Button", control_type="Button")'
    assert candidates[4].selector_text == 'dlg.child_window(title_re="^1$", control_type="Button")'


def test_selector_text_keeps_japanese_readable():
    element = ElementInfo(
        backend="win32",
        window_text="電卓",
        class_name="Text",
    )

    candidates = generate_candidates(element)

    assert candidates[0].selector_text == 'dlg.child_window(title="電卓", class_name="Text")'
    assert candidates[2].selector_text == 'dlg.child_window(title="電卓")'


def test_selector_text_escapes_python_string_syntax():
    element = ElementInfo(
        backend="uia",
        window_text='名前"\\\n',
        automation_id="nameBox",
        control_type="Edit",
    )

    candidates = generate_candidates(element)

    assert candidates[1].selector_text == 'dlg.child_window(title="名前\\"\\\\\\n", auto_id="nameBox", control_type="Edit")'


def test_win32_candidates_include_parent_scoped_edit_selector():
    element = ElementInfo(
        backend="win32",
        window_text="L:\\Cubase Projects\\Audio",
        class_name="Edit",
        control_id=1001,
    )
    hierarchy = [
        HierarchyNode(depth=0, class_name="Afx:00400000:8:00010003:00000006:00010B7B"),
        HierarchyNode(depth=1, class_name="ReBarWindow32", control_id=59396),
        HierarchyNode(
            depth=2,
            window_text="L:\\Cubase Projects\\Audio",
            class_name="ComboBox",
            control_id=1003,
        ),
        HierarchyNode(
            depth=3,
            window_text="L:\\Cubase Projects\\Audio",
            class_name="Edit",
            control_id=1001,
        ),
    ]

    candidates = generate_candidates(element, hierarchy)
    selector_texts = [candidate.selector_text for candidate in candidates]

    assert 'dlg.child_window(title="L:\\\\Cubase Projects\\\\Audio", class_name="ComboBox").child_window(class_name="Edit")' in selector_texts
    assert 'dlg.child_window(class_name="ComboBox").child_window(class_name="Edit")' in selector_texts
    assert all("control_id" not in candidate.selector_text for candidate in candidates)
    assert all("control_id" not in step.condition for candidate in candidates for step in candidate.steps)
    parent_candidate = next(
        candidate
        for candidate in candidates
        if candidate.selector_text
        == 'dlg.child_window(title="L:\\\\Cubase Projects\\\\Audio", class_name="ComboBox").child_window(class_name="Edit")'
    )
    assert parent_candidate.uses_parent_scope is True
    assert parent_candidate.uses_control_id is False
