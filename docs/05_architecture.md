# 05_architecture.md

# pyselector アーキテクチャ設計書

## 1. 目的

本書は、pywinauto Selector Inspector CLI の内部アーキテクチャを定義する。

本ツールは、Windowsアプリケーション上のUI要素をカーソル位置から特定し、pywinautoで利用可能なセレクター候補とヒット件数を表示するCLIツールである。

本書では以下を定義する。

- パッケージ構成
- モジュール責務
- 主要データモデル
- inspect処理フロー
- tree処理フロー
- セレクター生成・評価の流れ
- 例外処理方針
- 既存ElementFinderからの流用方針

---

## 2. アーキテクチャ方針

## 2.1 基本方針

本ツールは、CLIアプリケーションとして実装する。

内部構造は、以下の責務に分離する。

```text
- CLI引数の解析
- カウントダウンとカーソル座標取得
- Win32 Backendによる要素取得
- UIA Backendによる要素取得
- 要素情報の正規化
- セレクター候補生成
- セレクター候補のヒット件数評価
- テキスト出力整形
````

責務を分けることで、セレクター生成ロジックや出力整形ロジックを単体でテスト・修正しやすくする。

---

## 2.2 設計上の優先事項

実装では以下を優先する。

```text
- CLIとしてシンプルに使えること
- Win32 Backendを優先すること
- UIA Backendも併用できること
- セレクター生成ロジックを独立させること
- テキスト出力仕様を安定させること
- 取得失敗時も可能な範囲で結果を表示すること
- 既存ElementFinderの再利用可能な処理は流用すること
```

---

## 2.3 初期版で扱わないもの

初期版では以下を実装しない。

```text
- GUI
- 常駐モード
- JSON出力
- ファイル出力
- クリップボードコピー
- クリックや入力などの操作実行
- Playwright / Selenium連携
- pytestコード全体の自動生成
```

---

## 3. パッケージ構成

## 3.1 ディレクトリ構成

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

tests/
  test_selector_win32_generator.py
  test_selector_uia_generator.py
  test_selector_warning.py
  test_text_output.py

pyproject.toml
README.md
docs/
  01_requirements.md
  02_cli_spec.md
  03_output_format.md
  04_selector_generation_spec.md
  05_architecture.md
  06_implementation_tasks.md
```

---

## 3.2 構成方針

パッケージは、以下の層に分ける。

```text
CLI層
  cli.py

入力補助層
  countdown.py
  cursor.py

バックエンド層
  backends/

モデル層
  model/

セレクター層
  selector/

出力層
  output/

共通ユーティリティ層
  utils/
```

依存方向は原則として以下とする。

```text
cli
  -> countdown / cursor
  -> backends
  -> selector
  -> output
  -> model
```

`model` は他の層から参照されるが、他の層へ依存しない。

---

# 4. モジュール責務

## 4.1 `cli.py`

CLIエントリポイント。

### 責務

```text
- コマンドライン引数の解析
- サブコマンドの振り分け
- inspect処理の起動
- tree処理の起動
- version表示
- 終了コード制御
```

### 提供する主な関数

```python
def main() -> int:
    ...
```

### 備考

`pyproject.toml` の console scripts から呼び出される。

```toml
[project.scripts]
pyselector = "pyselector.cli:main"
```

---

## 4.2 `countdown.py`

カウントダウン表示を担当する。

### 責務

```text
- delay秒数の待機
- カウントダウン表示
- Ctrl+C中断の検出
```

### 主な関数

```python
def wait_with_countdown(delay: int) -> None:
    ...
```

### 仕様

* `delay > 0` の場合はカウントダウンを表示する
* `delay = 0` の場合は即時復帰する
* Ctrl+C時は上位へ例外を送出する

---

## 4.3 `cursor.py`

マウスカーソル座標の取得を担当する。

### 責務

```text
- 現在のスクリーン座標を取得する
- x, y座標をモデル化する
```

### 主な関数

```python
def get_cursor_position() -> CursorPosition:
    ...
```

---

## 4.4 `backends/base.py`

バックエンド共通インターフェースを定義する。

### 責務

```text
- Win32 / UIA Inspectorの共通インターフェース定義
- 共通的な戻り値の型を定義
```

### 主なクラス

```python
class BackendInspector:
    backend_name: str

    def element_from_point(self, x: int, y: int) -> ElementInfo:
        ...

    def get_target_window(self, element: ElementInfo) -> TargetWindowInfo:
        ...

    def get_hierarchy(self, element: ElementInfo) -> list[HierarchyNode]:
        ...

    def find_elements(self, scope: SearchScope, condition: SelectorCondition) -> list[ElementInfo]:
        ...
```

実装言語上、抽象基底クラスにしてもよい。

---

## 4.5 `backends/win32_inspector.py`

Win32 Backendによる要素取得を担当する。

### 責務

```text
- カーソル座標からWin32要素を取得する
- Win32要素の属性をElementInfoへ変換する
- トップレベルウィンドウを取得する
- 親階層を取得する
- セレクター評価用に要素検索を行う
```

### 主なクラス

```python
class Win32Inspector:
    backend_name = "win32"
```

### 注意点

Win32では、UIAほど細かい子要素が取得できない場合がある。

その場合は、取得できた範囲の要素情報を返す。
取得できなかった場合も、UIA側の処理まで止めない。

---

## 4.6 `backends/uia_inspector.py`

UIA Backendによる要素取得を担当する。

### 責務

```text
- カーソル座標からUIA要素を取得する
- UIA要素の属性をElementInfoへ変換する
- トップレベルウィンドウを取得する
- 親階層を取得する
- セレクター評価用に要素検索を行う
```

### 主なクラス

```python
class UiaInspector:
    backend_name = "uia"
```

### 注意点

UIAは細かい要素を取得できることがある一方で、探索が重くなる場合がある。

タイムアウトと最大件数制限を考慮する。

---

## 4.7 `model/`

データモデルを定義する。

### 責務

```text
- バックエンド取得結果を共通形式で保持する
- セレクター候補を保持する
- 評価結果を保持する
- 出力層へ渡すデータを構造化する
```

モデルは、pywinautoのwrapperオブジェクトを直接持たない方針とする。
必要な値だけを抽出して保持する。

理由は、出力・セレクター生成・テストで扱いやすくするためである。

---

## 4.8 `selector/generator.py`

セレクター候補生成の統合窓口。

### 責務

```text
- backendに応じてWin32/UIA generatorへ処理を委譲する
- 候補の重複排除を行う
- 表示順を整える
```

### 主な関数

```python
def generate_candidates(element: ElementInfo, context: SelectorContext) -> list[SelectorCandidate]:
    ...
```

---

## 4.9 `selector/win32_generator.py`

Win32向けセレクター候補を生成する。

### 責務

```text
- control_id + class_name候補を生成する
- title + class_name候補を生成する
- control_id候補を生成する
- class_name候補を生成する
- title候補を生成する
- found_index候補を生成する
- handle候補を最後に生成する
```

候補の詳細ルールは `04_selector_generation_spec.md` に従う。

---

## 4.10 `selector/uia_generator.py`

UIA向けセレクター候補を生成する。

### 責務

```text
- auto_id + control_type候補を生成する
- title + auto_id + control_type候補を生成する
- auto_id候補を生成する
- title + control_type候補を生成する
- title_re + control_type候補を生成する
- control_type + found_index候補を生成する
- title候補を生成する
```

候補の詳細ルールは `04_selector_generation_spec.md` に従う。

---

## 4.11 `selector/evaluator.py`

セレクター候補のヒット件数評価を担当する。

### 責務

```text
- 候補ごとに探索条件を作る
- 対象スコープ内で一致要素を検索する
- ヒット件数を返す
- タイムアウトや評価失敗を扱う
```

### 主な関数

```python
def evaluate_candidates(
    candidates: list[SelectorCandidate],
    inspector: BackendInspector,
    scope: SearchScope,
    timeout_sec: int,
    max_items: int | None,
) -> list[SelectorEvaluation]:
    ...
```

---

## 4.12 `selector/warning.py`

warning判定を担当する。

### 責務

```text
- hits = 0 のwarning
- hits > 1 のwarning
- found_index使用時のwarning
- handle使用時のwarning
- 評価失敗時のwarning
- タイムアウト時のwarning
- 探索上限到達時のwarning
- 非表示・無効状態のwarning
```

### 主な関数

```python
def build_warnings(
    candidate: SelectorCandidate,
    evaluation: SelectorEvaluation,
    element: ElementInfo,
    detail: bool,
) -> list[str]:
    ...
```

---

## 4.13 `selector/snippet.py`

コードスニペット生成を担当する。

### 責務

```text
- Desktop(backend=...) の接続コードを生成する
- 候補セレクターを使った target取得コードを生成する
- 操作コードは生成しない
```

### 主な関数

```python
def build_code_snippet(
    backend: str,
    target_window: TargetWindowInfo,
    evaluations: list[SelectorEvaluation],
) -> str:
    ...
```

---

## 4.14 `output/text_output.py`

標準出力用のテキスト整形を担当する。

### 責務

```text
- inspect結果の出力文字列を組み立てる
- tree結果の出力文字列を組み立てる
- セクション順序を制御する
- warning表示を整形する
```

出力仕様は `03_output_format.md` に従う。

---

## 4.15 `output/formatters.py`

値の表示整形を担当する。

### 責務

```text
- Noneを(None)へ変換する
- 例外値を(Error)へ変換する
- rectangleをL/T/R/B/W/H形式へ変換する
- handleを16進数表記へ変換する
- 文字列を引用符付きで表示する
```

---

## 4.16 `utils/`

共通処理を提供する。

### `utils/process.py`

```text
- process_idからprocess_nameを取得する
- プロセス情報取得失敗時のフォールバックを提供する
```

### `utils/errors.py`

```text
- ツール固有例外を定義する
- エラーコードと例外を対応づける
```

### `utils/logging.py`

```text
- verboseログの出力を制御する
```

### `utils/text.py`

```text
- Python文字列エスケープ
- 正規表現エスケープ
- 空値判定
```

### `utils/timing.py`

```text
- 処理時間計測
- タイムアウト補助
```

---

# 5. 主要データモデル

## 5.1 `CursorPosition`

```python
@dataclass
class CursorPosition:
    x: int
    y: int
```

---

## 5.2 `RectangleInfo`

```python
@dataclass
class RectangleInfo:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top
```

---

## 5.3 `ElementInfo`

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

### 方針

`ElementInfo` は、pywinauto wrapperそのものを保持しない。

pywinauto wrapperは、バックエンド層内部でのみ扱う。

---

## 5.4 `TargetWindowInfo`

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

---

## 5.5 `HierarchyNode`

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

---

## 5.6 `SelectorCandidate`

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

### `selector_text`

表示用のpywinautoセレクター文字列。

例。

```python
dlg.child_window(control_id=1, class_name="Button")
```

### `condition`

ヒット件数評価に使用する内部条件。

表示文字列を再パースしないために保持する。

例。

```python
{
    "control_id": 1,
    "class_name": "Button"
}
```

---

## 5.7 `SelectorEvaluation`

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

---

## 5.8 `BackendInspection`

バックエンド単位のinspect結果。

```python
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
```

---

## 5.9 `InspectionResult`

inspect全体の結果。

```python
@dataclass
class InspectionResult:
    cursor_position: CursorPosition
    win32: BackendInspection | None
    uia: BackendInspection | None
```

---

## 5.10 `TreeResult`

treeコマンドの結果。

```python
@dataclass
class TreeResult:
    backend: str
    root: ElementInfo | None
    nodes: list[HierarchyNode]
    reached_limit: bool
    status: str
    message: str | None = None
```

---

# 6. inspect 処理フロー

## 6.1 全体フロー

```text
1. CLI引数を解析する
2. delay秒数だけカウントダウンする
3. カーソル座標を取得する
4. 指定バックエンドを決定する
5. バックエンドごとに要素取得を行う
6. 対象ウィンドウ情報を取得する
7. 親階層を取得する
8. セレクター候補を生成する
9. セレクター候補のヒット件数を評価する
10. warningを付与する
11. コードスニペットを生成する
12. テキスト出力を生成する
13. 終了コードを返す
```

---

## 6.2 疑似コード

```python
def run_inspect(args) -> int:
    wait_with_countdown(args.delay)

    cursor = get_cursor_position()

    requested_backends = resolve_backends(args.backend)

    inspections = []

    for backend in requested_backends:
        inspector = create_inspector(backend)

        try:
            element = inspector.element_from_point(cursor.x, cursor.y)
            target_window = inspector.get_target_window(element)
            hierarchy = inspector.get_hierarchy(element)

            context = SelectorContext(
                scope=args.scope,
                target_window=target_window,
                only_visible=args.only_visible,
            )

            candidates = generate_candidates(element, context)

            evaluations = evaluate_candidates(
                candidates=candidates,
                inspector=inspector,
                scope=context.scope,
                timeout_sec=args.timeout,
                max_items=args.max_items,
            )

            evaluations = attach_warnings(
                evaluations=evaluations,
                element=element,
                detail=args.detail,
            )

            snippet = build_code_snippet(
                backend=backend,
                target_window=target_window,
                evaluations=evaluations,
            )

            inspections.append(
                BackendInspection(
                    backend=backend,
                    element=element,
                    target_window=target_window,
                    hierarchy=hierarchy,
                    candidates=candidates,
                    evaluations=evaluations,
                    code_snippet=snippet,
                    status="success",
                )
            )

        except BackendError as e:
            inspections.append(
                BackendInspection(
                    backend=backend,
                    element=None,
                    target_window=None,
                    hierarchy=[],
                    candidates=[],
                    evaluations=[],
                    code_snippet=None,
                    status="failed",
                    message=str(e),
                )
            )

    result = InspectionResult(
        cursor_position=cursor,
        win32=find_backend(inspections, "win32"),
        uia=find_backend(inspections, "uia"),
    )

    print(format_inspection_result(result))

    return resolve_exit_code(result)
```

---

## 6.3 バックエンド失敗時の扱い

`--backend both` の場合、片方のバックエンドで失敗しても、もう片方が成功していれば正常終了とする。

```text
Win32失敗 + UIA成功 -> exit code 0
Win32成功 + UIA失敗 -> exit code 0
Win32失敗 + UIA失敗 -> exit code 1
```

`--backend win32` または `--backend uia` の場合、指定バックエンドが失敗したら異常終了とする。

---

# 7. tree 処理フロー

## 7.1 全体フロー

```text
1. CLI引数を解析する
2. 起点指定を検証する
3. 使用バックエンドを決定する
4. 起点要素を取得する
   - --cursor の場合はカウントダウン後のカーソル下要素
   - --window-title の場合はタイトル一致ウィンドウ
5. 起点要素配下をdepthまで探索する
6. max-itemsに達した場合は探索を打ち切る
7. テキスト出力を生成する
8. 終了コードを返す
```

---

## 7.2 疑似コード

```python
def run_tree(args) -> int:
    inspector = create_inspector(args.backend)

    if args.cursor:
        wait_with_countdown(args.delay)
        cursor = get_cursor_position()
        root = inspector.element_from_point(cursor.x, cursor.y)
    else:
        root = inspector.find_window_by_title(
            title=args.window_title,
            use_regex=args.title_re,
        )

    nodes, reached_limit = inspector.walk_tree(
        root=root,
        depth=args.depth,
        max_items=args.max_items,
        only_visible=args.only_visible,
    )

    result = TreeResult(
        backend=args.backend,
        root=root,
        nodes=nodes,
        reached_limit=reached_limit,
        status="success",
    )

    print(format_tree_result(result))

    return 0
```

---

# 8. セレクター生成・評価フロー

## 8.1 生成から表示までの流れ

```text
1. ElementInfoを受け取る
2. 空値を除外する
3. バックエンド別の候補生成ルールを適用する
4. found_index候補を必要に応じて生成する
5. handle候補を最後に追加する
6. 重複候補を除外する
7. display_order順に並べる
8. 各候補のヒット件数を評価する
9. warningを付与する
10. テキスト出力する
```

---

## 8.2 Win32候補生成の流れ

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

---

## 8.3 UIA候補生成の流れ

```text
1. auto_id + control_type
2. title + auto_id + control_type
3. auto_id
4. title + control_type
5. title_re + control_type
6. control_type + found_index
7. title
```

---

## 8.4 ヒット件数評価の流れ

```text
1. SelectorCandidate.condition を取得する
2. scopeに応じて探索ルートを決定する
3. バックエンドに一致要素検索を依頼する
4. 件数を数える
5. 成功、失敗、タイムアウトを SelectorEvaluation に格納する
```

表示文字列 `selector_text` をパースして評価条件を復元してはならない。
評価には `SelectorCandidate.condition` を使う。

---

# 9. 例外処理方針

## 9.1 例外分類

内部例外は、おおまかに以下へ分類する。

```text
ArgumentError
  引数エラー

CursorError
  カーソル座標取得エラー

BackendError
  バックエンド共通エラー

ElementNotFoundError
  対象要素取得失敗

TargetWindowNotFoundError
  対象ウィンドウ取得失敗

SelectorGenerationError
  セレクター候補生成エラー

SelectorEvaluationError
  セレクター評価エラー

SelectorEvaluationTimeout
  セレクター評価タイムアウト

UnexpectedError
  予期しないエラー
```

---

## 9.2 終了コードとの対応

| 例外                          | 終了コード |
| --------------------------- | ----: |
| `ElementNotFoundError`      |   `1` |
| `TargetWindowNotFoundError` |   `2` |
| UIA取得失敗                     |   `3` |
| Win32取得失敗                   |   `4` |
| `SelectorEvaluationError`   |   `5` |
| `ArgumentError`             |  `10` |
| `KeyboardInterrupt`         | `130` |
| その他                         | `100` |

ただし、`--backend both` で片方のバックエンドだけ失敗した場合は、もう片方が成功していれば終了コード `0` とする。

---

## 9.3 例外を握りつぶさない

内部的に例外を補足する場合も、最低限以下を保持する。

```text
- 発生箇所
- バックエンド
- エラー概要
```

`--verbose` 指定時は、詳細な例外情報を表示してよい。

---

# 10. タイムアウト方針

## 10.1 対象処理

タイムアウト対象は以下。

```text
- カーソル下要素取得
- 親階層取得
- ツリー探索
- セレクター候補のヒット件数評価
```

## 10.2 タイムアウト時の扱い

可能な範囲で部分結果を表示する。

セレクター評価中にタイムアウトした場合、該当候補は以下のように扱う。

```text
hits: (Timeout)
warning: セレクター評価がタイムアウトしました
```

## 10.3 実装方針

pywinautoやWindows UI Automationの呼び出しは、完全に安全な中断が難しい場合がある。

初期版では、以下のような現実的な対策を優先する。

```text
- 探索範囲を対象ウィンドウ配下に限定する
- max-itemsで探索件数を制限する
- 重い探索を避ける
- backendごとの処理時間を測定する
- timeout超過時は以降の探索を打ち切る
```

---

# 11. 既存ElementFinderからの流用方針

## 11.1 流用候補

既存ElementFinderから、以下の処理は流用候補とする。

```text
- CLI引数処理
- カウントダウン
- カーソル座標取得
- UIA Backendによる要素取得
- Win32 Backendによる要素取得
- 要素属性抽出
- 親階層取得
- 子要素列挙
- 深度制限
- 可視要素フィルタ
- ログ出力
```

---

## 11.2 そのまま流用しないほうがよい部分

以下は、新設計に合わせて作り直す。

```text
- 出力フォーマット
- セレクター候補生成
- セレクター候補のヒット件数評価
- warning判定
- コードスニペット生成
- データモデル
```

理由は、後継版では「要素列挙」ではなく、「セレクター候補とヒット件数の提示」が主目的になるためである。

---

## 11.3 流用時の注意

既存ElementFinderのロジックを流用する場合も、以下を守る。

```text
- pyselector側のデータモデルへ変換する
- 出力仕様は03_output_format.mdに合わせる
- セレクター生成仕様は04_selector_generation_spec.mdに合わせる
- 既存のオプションをそのまま増やしすぎない
```

既存機能を便利だから全部入れると、道具が急に十徳ナイフ化する。
便利ではあるけど、刃が多すぎるナイフはポケットの中で少し怖い。

---

# 12. 依存ライブラリ

## 12.1 必須依存

```text
pywinauto
```

## 12.2 標準ライブラリで対応するもの

以下は可能な限り標準ライブラリで対応する。

```text
argparse
dataclasses
time
re
sys
traceback
typing
```

## 12.3 追加依存の方針

初期版では、依存ライブラリを増やしすぎない。

必要性が明確な場合のみ追加する。

候補。

```text
psutil
```

`psutil` は process_id から process_name を取得する用途で便利だが、必須にするかは実装時に判断する。

---

# 13. インストール構成

## 13.1 `pyproject.toml`

`pip install .` でCLIコマンドを登録する。

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

---

## 13.2 開発インストール

```bash
pip install -e .
```

---

## 13.3 通常インストール

```bash
pip install .
```

---

# 14. ログ方針

## 14.1 通常時

通常時は、必要最小限の `[INFO]` のみ表示する。

```text
[INFO] pyselector started
[INFO] 座標を決定しました。 X=636, Y=2240
```

## 14.2 verbose時

`--verbose` 指定時は、以下を表示してよい。

```text
- 使用バックエンド
- 要素取得開始/終了
- 対象ウィンドウ推定結果
- 候補生成件数
- 候補評価件数
- 評価処理時間
- 例外概要
```

## 14.3 warning

セレクター候補に紐づくwarningは、候補一覧の中に表示する。

```text
warning: 複数要素にヒットします
```

処理全体に関する警告は `[WARN]` として表示してよい。

```text
[WARN] Win32 Backendではカーソル下の要素を取得できませんでした。
```

---

# 15. 実装時の境界

## 15.1 バックエンド層で行うこと

```text
- pywinauto wrapperを扱う
- Windows UIから値を取得する
- ElementInfoへ変換する
- 要素検索を実行する
```

---

## 15.2 セレクター層で行うこと

```text
- ElementInfoから候補を生成する
- 候補のヒット件数を評価する
- warningを判定する
- コードスニペットを生成する
```

---

## 15.3 出力層で行うこと

```text
- InspectionResultを文字列に変換する
- 表示順を制御する
- NoneやErrorの表示を整える
```

---

## 15.4 CLI層で行わないこと

CLI層には、以下のロジックを直接書かない。

```text
- pywinauto wrapper操作
- セレクター生成ルール
- warning判定
- 出力文字列の細かい整形
```

CLI層は、入力を受け取り、処理を呼び出し、終了コードを返すだけに留める。

---

# 16. 実装順序の推奨

実装は以下の順で進める。

```text
1. パッケージ雛形作成
2. CLI引数解析
3. カウントダウンとカーソル座標取得
4. Win32 Backendの要素取得
5. UIA Backendの要素取得
6. ElementInfoへの変換
7. TargetWindowInfoとHierarchy取得
8. Win32セレクター候補生成
9. UIAセレクター候補生成
10. ヒット件数評価
11. warning判定
12. テキスト出力
13. treeコマンド
14. pyproject.toml整備
```

---

# 17. アーキテクチャ上の注意点

## 17.1 pywinauto wrapperを外へ漏らさない

pywinauto wrapperはバックエンド層内に閉じ込める。

他の層では `ElementInfo` や `SelectorCandidate` を扱う。

これにより、セレクター生成・出力整形をUIに依存せずに扱いやすくする。

---

## 17.2 バックエンドごとの差異を無理に統合しない

Win32とUIAでは、取得できる要素、属性、階層が異なる。

本ツールでは差異を無理に吸収せず、バックエンドごとに表示する。

---

## 17.3 表示文字列から条件を復元しない

`selector_text` は表示用である。

ヒット件数評価では、必ず `SelectorCandidate.condition` を使う。

---

## 17.4 handleを優先しない

handleは一意になりやすいが、ハードコードには向かない。

そのため、候補生成では常に最後にする。

---

## 17.5 部分結果を許容する

Windows UI Automationでは、環境や対象アプリによって取得に失敗することがある。

片方のバックエンドで失敗しても、もう片方で取得できた場合は結果を表示する。
