from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo
from pyselector.selector.snippet import build_code_snippet


def test_code_snippet_clicks_target_at_end():
    evaluation = SelectorEvaluation(
        candidate=SelectorCandidate(
            backend="uia",
            selector_text='dlg.child_window(auto_id="num1Button", control_type="Button")',
            selector_kind="uia_auto_id_control_type",
            condition={"auto_id": "num1Button", "control_type": "Button"},
        ),
        hits=1,
    )
    target_window = TargetWindowInfo(backend="uia", title="Calculator")

    snippet = build_code_snippet("uia", target_window, [evaluation])

    assert snippet == (
        'from pywinauto import Desktop\n'
        'dlg = Desktop(backend="uia").window(title="Calculator")\n'
        'target = dlg.child_window(auto_id="num1Button", control_type="Button")\n'
        'target.wait("visible", timeout=10).click()'
    )
