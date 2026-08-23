from __future__ import annotations

import re
import warnings
from collections import OrderedDict
from dataclasses import replace
from typing import Any, Callable

from pyselector.actions import perform_action
from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.target_window import TargetWindowInfo
from pyselector.server.refs import RefRegistry, stale_ref_message
from pyselector.utils.errors import ElementNotFoundError, StaleRefError, TargetWindowNotFoundError
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


def element_from_wrapper(
    wrapper: Any,
    backend: str,
    depth: int | None = None,
    include_children_count: bool = True,
    include_process_name: bool = True,
) -> ElementInfo:
    element_info = getattr(wrapper, "element_info", None)
    process_id = wrapper_process_id(wrapper)
    control_id = safe_call(wrapper, "control_id")
    if control_id is None:
        control_id = getattr(element_info, "control_id", None)
    try:
        control_id = int(control_id) if control_id is not None else None
    except Exception:
        control_id = None
    children = safe_call(wrapper, "children", []) if include_children_count else None
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
        process_name=get_process_name(process_id) if include_process_name else None,
    )


#: 常駐していないときの参照表に付ける印。ref はプロセス終了とともに消えるため
#: 外には出さないが、形式は常駐時と揃えておく。
LOCAL_INSTANCE_ID = "local"


def is_wrapper_alive(wrapper: Any) -> bool:
    """wrapper がまだ画面上の要素を指しているかを軽く確かめる。

    画面が変わると wrapper は無効になる。呼べる ``is_visible`` が無い実装は
    生存とみなす（判定できないことを失効の根拠にしない）。
    """
    checker = getattr(wrapper, "is_visible", None)
    if not callable(checker):
        return True
    try:
        checker()
    except Exception:
        return False
    return True


def element_info_matches(element_info: Any, condition: dict[str, Any]) -> bool:
    if "handle" in condition and getattr(element_info, "handle", None) != condition["handle"]:
        return False
    if "class_name" in condition and getattr(element_info, "class_name", None) != condition["class_name"]:
        return False
    if "control_id" in condition and getattr(element_info, "control_id", None) != condition["control_id"]:
        return False
    if "control_type" in condition and getattr(element_info, "control_type", None) != condition["control_type"]:
        return False
    if "auto_id" in condition and getattr(element_info, "automation_id", None) != condition["auto_id"]:
        return False
    text = getattr(element_info, "rich_text", None) or getattr(element_info, "name", None) or ""
    if "title" in condition and text != condition["title"]:
        return False
    if "title_re" in condition and re.match(condition["title_re"], text) is None:
        return False
    return True


def _matched_titles_hint(matches: list[Any], max_titles: int = 5) -> str:
    titles = [safe_call(window, "window_text") or "" for window in matches[:max_titles]]
    if not titles:
        return ""
    listed = ", ".join(f'"{title}"' for title in titles)
    suffix = ", ..." if len(matches) > max_titles else ""
    return f"（{listed}{suffix}）"


def hierarchy_node_from_wrapper(wrapper: Any, backend: str, depth: int) -> HierarchyNode:
    info = element_from_wrapper(
        wrapper,
        backend,
        depth,
        include_children_count=False,
        include_process_name=False,
    )
    return HierarchyNode(
        depth=depth,
        window_text=info.window_text,
        control_type=info.control_type,
        automation_id=info.automation_id,
        class_name=info.class_name,
        friendly_class_name=info.friendly_class_name,
        control_id=info.control_id,
        handle=info.handle,
        rectangle=info.rectangle,
    )


class PywinautoInspectorMixin:
    backend_name: str

    def __init__(self) -> None:
        self._last_wrapper: Any = None
        # handle からの逆引き。参照表と同じく、常駐プロセスでは際限なく増えうるので
        # 参照表の上限に合わせて古いものから捨てる。
        self._wrapper_by_handle: "OrderedDict[int, Any]" = OrderedDict()
        # プロセス内だけで使う参照表。上限は設けない（1 コマンドで終わるため）。
        # 常駐モードではサーバーが共有の参照表に差し替える。
        self._refs = RefRegistry(LOCAL_INSTANCE_ID, max_refs=None)

    def use_ref_registry(self, registry: RefRegistry) -> None:
        """サーバーが持つ共有の参照表に差し替える。

        backend をまたいで 1 つの表を使うことで、ref のインスタンス ID と連番が
        サーバー全体で一意になる。
        """
        self._refs = registry

    def _desktop(self) -> Any:
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"Revert to STA COM threading mode",
                    category=UserWarning,
                    module=r"pywinauto",
                )
                from pywinauto import Desktop
        except Exception as exc:
            raise ElementNotFoundError("pywinauto をインポートできませんでした") from exc
        return Desktop(backend=self.backend_name)

    def _remember(self, wrapper: Any) -> ElementInfo:
        self._last_wrapper = wrapper
        return self._track(wrapper, element_from_wrapper(wrapper, self.backend_name))

    def _track(self, wrapper: Any, element: ElementInfo) -> ElementInfo:
        """要素と pywinauto wrapper の対応を記録し、参照 ID を持つ要素を返す。

        handle を持たない UIA 要素でも、後から同じ wrapper を解決できるようにする。
        """
        ref = self._refs.issue(self.backend_name, wrapper)
        if element.handle is not None:
            self._wrapper_by_handle[element.handle] = wrapper
            self._wrapper_by_handle.move_to_end(element.handle)
            self._evict_handles()
        return replace(element, ref=ref)

    def _evict_handles(self) -> None:
        limit = self._refs.max_refs
        if limit is None:
            return
        while len(self._wrapper_by_handle) > limit:
            self._wrapper_by_handle.popitem(last=False)

    def _wrapper_for(self, element: ElementInfo) -> Any:
        if element.ref is not None:
            wrapper = self._refs.get(element.ref)
            if wrapper is not None:
                return wrapper
        if element.handle is not None and element.handle in self._wrapper_by_handle:
            self._wrapper_by_handle.move_to_end(element.handle)
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
                window = self._desktop().window(handle=target_handle)
                return window.wrapper_object() if hasattr(window, "wrapper_object") else window
            except Exception:
                pass
        return self._last_wrapper or self._desktop()

    def find_elements(self, scope: dict[str, Any], condition: dict[str, Any]) -> tuple[list[ElementInfo], bool]:
        search_condition = dict(condition)
        max_items = search_condition.pop("_max_items", None)
        if max_items is not None:
            try:
                root = self._scope_root(scope)
                wrappers, reached_limit = self._find_wrappers_limited(root, search_condition, max_items)
            except Exception:
                wrappers, reached_limit = [], False
            return [element_from_wrapper(w, self.backend_name, include_children_count=False) for w in wrappers], reached_limit
        try:
            root = self._scope_root(scope)
            wrappers = root.descendants(**search_condition)
        except Exception:
            wrappers = []
        return [element_from_wrapper(w, self.backend_name, include_children_count=False) for w in wrappers], False

    def find_elements_chain(
        self,
        scope: dict[str, Any],
        steps: list[dict[str, Any]],
        max_items: int | None,
    ) -> tuple[list[ElementInfo], bool, int | None]:
        if not steps:
            return [], False, None
        try:
            current_wrappers = [self._scope_root(scope)]
            parent_hits: int | None = None
            reached_limit = False
            for index, condition in enumerate(steps):
                next_wrappers = []
                step_condition = dict(condition)
                found_index = step_condition.pop("found_index", None)
                for wrapper in current_wrappers:
                    try:
                        step_max_items = max_items
                        if found_index is not None:
                            try:
                                step_max_items = max(max_items or 0, int(found_index) + 1)
                            except (TypeError, ValueError):
                                step_max_items = max_items
                        if step_max_items is None:
                            found_wrappers = wrapper.descendants(**step_condition)
                            found_reached_limit = False
                        else:
                            found_wrappers, found_reached_limit = self._find_wrappers_limited(wrapper, step_condition, step_max_items)
                        if found_index is not None:
                            try:
                                found_wrappers = [found_wrappers[int(found_index)]]
                            except (IndexError, TypeError, ValueError):
                                found_wrappers = []
                            found_reached_limit = False
                        next_wrappers.extend(found_wrappers)
                        reached_limit = reached_limit or found_reached_limit
                    except Exception:
                        continue
                if index == 0 and len(steps) > 1:
                    parent_hits = len(next_wrappers)
                if max_items is not None and len(next_wrappers) > max_items:
                    next_wrappers = next_wrappers[:max_items]
                    reached_limit = True
                current_wrappers = next_wrappers
            return [
                element_from_wrapper(w, self.backend_name, include_children_count=False)
                for w in current_wrappers
            ], reached_limit, parent_hits
        except Exception:
            return [], False, None

    def _find_wrappers_limited(self, root: Any, condition: dict[str, Any], max_items: int) -> tuple[list[Any], bool]:
        if self.backend_name == "win32":
            try:
                return self._find_win32_wrappers_limited(root, condition, max_items)
            except Exception:
                pass
        wrappers = root.descendants(**condition)
        if len(wrappers) > max_items:
            return wrappers[:max_items], True
        return wrappers, False

    def _find_win32_wrappers_limited(self, root: Any, condition: dict[str, Any], max_items: int) -> tuple[list[Any], bool]:
        from pywinauto.controls.hwndwrapper import HwndElementInfo
        from pywinauto import win32functions
        import ctypes
        from ctypes import wintypes

        root_info = getattr(root, "element_info", None)
        if not isinstance(root_info, HwndElementInfo):
            raise TypeError("root is not a win32 wrapper")
        wrapper_class = type(root)
        element_infos: list[Any] = []
        reached_limit = False

        def enum_window_proc(hwnd: int, lparam: int) -> bool:
            nonlocal reached_limit
            element_info = HwndElementInfo(hwnd)
            if element_info_matches(element_info, condition):
                if len(element_infos) >= max_items:
                    reached_limit = True
                    return False
                element_infos.append(element_info)
            return True

        enum_win_proc_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        proc = enum_win_proc_t(enum_window_proc)
        win32functions.EnumChildWindows(root_info.handle, proc, 0)
        return [wrapper_class(element_info) for element_info in element_infos], reached_limit

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
            raise ElementNotFoundError(f"一致するウィンドウ数が {len(matches)} 件です{_matched_titles_hint(matches)}")
        return self._remember(matches[0])

    def find_window_by_handle(self, handle: int) -> ElementInfo:
        return self.element_from_handle(handle)

    def element_from_ref(self, ref: str) -> ElementInfo:
        """参照 ID から要素を引き直す。

        参照表に無い、あるいは wrapper が既に死んでいる場合は ``stale_ref`` にする。
        act が失効した ref で別の要素を操作しないよう、使う前に必ずここを通す（設計 7.4）。
        """
        wrapper = self._refs.get(ref)
        if wrapper is None or not is_wrapper_alive(wrapper):
            raise StaleRefError(stale_ref_message(ref))
        self._last_wrapper = wrapper
        return replace(element_from_wrapper(wrapper, self.backend_name), ref=ref)

    def element_from_handle(self, handle: int) -> ElementInfo:
        try:
            window = self._desktop().window(handle=handle)
            wrapper = window.wrapper_object() if hasattr(window, "wrapper_object") else window
        except Exception as exc:
            raise ElementNotFoundError(f"handle {handle:#x} の要素を取得できませんでした") from exc
        if wrapper is None:
            raise ElementNotFoundError(f"handle {handle:#x} の要素を取得できませんでした")
        return self._remember(wrapper)

    def perform_action(self, element: ElementInfo, action: str, value: str | None = None) -> str:
        return perform_action(self._wrapper_for(element), action, value)

    def refresh_element(self, element: ElementInfo) -> ElementInfo:
        """操作後の状態を読み直す。wrapper は再解決せず、同じ要素を見る。"""
        wrapper = self._wrapper_for(element)
        return element_from_wrapper(
            wrapper,
            self.backend_name,
            element.depth,
            include_children_count=False,
            include_process_name=False,
        )

    def list_windows(self, only_visible: bool = True) -> list[ElementInfo]:
        try:
            windows = self._desktop().windows(visible_only=only_visible)
        except Exception as exc:
            raise ElementNotFoundError("ウィンドウ一覧を取得できませんでした") from exc
        return [
            self._track(
                wrapper,
                element_from_wrapper(
                    wrapper,
                    self.backend_name,
                    0,
                    include_children_count=False,
                    include_process_name=False,
                ),
            )
            for wrapper in windows
        ]

    def walk_tree(
        self,
        root: ElementInfo,
        depth: int,
        max_items: int,
        only_visible: bool,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[list[HierarchyNode], bool]:
        collected, reached_limit = self._walk_wrappers(root, depth, max_items, only_visible, progress_callback)
        nodes = [hierarchy_node_from_wrapper(wrapper, self.backend_name, node_depth) for wrapper, node_depth in collected]
        return nodes, reached_limit

    def walk_elements(
        self,
        root: ElementInfo,
        depth: int,
        max_items: int,
        only_visible: bool,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[list[ElementInfo], bool]:
        """走査した要素を ElementInfo として返す。

        各要素は参照 ID を持つため、後から get_hierarchy() などで再解決できる。
        """
        collected, reached_limit = self._walk_wrappers(root, depth, max_items, only_visible, progress_callback)
        elements = [
            self._track(
                wrapper,
                element_from_wrapper(
                    wrapper,
                    self.backend_name,
                    node_depth,
                    include_children_count=False,
                    include_process_name=False,
                ),
            )
            for wrapper, node_depth in collected
        ]
        return elements, reached_limit

    def _walk_wrappers(
        self,
        root: ElementInfo,
        depth: int,
        max_items: int,
        only_visible: bool,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[list[tuple[Any, int]], bool]:
        root_wrapper = self._wrapper_for(root)
        collected: list[tuple[Any, int]] = []
        reached_limit = False

        def walk(wrapper: Any, current_depth: int) -> None:
            nonlocal reached_limit
            if reached_limit:
                return
            if only_visible and safe_call(wrapper, "is_visible") is False:
                return
            collected.append((wrapper, current_depth))
            if progress_callback is not None:
                progress_callback(len(collected), max_items)
            if len(collected) >= max_items:
                reached_limit = True
                return
            if current_depth >= depth:
                return
            for child in safe_call(wrapper, "children", []) or []:
                walk(child, current_depth + 1)

        walk(root_wrapper, 0)
        return collected, reached_limit
