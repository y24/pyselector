# pyselector

```
                       _           _                       _ _ 
  _ __  _   _ ___  ___| | ___  ___| |_ ___  _ __       ___| (_)
 | '_ \| | | / __|/ _ \ |/ _ \/ __| __/ _ \| '__|____ / __| | |
 | |_) | |_| \__ \  __/ |  __/ (__| || (_) | | |_____| (__| | |
 | .__/ \__, |___/\___|_|\___|\___|\__\___/|_|        \___|_|_|
 |_|    |___/                                                  
```

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
2. ターミナルで `pyselector` を実行すると、画面全体に半透明オーバーレイが表示される
3. 調査したいボタンや入力欄を左クリックする
4. 出力された `[Selector Candidates]` または `[Code Snippet]` を pywinauto のコードにコピーして使う

最短では `pyselector` コマンドだけで使えます。`inspect` モードで実行されます。

```bash
# 基本のコマンド
pyselector

# 上と同じ意味
pyselector inspect
```

## AI エージェント向けの使い方

`inspect` はオーバーレイのクリック、`tree --cursor` はマウス位置を前提としているため、AI エージェントはそのままでは使えません。エージェント向けには、人の操作を一切必要としない次のコマンドを用意しています。

| コマンド | 用途 |
| --- | --- |
| `pyselector windows` | 開いているウィンドウと handle の一覧 |
| `pyselector find` | ウィンドウ内の要素を条件で絞り込み検索 |
| `pyselector inspect --at X,Y` | 座標を指定して要素を調査（クリック不要） |
| `pyselector inspect --handle 0x...` | ウィンドウ自身を調査 |
| `pyselector tree --window-handle 0x...` | タイトルに依存せずツリーを取得 |
| `pyselector act` | 要素を操作する（既定で無効。後述） |
| `pyselector diff` | 2 つのツリー出力を比較する |

外側から内側へ絞り込むのが基本の流れです。

```bash
# 1. 対象ウィンドウと handle を見つける
pyselector windows --json

# 2. そのウィンドウの規模を掴む（全ノードではなく件数の集計）
pyselector tree --json --window-handle 0x2E20F46 --summary

# 3. 要素を絞り込む
pyselector find --json --window-handle 0x2E20F46 --control-type Button

# 4. セレクター候補まで確定させる
pyselector find --json --window-handle 0x2E20F46 --text "保存" --with-selectors

# 5. 単一要素を完全に評価したいときだけ
pyselector inspect --json --at 636,2240
```

`find` の各一致要素には要素矩形の中心座標 `point` が含まれます。これはそのまま `inspect --at X,Y` に渡せます。

### `windows`

```bash
pyselector windows --json
pyselector windows --json --title "電卓"
pyselector windows --json --process notepad.exe
pyselector windows --json --pid 12345
```

既定ではタイトルを持つウィンドウだけを表示します。ヘルパーウィンドウも含めたい場合は `--include-untitled` を付けます。

### `find`

`--window-handle` / `--window-title` / `--at` のいずれか 1 つで探索の起点を指定します。

```bash
pyselector find --json --window-handle 0x2E20F46 --control-type Button
pyselector find --json --window-handle 0x2E20F46 --auto-id num1Button --with-selectors
pyselector find --json --window-title "メモ帳" --class-name Edit --backend win32
pyselector find --json --at 636,2240 --depth 2
```

絞り込み条件は AND で結合されます。

| オプション | 一致条件 |
| --- | --- |
| `--text` | `window_text` の部分一致（大文字小文字を区別しない） |
| `--text-re` | `window_text` の正規表現一致 |
| `--auto-id` | `automation_id` の完全一致 |
| `--control-type` | `control_type` の一致（大文字小文字を区別しない） |
| `--class-name` | `class_name` の完全一致 |
| `--enabled-only` | 有効な要素のみ |

`--with-selectors` を付けると、先頭 `--selector-limit` 件（既定 3 件）についてセレクター候補の生成と評価まで行います。評価は重い処理のため、上限を上げるより条件を絞ることを推奨します。

出力量の制御には `--limit`（出力件数）、`--max-items`（走査上限）、`--depth`、`--compact` を使います。`reached_limit` は走査が `--max-items` で打ち切られたこと、`truncated` は一致要素が `--limit` で切られたことを表します。

### `act`（UI 操作 / 既定で無効）

`act` は実際のデスクトップを操作します。他のコマンドと違い、取り消せない変更を起こしうるため、**2 段階の明示的な許可**が必要です。

1. `pyselector_config.json` に `{"act": {"allow_actions": true}}` を書く
2. 実行時に `--allow-actions` を付ける

どちらか欠けていれば何も実行せず、終了コード 7（`action_not_allowed`）で終わります。

```bash
# まず --dry-run で対象を確認する（許可は不要）
pyselector act --json --window-handle 0x2E20F46 --auto-id num5Button --click --dry-run

# 実行する
pyselector act --json --window-handle 0x2E20F46 --auto-id num5Button --click --allow-actions
```

操作は次のいずれか 1 つを指定します。

| オプション | 動作 |
| --- | --- |
| `--click` / `--double-click` / `--right-click` | 実際のマウス操作 |
| `--invoke` | UIA の invoke パターン（マウスを動かさない） |
| `--focus` | フォーカスを移す |
| `--set-text TEXT` | 入力欄のテキストを置き換える |
| `--send-keys KEYS` | キー入力を送る（`{ENTER}` などの pywinauto 記法が使えます） |

対象の指定は `find` と同じ条件です。ただし **一意に定まらない限り実行しません**。複数一致した場合は終了コード 6（`ambiguous_target`）で候補を提示するので、条件を絞るか `--index N` で選びます。`--at X,Y` は対象を直接指定するもので、他の条件とは併用できません。

`--diff` を付けると、操作の前後でウィンドウのツリーを取り直して差分を返します。

```bash
pyselector act --window-handle 0x2E20F46 --auto-id TogglePaneButton --click --allow-actions --diff
```

```text
[Act]
  [UIA]
    action: click
    performed: True
    method: click_input
    target: "ナビゲーションを開く"  control_type="Button", auto_id="TogglePaneButton"
    after: "ナビゲーションを閉じる"

[Diff]
  [UIA]
    added: 22, removed: 0, changed: 1, unchanged: 51
    + 6 ListItem "標準 電卓"  auto_id="Standard", class_name="Microsoft.UI.Xaml.Controls.NavigationViewItem"
    + 6 ListItem "関数電卓 電卓"  auto_id="Scientific", class_name="Microsoft.UI.Xaml.Controls.NavigationViewItem"
    ...
```

閉じているメニューの中身のように、その時点では見えていない画面に到達するための手段です。

### `diff`（ツリー出力の比較）

`tree --json` の出力ファイル同士を比較します。

```bash
pyselector tree --json --window-handle 0x2E20F46 --depth 8 > before.json
pyselector tree --json --window-handle 0x2E20F46 --depth 8 > after.json
pyselector diff --json before.json after.json
```

`added` / `removed` / `changed`（属性ごとの before・after）と `summary` を返します。終了コードは、差分があれば 0、完全に同じなら 1 です。`--summary` で取得した出力は比較できません。

### JSON の共通仕様

`--json` の出力には必ず `schema_version` / `command` / `status` が含まれます。

`status` は、いずれかのバックエンドが完走すれば `success` です。**該当なしと失敗は別物**として扱えます。

```text
status=success, matches=[] … 探索は成功したが該当なし（終了コード 1）
status=error                … 探索そのものが失敗
```

失敗時は `error` オブジェクト（`code` / `exit_code` / `message`）が返ります。引数エラーも含め、`--json` 指定時のエラーは標準出力から JSON として読めます。

### エージェント向け Skill のインストール

別のリポジトリで AI エージェントに `pyselector` の使い方を認識させたい場合は、そのリポジトリのルートで次を実行します。

```bash
pyselector install-skills --copilot
pyselector install-skills --claude
```

それぞれ `.github/skills/pyselector-cli/SKILL.md`、`.claude/skills/pyselector-cli/SKILL.md` を作成します。両方を同時に指定することもできます。エージェントがこの skill を読み込むと、上記の探索手順を常に `--json` 付きで使う方法を参照できます。

### 制限

`act` 以外のコマンドは UI を読み取るだけで、アプリの状態を変えません。`act` が唯一の書き込み系コマンドで、上記の 2 段階の許可がなければ何も実行しません。

`act` を有効にしていない場合、メニューを開く・タブを切り替えるといった操作が必要な画面は、あらかじめ人が表示させておく必要があります。

## `inspect` モードのオプション

`inspect` は起動直後にオーバーレイを表示します。左クリックで座標を確定し、Esc でキャンセルできます。

カウントダウン後のマウス位置で調べる場合:

```bash
pyselector inspect --delay 5
```

クリックもカウントダウンもせず、座標やハンドルを直接指定する場合:

```bash
pyselector inspect --at 636,2240
pyselector inspect --handle 0x2E20F46
```

`--at` は物理ピクセルの画面座標です。`find` が返す `point` や `rectangle` と同じ座標系です。`--handle` はウィンドウ自身を対象にします（中心座標を調べると子要素が取れてしまうため）。

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

同じタイトルのウィンドウが複数ある場合は、`windows` で得た handle で指定できます:

```bash
pyselector tree --window-handle 0x2E20F46
```

全体像だけを掴む（ノードを列挙せず `control_type` / `class_name` ごとの件数を出す）:

```bash
pyselector tree --window-handle 0x2E20F46 --summary
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
  "windows": {
    "backend": "win32",
    "max_items": 50,
    "only_visible": true
  },
  "find": {
    "backend": "uia",
    "scope": "window",
    "timeout": 5,
    "depth": 8,
    "max_items": 200,
    "limit": 20,
    "selector_limit": 3,
    "only_visible": true
  },
  "act": {
    "allow_actions": false,
    "backend": "uia",
    "depth": 8,
    "max_items": 200,
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
