from __future__ import annotations

import re
from typing import Any

from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.target_window import TargetWindowInfo
from pyselector.utils.errors import ElementNotFoundError, TargetWindowNotFoundError
from pyselector.utils.process import get_process_name


def safe_call(obj: Any, name: str, default: Any = None, *args: Any) -> Any:
    try:
        attr = getattr(obj, name)
        return attr(*args) if callable(attr) else attr
    except Exception:
        return default


def rect_from_wrapper(wrapper: Any) -> RectangleInfo | None:
    rect = safe_call(wrapper, "rectangle")
    if rect is None:
        return None
    try:
        return RectangleInfo(left=rect.left, top=rect.top, right=rect.right, bottom=rect.bottom)
    except Exception:
        return None


def wrapper_handle(wrapper: Any) -> int | None:
    value = safe_call(wrapper, "handle")
    if value is None:
        value = getattr(getattr(wrapper, "element_info", None), "handle", None)
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def wrapper_process_id(wrapper: Any) -> int | None:
    value = safe_call(wrapper, "process_id")
    if value is None:
        value = getattr(getattr(wrapper, "element_info", None), "process_id", None)
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def element_from_wrapper(wrapper: Any, backend: str, depth: int | None = None) -> ElementInfo:
    element_info = getattr(wrapper, "element_info", None)
    process_id = wrapper_process_id(wrapper)
    control_id = safe_call(wrapper, "control_id")
    if control_id is None:
        control_id = getattr(element_info, "control_id", None)
    try:
        control_id = int(control_id) if control_id is not None else None
    except Exception:
        control_id = None
    children = safe_call(wrapper, "children", [])
    return ElementInfo(
        backend=backend,
        window_text=safe_call(wrapper, "window_text") or getattr(element_info, "name", None),
        control_type=getattr(element_info, "control_type", None),
        automation_id=getattr(element_info, "automation_id", None),
        class_name=safe_call(wrapper, "class_name") or getattr(element_info, "class_name", None),
        friendly_class_name=safe_call(wrapper, "friendly_class_name"),
        control_id=control_id,
        children_count=len(children) if isinstance(children, list) else None,
        depth=depth,
        rectangle=rect_from_wrapper(wrapper),
        is_visible=safe_call(wrapper, "is_visible"),
        is_enabled=safe_call(wrapper, "is_enabled"),
        handle=wrapper_handle(wrapper),
        process_id=process_id,
        process_name=get_process_name(process_id),
    )


def hierarchy_node_from_wrapper(wrapper: Any, backend: str, depth: int) -> HierarchyNode:
    info = element_from_wrapper(wrapper, backend, depth)
    return HierarchyNode(
        depth=depth,
        window_text=info.window_text,
        control_type=info.control_type,
        automation_id=info.automation_id,
        class_name=info.class_name,
        control_id=info.control_id,
        handle=info.handle,
        rectangle=info.rectangle,
    )


class PywinautoInspectorMixin:
    backend_name: str

    def __init__(self) -> None:
        self._last_wrapper: Any = None
        self._wrapper_by_handle: dict[int, Any] = {}

    def _desktop(self) -> Any:
        try:
            from pywinauto import Desktop
        except Exception as exc:
            raise ElementNotFoundError("pywinauto をインポートできませんでした") from exc
        return Desktop(backend=self.backend_name)

    def _remember(self, wrapper: Any) -> ElementInfo:
        self._last_wrapper = wrapper
        handle = wrapper_handle(wrapper)
        if handle is not None:
            self._wrapper_by_handle[handle] = wrapper
        return element_from_wrapper(wrapper, self.backend_name)

    def _wrapper_for(self, element: ElementInfo) -> Any:
        if element.handle is not None and element.handle in self._wrapper_by_handle:
            return self._wrapper_by_handle[element.handle]
        if self._last_wrapper is not None:
            return self._last_wrapper
        raise ElementNotFoundError("対象要素の内部参照がありません")

    def element_from_point(self, x: int, y: int) -> ElementInfo:
        try:
            wrapper = self._desktop().from_point(x, y)
        except Exception as exc:
            raise ElementNotFoundError("カーソル下のUI要素を取得できませんでした") from exc
        return self._remember(wrapper)

    def get_target_window(self, element: ElementInfo) -> TargetWindowInfo:
        wrapper = self._wrapper_for(element)
        top = wrapper
        try:
            top = wrapper.top_level_parent()
        except Exception:
            parent = wrapper
            while True:
                nxt = safe_call(parent, "parent")
                if nxt is None:
                    break
                top = nxt
                parent = nxt
        if top is None:
            raise TargetWindowNotFoundError("対象ウィンドウを特定できませんでした")
        info = element_from_wrapper(top, self.backend_name, 0)
        return TargetWindowInfo(
            backend=self.backend_name,
            title=info.window_text,
            class_name=info.class_name,
            process_name=info.process_name,
            process_id=info.process_id,
            handle=info.handle,
        )

    def get_hierarchy(self, element: ElementInfo) -> list[HierarchyNode]:
        wrapper = self._wrapper_for(element)
        items: list[Any] = []
        current = wrapper
        for _ in range(64):
            if current is None:
                break
            items.append(current)
            parent = safe_call(current, "parent")
            if parent is None:
                break
            current = parent
        items.reverse()
        return [hierarchy_node_from_wrapper(item, self.backend_name, i) for i, item in enumerate(items)]

    def _scope_root(self, scope: dict[str, Any]) -> Any:
        if scope.get("scope") == "desktop":
            return self._desktop()
        target_handle = scope.get("target_handle")
        if target_handle:
            try:
                return self._desktop().window(handle=target_handle)
            except Exception:
                pass
        return self._last_wrapper or self._desktop()

    def find_elements(self, scope: dict[str, Any], condition: dict[str, Any]) -> tuple[list[ElementInfo], bool]:
        search_condition = dict(condition)
        max_items = search_condition.pop("_max_items", None)
        try:
            root = self._scope_root(scope)
            wrappers = root.descendants(**search_condition)
        except Exception:
            wrappers = []
        reached_limit = False
        if max_items is not None and len(wrappers) > max_items:
            wrappers = wrappers[:max_items]
            reached_limit = True
        return [element_from_wrapper(w, self.backend_name) for w in wrappers], reached_limit

    def find_window_by_title(self, title: str, use_regex: bool) -> ElementInfo:
        try:
            windows = self._desktop().windows()
        except Exception as exc:
            raise ElementNotFoundError("ウィンドウ一覧を取得できませんでした") from exc
        matches = []
        for window in windows:
            window_title = safe_call(window, "window_text") or ""
            if (use_regex and re.search(title, window_title)) or (not use_regex and title in window_title):
                matches.append(window)
        if len(matches) != 1:
            raise ElementNotFoundError(f"一致するウィンドウ数が {len(matches)} 件です")
        return self._remember(matches[0])

    def walk_tree(self, root: ElementInfo, depth: int, max_items: int, only_visible: bool) -> tuple[list[HierarchyNode], bool]:
        root_wrapper = self._wrapper_for(root)
        nodes: list[HierarchyNode] = []
        reached_limit = False

        def walk(wrapper: Any, current_depth: int) -> None:
            nonlocal reached_limit
            if reached_limit:
                return
            if only_visible and safe_call(wrapper, "is_visible") is False:
                return
            nodes.append(hierarchy_node_from_wrapper(wrapper, self.backend_name, current_depth))
            if len(nodes) >= max_items:
                reached_limit = True
                return
            if current_depth >= depth:
                return
            for child in safe_call(wrapper, "children", []) or []:
                walk(child, current_depth + 1)

        walk(root_wrapper, 0)
        return nodes, reached_limit
