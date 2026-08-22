from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from pyselector.model.diff_result import BackendDiff, NodeChange
from pyselector.utils.errors import ArgumentError

# ノードの同一性を判断するキー。ここが同じなら「同じ要素」とみなす。
IDENTITY_FIELDS = ("depth", "control_type", "class_name", "automation_id")

# 同一とみなしたノード同士で変化を見る属性。
COMPARED_FIELDS = ("window_text", "rectangle", "handle", "control_id", "friendly_class_name")


def load_tree_payload(path: Path) -> dict[str, Any]:
    """tree --json の出力ファイルを読み込む。"""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ArgumentError(f"ファイルを読み込めません: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ArgumentError(f"JSON として解析できません: {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("command") != "tree":
        raise ArgumentError(f"pyselector tree --json の出力ではありません: {path}")
    if not isinstance(raw.get("results"), list):
        raise ArgumentError(f"results がありません: {path}")
    return raw


def diff_tree_payloads(before: dict[str, Any], after: dict[str, Any]) -> list[BackendDiff]:
    before_results = _results_by_backend(before)
    after_results = _results_by_backend(after)
    backends = list(before_results) + [key for key in after_results if key not in before_results]
    return [
        _diff_backend(backend, before_results.get(backend), after_results.get(backend))
        for backend in backends
    ]


def _results_by_backend(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = {}
    for result in payload.get("results", []):
        if isinstance(result, dict) and isinstance(result.get("backend"), str):
            results[result["backend"]] = result
    return results


def _diff_backend(
    backend: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> BackendDiff:
    if before is None or after is None:
        missing = "before" if before is None else "after"
        return BackendDiff(
            backend=backend,
            status="failed",
            message=f"{missing} 側に {backend} の結果がありません",
        )
    for label, result in (("before", before), ("after", after)):
        if "nodes" not in result:
            return BackendDiff(
                backend=backend,
                status="failed",
                message=f"{label} 側に nodes がありません（--summary で取得した出力は比較できません）",
            )
        if result.get("status") != "success":
            return BackendDiff(
                backend=backend,
                status="failed",
                message=f"{label} 側の取得が失敗しています: {result.get('message')}",
            )

    return diff_nodes(backend, before.get("nodes") or [], after.get("nodes") or [])


def diff_nodes(backend: str, before_nodes: list[Any], after_nodes: list[Any]) -> BackendDiff:
    """ノードの辞書リスト同士を比較する。tree の出力ファイル比較と act --diff で共有する。"""
    before_indexed = _index_nodes(before_nodes)
    after_indexed = _index_nodes(after_nodes)

    removed = [node for key, node in before_indexed.items() if key not in after_indexed]
    added = [node for key, node in after_indexed.items() if key not in before_indexed]
    changed: list[NodeChange] = []
    unchanged = 0
    for key, after_node in after_indexed.items():
        before_node = before_indexed.get(key)
        if before_node is None:
            continue
        changes = _compare_node(before_node, after_node)
        if changes:
            changed.append(NodeChange(before=before_node, after=after_node, changes=changes))
        else:
            unchanged += 1

    return BackendDiff(backend=backend, added=added, removed=removed, changed=changed, unchanged=unchanged)


def _index_nodes(nodes: list[Any]) -> dict[tuple, dict[str, Any]]:
    """同一キーのノードには出現順の連番を付け、前後で対応付けられるようにする。"""
    counters: Counter = Counter()
    indexed: dict[tuple, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        key = tuple(node.get(field) for field in IDENTITY_FIELDS)
        indexed[(key, counters[key])] = node
        counters[key] += 1
    return indexed


def _compare_node(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changes = {}
    for field in COMPARED_FIELDS:
        before_value = before.get(field)
        after_value = after.get(field)
        if before_value != after_value:
            changes[field] = {"before": before_value, "after": after_value}
    return changes
