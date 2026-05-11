# pyselector

pyselector は、Windows の UI 要素を調査し、pywinauto のセレクター候補を生成する CLI ツールです。

## インストール

```bash
pip install .
```

開発用:

```bash
pip install -e .
```

## アンインストール

`pyselector` コマンドを無効にしたい場合は、インストールした Python 環境で次を実行します。

```bash
pip uninstall pyselector
```

## 基本的な使い方

1. 調査したい Windows アプリを開いておく
2. ターミナルで `pyselector` を実行すると、5秒のカウントダウンが開始される
3. カウントダウン中に、調査したいボタンや入力欄へマウスカーソルを移動する
4. 出力された `[Selector Candidates]` または `[Code Snippet]` を pywinauto のコードにコピーして使う

最短では `pyselector` コマンドだけで使えます。`inspect` モードで実行されます。

```bash
# 基本のコマンド
pyselector

# 上と同じ意味
pyselector inspect
```

## `inspect` モードのオプション

カウントダウン時間を調整したい場合:

```bash
# 即時に取得
pyselector inspect --delay 0

# 10秒後に延長
pyselector inspect --delay 10
```

win32/uia バックエンドいずれか片方だけで調べる場合:

```bash
pyselector inspect --backend win32
pyselector inspect --backend uia
```

デスクトップ全体からヒット数を確認する:
通常は対象ウィンドウ内だけを探索する `--scope window` で実行されます。複数ウィンドウをまたいで候補のヒット数を確認したい場合に `desktop` を使います。

```bash
pyselector inspect --scope desktop
```

非表示要素も含めて調べる:

```bash
pyselector inspect --include-hidden
```

## `inspect` の出力例

たとえば電卓アプリの `1` ボタンにカーソルを合わせて実行すると、次のような情報が表示されます。

```text
[INFO] 座標を決定しました。 X=636, Y=2240

[Target Window]
  title: 電卓
  class_name: ApplicationFrameWindow
  process_name: CalculatorApp.exe
  process_id: 12345
  handle: 0x2E20F46

[Backend]
  [Win32]
    window_text: 電卓
    control_type: (None)
    automation_id: (None)
    class_name: Windows.UI.Core.CoreWindow
    friendly_class_name: Window
    control_id: (None)
    children_count: 0
    depth: 1
    rectangle: L=594, T=1794, R=914, B=2326, W=320, H=532
    is_visible: True
    is_enabled: True
    handle: 0x2E20F46

  [UIA]
    window_text: 1
    control_type: Button
    automation_id: num1Button
    class_name: Button
    friendly_class_name: Button
    control_id: (None)
    children_count: 0
    depth: 6
    rectangle: L=598, T=2218, R=675, B=2269, W=77, H=51
    is_visible: True
    is_enabled: True
    handle: (None)

[Hierarchy]
  [Win32]
    0 ApplicationFrameWindow "電卓"  class_name="ApplicationFrameWindow"
    1 Windows.UI.Core.CoreWindow "電卓"  class_name="Windows.UI.Core.CoreWindow"

  [UIA]
    0 Pane    "デスクトップ 1"  control_type="Pane" class_name="#32769" friendly_class_name="Pane"
    1 Window  "電卓"  control_type="Window" class_name="ApplicationFrameWindow" friendly_class_name="Dialog"
    2 Window  "電卓"  control_type="Window" class_name="Windows.UI.Core.CoreWindow" friendly_class_name="Dialog"
    3 Custom  ""  control_type="Custom" auto_id="NavView" friendly_class_name="Custom"
    4 Group   ""  control_type="Group" class_name="LandmarkTarget" friendly_class_name="GroupBox"
    5 Group   "数字パッド"  control_type="Group" auto_id="NumberPad" class_name="NamedContainerAutomationPeer" friendly_class_name="GroupBox"
    6 Button  "1"  control_type="Button" auto_id="num1Button" class_name="Button"

[Selector Candidates]
  [Win32]
    [1] dlg.child_window(title="電卓", class_name="Windows.UI.Core.CoreWindow")
    [1] dlg.child_window(title="電卓")
    [1] dlg.window(handle=0x2E20F46)
        - warning: handle はアプリ起動ごとに変わる可能性があります

  [UIA]
    [1] dlg.child_window(title="1", control_type="Button")
    [1] dlg.child_window(title="数字パッド", control_type="Group").child_window(title="1", control_type="Button")
    [10+] dlg.child_window(control_type="Button")
        - warning: 複数要素にヒットします

[Code Snippet]
  [Win32]
from pywinauto import Desktop

dlg = Desktop(backend="win32").window(title="電卓")
target = dlg.child_window(class_name="Windows.UI.Core.CoreWindow")
target.wait("visible", timeout=10).click()

  [UIA]
from pywinauto import Desktop

dlg = Desktop(backend="uia").window(title="電卓")
target = dlg.child_window(auto_id="num1Button", control_type="Button")
target.wait("visible", timeout=10).click()
```

### 出力の読み方

- `[Target Window]`: 対象要素が所属するトップレベルウィンドウの情報です。
- `[Backend]`: カーソル下で取得できた UI 要素の属性です。
- `[Hierarchy]`: 対象要素までの親階層です。
- `[Selector Candidates]`: pywinauto で使えるセレクター候補とヒット数です。
- `[Code Snippet]`: 先頭候補を使った最小限の pywinauto コード例です。

Win32 と UIA で取得できる情報は異なることがあります。

Windows 標準アプリや新しい UI では UIA のほうが扱いやすいことがありますが、扱える要素が多くパフォーマンスに問題が生じる場合があるため、可能ならwin32の使用を推奨します。

主に見る場所は `[Selector Candidates]` です。各行の先頭にある `[1]` や `[24]` は、そのセレクター候補が何件の要素にヒットしたかを表します。

- `[1]` は 1 件だけにヒットしているため、比較的使いやすい候補です。
- `[24]` のように複数件ヒットしている候補は、対象以外の要素にも一致する可能性があります。
- `warning:` が表示されている候補は、画面変更やアプリ再起動の影響を受けやすい可能性があります。

上の例では、UIA の次の候補が扱いやすい候補です。

```python
dlg.child_window(auto_id="num1Button", control_type="Button")
```

実際の pywinauto コードでは、`[Code Snippet]` のように使用します。

```python
from pywinauto import Desktop

dlg = Desktop(backend="uia").window(title="電卓")
target = dlg.child_window(auto_id="num1Button", control_type="Button")
target.wait("visible", timeout=10).click()
```

### `tree` モードのオプション

指定したウィンドウの UI ツリーを見る:

```bash
pyselector tree --window-title "電卓"
```

カーソル下の要素を起点に UI ツリーを見る:

```bash
pyselector tree --cursor
```

ツリーの深さを調整する:

```bash
pyselector tree --window-title "電卓" --backend uia --depth 5
```

## `tree` の出力例

```bash
pyselector tree --window-title "電卓" --backend uia --depth 3
```

出力例:

```text
[Tree]
  [UIA]
    0 Window  "電卓" control_type="Window" class_name="ApplicationFrameWindow"
    1 Pane    "" control_type="Pane"
    2 Group   "Number pad" control_type="Group"
    3 Button  "1" control_type="Button" auto_id="num1Button" class_name="Button"
    3 Button  "2" control_type="Button" auto_id="num2Button" class_name="Button"
    3 Button  "3" control_type="Button" auto_id="num3Button" class_name="Button"
```

先頭の数値は、起点からの深さです。`auto_id`、`class_name`、`control_type` などを見ながら、安定して使えそうなセレクター候補を探せます。

表示件数が多すぎる場合:

```bash
pyselector tree --window-title "電卓" --backend uia --depth 2 --max-items 50
```

タイトルの一部や正規表現で探したい場合:

```bash
pyselector tree --window-title "電.*" --title-re --backend uia
```

## 設定

カレントディレクトリに `pyselector_config.json` を置くと、内部で持っているデフォルト値を上書きできます。設定値の優先順位は次のとおりです。

1. コマンドラインで明示した CLI オプション
2. `pyselector_config.json`（`pyselector` コマンド実行時のカレントディレクトリ）
3. 内部デフォルト値

```json
{
  "inspect": {
    "delay": 5,
    "timeout": 5,
    "backend": "both",
    "scope": "window",
    "max_items": null,
    "only_visible": true
  },
  "tree": {
    "delay": 5,
    "backend": "both",
    "depth": 3,
    "max_items": 50,
    "only_visible": true
  },
  "selector": {
    "evaluation_max_items": 10,
    "found_index_trial_count": 3
  }
}
```

別の場所の設定ファイルを使う場合は、環境変数 `PYSELECTOR_CONFIG` にパスを指定できます。

## テスト

pytest を使ってテストを実行します。pytest が未インストールの場合は、先にインストールしてください。

```bash
pip install pytest
python -m pytest
```

`pyproject.toml` でテスト対象は `tests` ディレクトリに設定されています。
