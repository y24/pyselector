from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.target_window import TargetWindowInfo


class BackendInspector(ABC):
    backend_name: str

    @abstractmethod
    def element_from_point(self, x: int, y: int) -> ElementInfo:
        raise NotImplementedError

    @abstractmethod
    def element_from_handle(self, handle: int) -> ElementInfo:
        raise NotImplementedError

    @abstractmethod
    def element_from_ref(self, ref: str) -> ElementInfo:
        raise NotImplementedError

    @abstractmethod
    def get_target_window(self, element: ElementInfo) -> TargetWindowInfo:
        raise NotImplementedError

    @abstractmethod
    def get_hierarchy(self, element: ElementInfo) -> list[HierarchyNode]:
        raise NotImplementedError

    @abstractmethod
    def find_elements(self, scope: dict[str, Any], condition: dict[str, Any]) -> tuple[list[ElementInfo], bool]:
        raise NotImplementedError

    @abstractmethod
    def find_window_by_title(self, title: str, use_regex: bool) -> ElementInfo:
        raise NotImplementedError

    @abstractmethod
    def find_window_by_handle(self, handle: int) -> ElementInfo:
        raise NotImplementedError

    @abstractmethod
    def list_windows(self, only_visible: bool = True) -> list[ElementInfo]:
        raise NotImplementedError

    @abstractmethod
    def perform_action(self, element: ElementInfo, action: str, value: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def refresh_element(self, element: ElementInfo) -> ElementInfo:
        raise NotImplementedError

    @abstractmethod
    def read_element_state(self, element: ElementInfo) -> ElementInfo:
        raise NotImplementedError

    @abstractmethod
    def walk_tree(
        self,
        root: ElementInfo,
        depth: int,
        max_items: int,
        only_visible: bool,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[list[HierarchyNode], bool]:
        raise NotImplementedError

    @abstractmethod
    def walk_elements(
        self,
        root: ElementInfo,
        depth: int,
        max_items: int,
        only_visible: bool,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[list[ElementInfo], bool]:
        raise NotImplementedError
