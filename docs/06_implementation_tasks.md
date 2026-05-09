# 06_implementation_tasks.md

# pyselector 実装タスク一覧

## 1. 目的

本書は、pywinauto Selector Inspector CLI の実装タスクを定義する。

本ツールは、Windowsアプリケーション上のUI要素をカーソル位置から特定し、pywinautoで利用可能なセレクター候補とヒット件数を表示するCLIツールである。

本書では、実装作業を段階的に進められるよう、以下を定義する。

- 実装フェーズ
- タスク一覧
- 各タスクの目的
- 実装対象ファイル
- 完了条件
- 注意点

---

## 2. 実装方針

## 2.1 基本方針

実装は、小さな単位に分けて段階的に進める。

優先順位は以下とする。

```text
1. CLIとして起動できる
2. カーソル下の要素を取得できる
3. Win32 / UIA の要素情報を表示できる
4. セレクター候補を生成できる
5. ヒット件数を表示できる
6. warningを表示できる
7. treeコマンドを追加する
````

最初から完全な機能を目指さず、MVPとして使える最小構成を先に作る。

---

## 2.2 優先すること

```text
- pip install . でインストールできること
- pyselector inspect が動くこと
- Win32 Backendを優先すること
- UIA Backendも取得できること
- セレクター候補とヒット件数を表示できること
- 出力仕様を安定させること
```

---

## 2.3 初期版で実装しないこと

以下は初期版では実装しない。

```text
- JSON出力
- ファイル出力
- クリップボードコピー
- GUI
- 常駐モード
- クリックや入力などの操作実行
- Playwright / Selenium連携
- pytestコード全体の自動生成
```

---

# 3. 実装フェーズ

実装は以下のフェーズに分ける。

```text
Phase 1: プロジェクト雛形とCLI基盤
Phase 2: カーソル取得とカウントダウン
Phase 3: データモデル定義
Phase 4: Win32 Backend実装
Phase 5: UIA Backend実装
Phase 6: 出力整形
Phase 7: セレクター候補生成
Phase 8: ヒット件数評価
Phase 9: warning判定
Phase 10: コードスニペット生成
Phase 11: inspect統合
Phase 12: treeコマンド実装
Phase 13: インストール・README整備
```

---

# 4. Phase 1: プロジェクト雛形とCLI基盤

## TASK-001 プロジェクト構成を作成する

### 目的

pyselectorの基本ディレクトリ構成を作成する。

### 対象ファイル

```text
pyselector/
  __init__.py
  cli.py
  countdown.py
  cursor.py

  backends/
    __init__.py
    base.py
    win32_inspector.py
    uia_inspector.py

  model/
    __init__.py
    rectangle.py
    element_info.py
    target_window.py
    hierarchy.py
    selector_candidate.py
    inspection_result.py

  selector/
    __init__.py
    generator.py
    win32_generator.py
    uia_generator.py
    evaluator.py
    warning.py
    snippet.py

  output/
    __init__.py
    text_output.py
    formatters.py

  utils/
    __init__.py
    process.py
    errors.py
    logging.py
    text.py
    timing.py

pyproject.toml
README.md
```

### 完了条件

* 上記ディレクトリと空ファイルが作成されている
* Pythonパッケージとしてimportできる
* `pyselector/__init__.py` が存在する

---

## TASK-002 pyproject.tomlを作成する

### 目的

`pip install .` でCLIとしてインストールできるようにする。

### 対象ファイル

```text
pyproject.toml
```

### 実装内容

* project metadataを定義する
* Pythonバージョンを指定する
* pywinauto依存を定義する
* console scriptを定義する

### 例

```toml
[project]
name = "pyselector"
version = "0.1.0"
description = "A CLI tool to inspect Windows UI elements and generate pywinauto selector candidates."
requires-python = ">=3.9"
dependencies = [
    "pywinauto>=0.6.8"
]

[project.scripts]
pyselector = "pyselector.cli:main"
```

### 完了条件

以下が実行できる。

```bash
pip install -e .
pyselector --help
```

---

## TASK-003 CLI引数解析を実装する

### 目的

`inspect`, `tree`, `version` サブコマンドを受け付けるCLIを実装する。

### 対象ファイル

```text
pyselector/cli.py
```

### 実装内容

* `argparse` を使ってCLIを実装する
* サブコマンドを定義する
* サブコマンド省略時は `inspect` として扱う
* 引数エラー時は終了コード `10` を返す

### コマンド

```text
pyselector
pyselector inspect
pyselector tree
pyselector version
```

### inspectオプション

```text
--delay
--backend
--scope
--detail
--verbose
--timeout
--max-items
--only-visible
--include-hidden
```

### treeオプション

```text
--cursor
--window-title
--title-re
--backend
--depth
--max-items
--only-visible
--include-hidden
--detail
--delay
```

### 完了条件

以下が実行できる。

```bash
pyselector --help
pyselector inspect --help
pyselector tree --help
pyselector version
```

---

## TASK-004 終了コード制御を実装する

### 目的

エラー種別に応じて終了コードを返す。

### 対象ファイル

```text
pyselector/cli.py
pyselector/utils/errors.py
```

### 実装内容

以下の終了コードを扱う。

| 終了コード | 意味                 |
| ----: | ------------------ |
|   `0` | 正常終了               |
|   `1` | カーソル下の要素を取得できない    |
|   `2` | 対象ウィンドウを特定できない     |
|   `3` | UIA Backendで取得失敗   |
|   `4` | Win32 Backendで取得失敗 |
|   `5` | セレクター候補の評価に失敗      |
|  `10` | 引数エラー              |
| `100` | 予期しないエラー           |
| `130` | Ctrl+Cによる中断        |

### 完了条件

* Ctrl+Cで `130` が返る
* 引数エラーで `10` が返る
* 正常終了時に `0` が返る

---

# 5. Phase 2: カーソル取得とカウントダウン

## TASK-005 カウントダウン処理を実装する

### 目的

`--delay` で指定した秒数だけ待機し、カウントダウンを表示する。

### 対象ファイル

```text
pyselector/countdown.py
```

### 実装内容

```python
def wait_with_countdown(delay: int) -> None:
    ...
```

### 仕様

* `delay > 0` の場合はカウントダウンを表示する
* `delay = 0` の場合は即時復帰する
* 負数はCLI側で引数エラーとする
* Ctrl+Cは上位へ送出する

### 完了条件

```bash
pyselector inspect --delay 3
```

実行時に以下のような表示が出る。

```text
[INFO] 3秒後にカーソル下のUI要素を取得します
[INFO] 3...
[INFO] 2...
[INFO] 1...
```

---

## TASK-006 カーソル座標取得を実装する

### 目的

現在のマウスカーソル位置を取得する。

### 対象ファイル

```text
pyselector/cursor.py
pyselector/model/inspection_result.py
```

### 実装内容

```python
def get_cursor_position() -> CursorPosition:
    ...
```

### 方針

* Windows APIまたはpywinautoでカーソル位置を取得する
* X/Y座標を `CursorPosition` として返す

### 完了条件

`pyselector inspect --delay 0` 実行時に以下が表示できる。

```text
[INFO] cursor position: X=..., Y=...
```

---

# 6. Phase 3: データモデル定義

## TASK-007 RectangleInfoを実装する

### 目的

UI要素の矩形情報を共通モデルで扱う。

### 対象ファイル

```text
pyselector/model/rectangle.py
```

### 実装内容

```python
@dataclass
class RectangleInfo:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        ...

    @property
    def height(self) -> int:
        ...
```

### 完了条件

* widthが `right - left` で返る
* heightが `bottom - top` で返る

---

## TASK-008 ElementInfoを実装する

### 目的

バックエンドから取得したUI要素情報を共通形式で保持する。

### 対象ファイル

```text
pyselector/model/element_info.py
```

### 実装内容

```python
@dataclass
class ElementInfo:
    backend: str
    window_text: str | None
    control_type: str | None
    automation_id: str | None
    class_name: str | None
    friendly_class_name: str | None
    control_id: int | None
    children_count: int | None
    depth: int | None
    rectangle: RectangleInfo | None
    is_visible: bool | None
    is_enabled: bool | None
    handle: int | None
    process_id: int | None
    process_name: str | None
```

### 完了条件

* Win32 / UIA の両方で同じモデルを使える
* pywinauto wrapperを保持しない

---

## TASK-009 TargetWindowInfoを実装する

### 目的

対象要素が所属するトップレベルウィンドウ情報を保持する。

### 対象ファイル

```text
pyselector/model/target_window.py
```

### 実装内容

```python
@dataclass
class TargetWindowInfo:
    backend: str
    title: str | None
    class_name: str | None
    process_name: str | None
    process_id: int | None
    handle: int | None
```

### 完了条件

* Win32 / UIA バックエンドごとにトップレベルウィンドウ情報を保持できる

---

## TASK-010 HierarchyNodeを実装する

### 目的

親階層・ツリー表示用のノード情報を保持する。

### 対象ファイル

```text
pyselector/model/hierarchy.py
```

### 実装内容

```python
@dataclass
class HierarchyNode:
    depth: int
    window_text: str | None
    control_type: str | None
    automation_id: str | None
    class_name: str | None
    control_id: int | None
    handle: int | None
    rectangle: RectangleInfo | None
```

### 完了条件

* inspectの親階層表示に使える
* treeのツリー表示に使える

---

## TASK-011 SelectorCandidateを実装する

### 目的

生成したセレクター候補を保持する。

### 対象ファイル

```text
pyselector/model/selector_candidate.py
```

### 実装内容

```python
@dataclass
class SelectorCandidate:
    backend: str
    selector_text: str
    selector_kind: str
    condition: dict
    uses_title: bool = False
    uses_title_re: bool = False
    uses_class_name: bool = False
    uses_control_id: bool = False
    uses_auto_id: bool = False
    uses_control_type: bool = False
    uses_found_index: bool = False
    uses_handle: bool = False
    display_order: int = 0
```

### 完了条件

* 表示用の `selector_text` を保持できる
* 評価用の `condition` を保持できる
* warning判定用のフラグを保持できる

---

## TASK-012 SelectorEvaluationを実装する

### 目的

セレクター候補の評価結果を保持する。

### 対象ファイル

```text
pyselector/model/selector_candidate.py
```

### 実装内容

```python
@dataclass
class SelectorEvaluation:
    candidate: SelectorCandidate
    hits: int | None
    status: str
    warnings: list[str]
    reached_limit: bool = False
    error_message: str | None = None
```

### status

```text
success
error
timeout
```

### 完了条件

* hits数を保持できる
* Error / Timeout状態を表現できる
* warningを保持できる

---

## TASK-013 InspectionResult系モデルを実装する

### 目的

inspect全体の結果を保持する。

### 対象ファイル

```text
pyselector/model/inspection_result.py
```

### 実装内容

```python
@dataclass
class CursorPosition:
    x: int
    y: int

@dataclass
class BackendInspection:
    backend: str
    element: ElementInfo | None
    target_window: TargetWindowInfo | None
    hierarchy: list[HierarchyNode]
    candidates: list[SelectorCandidate]
    evaluations: list[SelectorEvaluation]
    code_snippet: str | None
    status: str
    message: str | None = None

@dataclass
class InspectionResult:
    cursor_position: CursorPosition
    win32: BackendInspection | None
    uia: BackendInspection | None
```

### 完了条件

* inspect結果を1つのオブジェクトとして出力層へ渡せる

---

# 7. Phase 4: Win32 Backend実装

## TASK-014 Backend共通インターフェースを実装する

### 目的

Win32 / UIA の処理を同じ呼び出し形で扱えるようにする。

### 対象ファイル

```text
pyselector/backends/base.py
```

### 実装内容

```python
class BackendInspector:
    backend_name: str

    def element_from_point(self, x: int, y: int) -> ElementInfo:
        ...

    def get_target_window(self, element: ElementInfo) -> TargetWindowInfo:
        ...

    def get_hierarchy(self, element: ElementInfo) -> list[HierarchyNode]:
        ...

    def find_elements(self, scope, condition: dict) -> list[ElementInfo]:
        ...
```

### 完了条件

* Win32Inspector / UiaInspectorが同じメソッドを提供する

---

## TASK-015 Win32でカーソル下要素を取得する

### 目的

Win32 Backendでカーソル座標からUI要素を取得する。

### 対象ファイル

```text
pyselector/backends/win32_inspector.py
```

### 実装内容

```python
class Win32Inspector:
    backend_name = "win32"

    def element_from_point(self, x: int, y: int) -> ElementInfo:
        ...
```

### 方針

* `Desktop(backend="win32")` または既存ElementFinderのロジックを使用する
* 取得したwrapperから `ElementInfo` を生成する
* 取得できない属性は `None` にする

### 完了条件

`pyselector inspect --backend win32` で以下が表示できる。

```text
[Win32 Backend]
  window_text: ...
  class_name: ...
  handle: ...
```

---

## TASK-016 Win32要素属性をElementInfoへ変換する

### 目的

Win32 wrapperから共通モデルへ変換する。

### 対象ファイル

```text
pyselector/backends/win32_inspector.py
```

### 取得対象

```text
window_text
class_name
friendly_class_name
control_id
children_count
depth
rectangle
is_visible
is_enabled
handle
process_id
process_name
```

### 完了条件

* 取得できる項目はElementInfoへ設定される
* 取得できない項目はNoneになる
* 例外が発生しても全体が落ちない

---

## TASK-017 Win32対象ウィンドウ取得を実装する

### 目的

対象要素が所属するトップレベルウィンドウを取得する。

### 対象ファイル

```text
pyselector/backends/win32_inspector.py
```

### 実装内容

```python
def get_target_window(self, element: ElementInfo) -> TargetWindowInfo:
    ...
```

### 完了条件

以下が表示できる。

```text
[Target Window]
  title: ...
  class_name: ...
  process_name: ...
  process_id: ...
  handle: ...
```

---

## TASK-018 Win32親階層取得を実装する

### 目的

対象要素までの親階層を取得する。

### 対象ファイル

```text
pyselector/backends/win32_inspector.py
```

### 実装内容

```python
def get_hierarchy(self, element: ElementInfo) -> list[HierarchyNode]:
    ...
```

### 完了条件

以下のような表示ができる。

```text
[Hierarchy - Win32]
  0 Window  "..."
  1 Pane    "..."
  2 Button  "OK"  class_name="Button" control_id=1
```

---

# 8. Phase 5: UIA Backend実装

## TASK-019 UIAでカーソル下要素を取得する

### 目的

UIA Backendでカーソル座標からUI要素を取得する。

### 対象ファイル

```text
pyselector/backends/uia_inspector.py
```

### 実装内容

```python
class UiaInspector:
    backend_name = "uia"

    def element_from_point(self, x: int, y: int) -> ElementInfo:
        ...
```

### 完了条件

`pyselector inspect --backend uia` で以下が表示できる。

```text
[UIA Backend]
  window_text: ...
  control_type: ...
  automation_id: ...
```

---

## TASK-020 UIA要素属性をElementInfoへ変換する

### 目的

UIA wrapperから共通モデルへ変換する。

### 対象ファイル

```text
pyselector/backends/uia_inspector.py
```

### 取得対象

```text
window_text
control_type
automation_id
class_name
friendly_class_name
children_count
depth
rectangle
is_visible
is_enabled
handle
process_id
process_name
```

### 完了条件

* UIAの主要属性がElementInfoへ設定される
* 取得できない項目はNoneになる
* UIA固有の例外で全体が落ちない

---

## TASK-021 UIA対象ウィンドウ取得を実装する

### 目的

UIA要素が所属するトップレベルウィンドウを取得する。

### 対象ファイル

```text
pyselector/backends/uia_inspector.py
```

### 実装内容

```python
def get_target_window(self, element: ElementInfo) -> TargetWindowInfo:
    ...
```

### 完了条件

UIA BackendでもTarget Window情報を表示できる。

---

## TASK-022 UIA親階層取得を実装する

### 目的

UIA要素までの親階層を取得する。

### 対象ファイル

```text
pyselector/backends/uia_inspector.py
```

### 実装内容

```python
def get_hierarchy(self, element: ElementInfo) -> list[HierarchyNode]:
    ...
```

### 完了条件

以下のような表示ができる。

```text
[Hierarchy - UIA]
  0 Window  "..."
  1 Pane    "..."
  2 Button  "OK"  auto_id="..." control_type="Button"
```

---

# 9. Phase 6: 出力整形

## TASK-023 値フォーマッタを実装する

### 目的

None、handle、rectangleなどの表示を統一する。

### 対象ファイル

```text
pyselector/output/formatters.py
```

### 実装内容

```python
format_value(value) -> str
format_handle(handle: int | None) -> str
format_rectangle(rect: RectangleInfo | None) -> str
quote_text(value: str | None) -> str
```

### 完了条件

以下の表示が統一される。

```text
(None)
0x00123456
L=100, T=200, R=300, B=400, W=200, H=200
```

---

## TASK-024 Backend要素情報の出力を実装する

### 目的

ElementInfoをテキスト形式で表示する。

### 対象ファイル

```text
pyselector/output/text_output.py
```

### 実装内容

```python
format_backend_element(inspection: BackendInspection) -> str
```

### 完了条件

以下のセクションが表示できる。

```text
[Win32 Backend]
...
[UIA Backend]
...
```

---

## TASK-025 Target Window出力を実装する

### 目的

TargetWindowInfoをテキスト形式で表示する。

### 対象ファイル

```text
pyselector/output/text_output.py
```

### 実装内容

```python
format_target_window(target_window: TargetWindowInfo) -> str
```

### 完了条件

以下の表示ができる。

```text
[Target Window]
  title: ...
  class_name: ...
  process_name: ...
  process_id: ...
  handle: ...
```

---

## TASK-026 Hierarchy出力を実装する

### 目的

HierarchyNodeのリストをテキスト形式で表示する。

### 対象ファイル

```text
pyselector/output/text_output.py
```

### 実装内容

```python
format_hierarchy(backend: str, nodes: list[HierarchyNode], detail: bool) -> str
```

### 完了条件

以下の表示ができる。

```text
[Hierarchy - UIA]
  0 Window  "電卓"
  1 Pane    ""
  2 Button  "1"  auto_id="num1Button"
```

---

# 10. Phase 7: セレクター候補生成

## TASK-027 文字列ユーティリティを実装する

### 目的

候補生成に必要な文字列処理を提供する。

### 対象ファイル

```text
pyselector/utils/text.py
```

### 実装内容

```python
is_blank(value: str | None) -> bool
escape_python_string(value: str) -> str
escape_regex(value: str) -> str
```

### 完了条件

* Noneや空文字を候補生成から除外できる
* Python文字列として安全に出力できる
* title_re用の正規表現エスケープができる

---

## TASK-028 Win32セレクター候補生成を実装する

### 目的

Win32 Backend向けのセレクター候補を生成する。

### 対象ファイル

```text
pyselector/selector/win32_generator.py
```

### 生成候補

```text
1. control_id + class_name
2. title + class_name
3. control_id
4. class_name + found_index
5. title + found_index
6. class_name
7. title
8. handle
```

### 完了条件

ElementInfoから以下のような候補を生成できる。

```text
dlg.child_window(control_id=1, class_name="Button")
dlg.child_window(title="OK", class_name="Button")
dlg.child_window(control_id=1)
dlg.child_window(class_name="Button")
dlg.child_window(title="OK")
dlg.child_window(handle=0x00123456)
```

---

## TASK-029 UIAセレクター候補生成を実装する

### 目的

UIA Backend向けのセレクター候補を生成する。

### 対象ファイル

```text
pyselector/selector/uia_generator.py
```

### 生成候補

```text
1. auto_id + control_type
2. title + auto_id + control_type
3. auto_id
4. title + control_type
5. title_re + control_type
6. control_type + found_index
7. title
```

### 完了条件

ElementInfoから以下のような候補を生成できる。

```text
dlg.child_window(auto_id="num1Button", control_type="Button")
dlg.child_window(title="1", auto_id="num1Button", control_type="Button")
dlg.child_window(auto_id="num1Button")
dlg.child_window(title="1", control_type="Button")
dlg.child_window(title_re="^1$", control_type="Button")
dlg.child_window(title="1")
```

---

## TASK-030 候補重複排除を実装する

### 目的

同一候補の重複表示を避ける。

### 対象ファイル

```text
pyselector/selector/generator.py
```

### 実装内容

```python
deduplicate_candidates(candidates: list[SelectorCandidate]) -> list[SelectorCandidate]
```

### 重複条件

以下が一致する場合、重複とみなす。

```text
backend
selector_text
```

### 完了条件

同じセレクター候補が複数回表示されない。

---

## TASK-031 候補表示順制御を実装する

### 目的

仕様に沿った順番で候補を表示する。

### 対象ファイル

```text
pyselector/selector/generator.py
```

### 実装内容

```python
sort_candidates(candidates: list[SelectorCandidate]) -> list[SelectorCandidate]
```

### 完了条件

* Win32内では定義済み優先順位順になる
* UIA内では定義済み優先順位順になる
* handle候補は最後になる

---

# 11. Phase 8: ヒット件数評価

## TASK-032 Backend検索処理を実装する

### 目的

SelectorCandidate.conditionをもとに、対象範囲内の一致要素を検索する。

### 対象ファイル

```text
pyselector/backends/win32_inspector.py
pyselector/backends/uia_inspector.py
```

### 実装内容

```python
def find_elements(self, scope, condition: dict) -> list[ElementInfo]:
    ...
```

### 完了条件

以下のようなconditionで一致要素を検索できる。

```python
{"class_name": "Button"}
{"control_id": 1, "class_name": "Button"}
{"auto_id": "num1Button", "control_type": "Button"}
```

---

## TASK-033 ヒット件数評価を実装する

### 目的

各セレクター候補のヒット件数を算出する。

### 対象ファイル

```text
pyselector/selector/evaluator.py
```

### 実装内容

```python
def evaluate_candidates(
    candidates: list[SelectorCandidate],
    inspector,
    scope,
    timeout_sec: int,
    max_items: int | None,
) -> list[SelectorEvaluation]:
    ...
```

### 完了条件

候補ごとに以下が得られる。

```text
hits: 1
hits: 5
hits: (Error)
hits: (Timeout)
```

---

## TASK-034 found_index算出を実装する

### 目的

複数ヒットする属性候補に対し、対象要素のfound_indexを算出する。

### 対象ファイル

```text
pyselector/selector/evaluator.py
pyselector/selector/win32_generator.py
pyselector/selector/uia_generator.py
```

### 方針

対象要素と一致要素一覧を比較し、0始まりのindexを算出する。

### 同一判定

Win32。

```text
1. handle
2. rectangle
3. control_id + class_name + window_text
```

UIA。

```text
1. runtime_id
2. rectangle
3. automation_id + control_type + window_text
```

### 完了条件

以下の候補が必要に応じて生成できる。

```text
dlg.child_window(class_name="Button", found_index=3)
dlg.child_window(control_type="Button", found_index=3)
```

---

# 12. Phase 9: warning判定

## TASK-035 warning判定を実装する

### 目的

候補ごとに必要なwarningを付与する。

### 対象ファイル

```text
pyselector/selector/warning.py
```

### 実装内容

```python
def build_warnings(
    candidate: SelectorCandidate,
    evaluation: SelectorEvaluation,
    element: ElementInfo,
    detail: bool,
) -> list[str]:
    ...
```

### warning条件

```text
hits = 0
hits > 1
found_indexを使用
handleを使用
評価失敗
評価タイムアウト
探索上限到達
対象要素が非表示
対象要素が無効状態
```

### 完了条件

以下のようなwarningが表示できる。

```text
warning: 複数要素にヒットします
warning: found_index は画面構成や表示順の変更に弱い可能性があります
warning: handle はアプリ起動ごとに変わる可能性があります
```

---

## TASK-036 Selector Candidates出力を実装する

### 目的

候補、ヒット数、warningを仕様通りに表示する。

### 対象ファイル

```text
pyselector/output/text_output.py
```

### 実装内容

```python
format_selector_candidates(
    backend: str,
    evaluations: list[SelectorEvaluation],
) -> str
```

### 完了条件

以下の表示ができる。

```text
[Selector Candidates - Win32]

[1] hits: 1
    dlg.child_window(control_id=1, class_name="Button")

[2] hits: 5
    dlg.child_window(class_name="Button")
    warning: 複数要素にヒットします
```

---

# 13. Phase 10: コードスニペット生成

## TASK-037 コードスニペット生成を実装する

### 目的

対象ウィンドウへの接続と対象要素取得の最小コードを表示する。

### 対象ファイル

```text
pyselector/selector/snippet.py
```

### 実装内容

```python
def build_code_snippet(
    backend: str,
    target_window: TargetWindowInfo,
    evaluations: list[SelectorEvaluation],
) -> str:
    ...
```

### 選択ルール

```text
1. hits = 1 かつ warningがない候補
2. hits = 1 かつ warningがfound_indexのみの候補
3. hits = 1 かつ warningがhandleのみの候補
4. 先頭候補
```

### 完了条件

以下のようなコードを表示できる。

```python
from pywinauto import Desktop

dlg = Desktop(backend="win32").window(title="電卓")
target = dlg.child_window(control_id=1, class_name="Button")
```

---

## TASK-038 Code Snippet出力を実装する

### 目的

コードスニペットを出力仕様に沿って表示する。

### 対象ファイル

```text
pyselector/output/text_output.py
```

### 完了条件

以下の表示ができる。

```text
[Code Snippet - Win32]
from pywinauto import Desktop

dlg = Desktop(backend="win32").window(title="電卓")
target = dlg.child_window(control_id=1, class_name="Button")
```

---

# 14. Phase 11: inspect統合

## TASK-039 inspect全体処理を実装する

### 目的

カウントダウンから出力まで、inspectの一連の処理を統合する。

### 対象ファイル

```text
pyselector/cli.py
```

必要に応じて以下を作成してもよい。

```text
pyselector/inspect_runner.py
```

### 処理フロー

```text
1. カウントダウン
2. カーソル座標取得
3. バックエンドごとに要素取得
4. 対象ウィンドウ取得
5. 親階層取得
6. セレクター候補生成
7. ヒット件数評価
8. warning付与
9. コードスニペット生成
10. 出力
11. 終了コード返却
```

### 完了条件

以下が実行できる。

```bash
pyselector inspect
pyselector inspect --backend win32
pyselector inspect --backend uia
pyselector inspect --delay 0
```

---

## TASK-040 片方のバックエンド失敗時の継続処理を実装する

### 目的

`--backend both` で片方が失敗しても、もう片方の結果を表示する。

### 対象ファイル

```text
pyselector/cli.py
pyselector/inspect_runner.py
```

### 完了条件

```text
Win32失敗 + UIA成功 -> 結果表示、exit code 0
Win32成功 + UIA失敗 -> 結果表示、exit code 0
Win32失敗 + UIA失敗 -> exit code 1
```

---

# 15. Phase 12: treeコマンド実装

## TASK-041 tree起点指定の検証を実装する

### 目的

`tree` コマンドの起点指定を検証する。

### 対象ファイル

```text
pyselector/cli.py
```

### 引数エラー条件

```text
--cursor と --window-title を同時に指定した
--cursor と --window-title のどちらも指定していない
```

### 完了条件

不正な起点指定時に終了コード `10` で終了する。

---

## TASK-042 window-title指定で起点ウィンドウを取得する

### 目的

タイトル指定によりトップレベルウィンドウを取得する。

### 対象ファイル

```text
pyselector/backends/win32_inspector.py
pyselector/backends/uia_inspector.py
```

### 実装内容

```python
def find_window_by_title(self, title: str, use_regex: bool) -> ElementInfo:
    ...
```

### 完了条件

以下が実行できる。

```bash
pyselector tree --window-title "電卓"
pyselector tree --window-title ".*電卓.*" --title-re
```

---

## TASK-043 tree探索を実装する

### 目的

起点要素から指定深度まで子要素を探索する。

### 対象ファイル

```text
pyselector/backends/win32_inspector.py
pyselector/backends/uia_inspector.py
```

### 実装内容

```python
def walk_tree(
    self,
    root: ElementInfo,
    depth: int,
    max_items: int,
    only_visible: bool,
) -> tuple[list[HierarchyNode], bool]:
    ...
```

### 完了条件

以下が実行できる。

```bash
pyselector tree --window-title "電卓" --depth 3
pyselector tree --cursor --depth 2
```

---

## TASK-044 tree出力を実装する

### 目的

TreeResultをテキスト表示する。

### 対象ファイル

```text
pyselector/output/text_output.py
```

### 実装内容

```python
format_tree_result(result: TreeResult) -> str
```

### 完了条件

以下のような表示ができる。

```text
[Tree - Win32]
  0 Window  "電卓"  class_name="ApplicationFrameWindow"
  1 Pane    ""      class_name="Windows.UI.Core.CoreWindow"
  2 Button  "OK"    class_name="Button" control_id=1
```

---

# 16. Phase 13: インストール・README整備

## TASK-045 READMEを作成する

### 目的

ツールの概要、インストール方法、基本的な使い方を説明する。

### 対象ファイル

```text
README.md
```

### 記載内容

```text
- ツール概要
- 開発動機
- インストール方法
- 基本コマンド
- inspectの使い方
- treeの使い方
- 出力例
- 注意事項
```

### 完了条件

READMEを読めば、最低限以下が実行できる。

```bash
pip install .
pyselector inspect
pyselector tree --window-title "電卓"
```

---

## TASK-046 docsとの整合性を確認する

### 目的

実装と仕様書のズレを確認する。

### 対象ファイル

```text
docs/
  01_requirements.md
  02_cli_spec.md
  03_output_format.md
  04_selector_generation_spec.md
  05_architecture.md
  06_implementation_tasks.md
```

### 確認観点

```text
- CLIオプションが02_cli_spec.mdと一致している
- 出力形式が03_output_format.mdと一致している
- セレクター生成順が04_selector_generation_spec.mdと一致している
- モジュール構成が05_architecture.mdと大きく乖離していない
- 初期版対象外の機能を実装していない
```

### 完了条件

仕様との差分があれば、実装または文書を修正する。

---

# 17. MVP完了条件

MVPは、以下を満たした時点で完了とする。

```text
- pip install . でインストールできる
- pyselector --help が実行できる
- pyselector inspect が実行できる
- 5秒カウントダウン後にカーソル下要素を取得できる
- Win32 Backendの要素情報を表示できる
- UIA Backendの要素情報を表示できる
- 対象ウィンドウ情報を表示できる
- 親階層を表示できる
- Win32セレクター候補を表示できる
- UIAセレクター候補を表示できる
- 各候補のヒット件数を表示できる
- warningが必要な候補にwarningを表示できる
- handle候補が最後に表示される
- pyselector tree が実行できる
```

---

# 18. 推奨実装順序

実装時は、以下の順で進める。

```text
1. TASK-001 プロジェクト構成を作成する
2. TASK-002 pyproject.tomlを作成する
3. TASK-003 CLI引数解析を実装する
4. TASK-005 カウントダウン処理を実装する
5. TASK-006 カーソル座標取得を実装する
6. TASK-007〜013 データモデルを実装する
7. TASK-015〜018 Win32 Backendを実装する
8. TASK-019〜022 UIA Backendを実装する
9. TASK-023〜026 出力整形を実装する
10. TASK-028〜031 セレクター候補生成を実装する
11. TASK-032〜034 ヒット件数評価を実装する
12. TASK-035〜036 warning表示を実装する
13. TASK-037〜038 コードスニペット生成を実装する
14. TASK-039〜040 inspect全体を統合する
15. TASK-041〜044 treeコマンドを実装する
16. TASK-045 READMEを作成する
17. TASK-046 docsとの整合性を確認する
```

---

# 19. 実装時の注意

## 19.1 仕様外機能を増やさない

便利そうでも、初期版では以下を実装しない。

```text
- --json
- --output
- --copy
- GUI
- 常駐モード
- 操作実行
```

仕様外機能を増やすと、MVPが重くなる。

---

## 19.2 セレクター候補に説明を出しすぎない

候補一覧に通常時のreasonや採用理由は表示しない。

表示するのは以下だけ。

```text
- セレクター候補
- ヒット件数
- warningがある場合のwarning
```

---

## 19.3 Win32を優先する

`--backend both` の場合、候補表示はWin32を先にする。

ただし、UIAでしか取れない要素もあるため、UIAの実装も省略しない。

---

## 19.4 handleを上位にしない

handleは一意になりやすいが、ハードコードには向かない。

そのため、候補一覧では常に最後に表示する。

---

## 19.5 pywinauto wrapperをモデルに保持しない

`ElementInfo` などのモデルには、pywinauto wrapperそのものを保持しない。

理由は以下。

```text
- 出力整形しやすくするため
- セレクター生成ロジックをUI依存から切り離すため
- テストしやすくするため
```

---

## 19.6 表示文字列を再パースしない

ヒット件数評価では、`selector_text` をパースして条件を復元してはならない。

必ず `SelectorCandidate.condition` を使用する。

---

## 19.7 失敗しても部分結果を表示する

Windows UI Automationでは、対象アプリや権限、バックエンドの違いによって取得に失敗することがある。

片方のバックエンドで失敗しても、もう片方で取得できた場合は結果を表示する。

---

# 20. 実装完了後の確認観点

テスト計画書は別途作成しないが、実装完了後は最低限以下を確認する。

```text
- pyselector --help が表示される
- pyselector version が表示される
- pyselector inspect が起動する
- pyselector inspect --delay 0 が即時取得する
- pyselector inspect --backend win32 が動く
- pyselector inspect --backend uia が動く
- pyselector inspect --backend both が動く
- セレクター候補がWin32、UIAの順で表示される
- hitsが表示される
- 複数ヒット時にwarningが表示される
- found_index候補にwarningが表示される
- handle候補が最後に表示される
- handle候補にwarningが表示される
- pyselector tree --cursor が動く
- pyselector tree --window-title "電卓" が動く
```
