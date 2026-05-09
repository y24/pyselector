# 03_output_format.md

# pyselector 出力仕様書

## 1. 目的

本書は、pywinauto Selector Inspector CLI の標準出力フォーマットを定義する。

本ツールは、Windowsアプリケーション上のUI要素を調査し、以下の情報をCLI上に表示する。

- 実行情報
- カーソル座標
- 対象ウィンドウ情報
- Win32 Backendの要素情報
- UIA Backendの要素情報
- 親階層
- セレクター候補
- 各セレクター候補のヒット件数
- 注意が必要な候補のwarning
- 最小コードスニペット

本書では、上記情報の表示順、表示項目、書式、warning表示条件を定義する。

---

## 2. 出力方針

## 2.1 基本方針

出力は、人間がCLI上で読みやすいテキスト形式とする。

本ツールでは、JSON出力、ファイル出力、クリップボードコピーは提供しない。

## 2.2 優先すること

出力では以下を優先する。

```text
- セレクター候補とヒット件数を見やすく表示する
- Win32 Backendの情報を先に表示する
- UIA Backendの情報も併記する
- warningがある候補だけにwarningを表示する
- 不要な推薦理由やスコアを表示しない
- 手動コピーしやすいコード形式でセレクターを表示する
````

## 2.3 表示しない情報

セレクター候補一覧では、以下を表示しない。

```text
- 星評価
- スコア
- recommended
- unique
- 通常時のreason
- 採用理由
```

ただし、注意が必要な候補には `warning:` を表示する。

---

## 3. 出力全体の構成

`inspect` コマンドの標準出力は、以下の順で表示する。

```text
1. 実行情報
2. カーソル座標
3. 対象ウィンドウ情報
4. Win32 Backendの要素情報
5. UIA Backendの要素情報
6. 親階層
7. セレクター候補とヒット件数
8. 最小コードスニペット
```

ただし、指定された `--backend` によって、表示するバックエンド情報は変わる。

| `--backend` | 表示対象                         |
| ----------- | ---------------------------- |
| `win32`     | Win32 Backendのみ              |
| `uia`       | UIA Backendのみ                |
| `both`      | Win32 Backend、UIA Backendの両方 |

`both` の場合、表示順は常に以下とする。

```text
1. Win32 Backend
2. UIA Backend
```

---

## 4. 共通表示ルール

## 4.1 セクション見出し

セクション見出しは角括弧で囲む。

CLI上では、端末が色表示に対応している場合に大見出しと小見出しへ色を付ける。
`NO_COLOR` 環境変数が設定されている場合は色を付けない。

Win32 / UIA の両方を持つ情報は、大見出しの下にバックエンド別の小見出しを置く。

```text
[Target Window]
[Backend]
  [Win32]
  [UIA]
[Hierarchy]
  [Win32]
  [UIA]
[Selector Candidates]
  [Win32]
  [UIA]
[Code Snippet]
  [Win32]
  [UIA]
```

## 4.2 インデント

属性情報は2スペースでインデントする。

```text
[Target Window]
  title: 電卓
  class_name: ApplicationFrameWindow

[Backend]
  [Win32]
    window_text: OK

  [UIA]
    window_text: 1
```

セレクター候補は、番号行の次の行に4スペースで表示する。

```text
[1] hits: 1
    dlg.child_window(control_id=1, class_name="Button")
```

warningは、セレクター候補の次の行に4スペースで表示する。

```text
[2] hits: 5
    dlg.child_window(class_name="Button")
    warning: 複数要素にヒットします
```

## 4.3 値が取得できない場合

値が取得できない場合は `(None)` と表示する。

```text
automation_id: (None)
control_id: (None)
handle: (None)
```

取得処理で例外が発生した場合は、原則として `(Error)` と表示する。

```text
children_count: (Error)
```

ただし、エラー概要を表示したほうが有用な場合は、warningまたはエラー表示に含めてもよい。

## 4.4 真偽値

真偽値はPython表記に合わせて表示する。

```text
is_visible: True
is_enabled: False
```

## 4.5 handle

handleは16進数で表示する。

```text
handle: 0x2E20F46
```

取得できない場合は `(None)` と表示する。

```text
handle: (None)
```

## 4.6 rectangle

rectangleは以下の形式で表示する。

```text
rectangle: L=598, T=2218, R=675, B=2269, W=77, H=51
```

各値の意味は以下。

| 表示  | 意味     |
| --- | ------ |
| `L` | left   |
| `T` | top    |
| `R` | right  |
| `B` | bottom |
| `W` | width  |
| `H` | height |

`W` と `H` は以下で算出する。

```text
W = R - L
H = B - T
```

---

## 5. 実行情報

## 5.1 表示項目

`inspect` 実行時は、冒頭に実行情報を表示する。

```text
[INFO] pyselector started
[INFO] countdown: 5 sec
```

## 5.2 カウントダウン

`--delay` が1以上の場合、カウントダウンを表示する。

```text
[INFO] 5秒後にカーソル下のUI要素を取得します
[INFO] 5...
[INFO] 4...
[INFO] 3...
[INFO] 2...
[INFO] 1...
```

`--delay 0` の場合、カウントダウンは表示しない。

```text
[INFO] delay: 0 sec
```

## 5.3 カーソル座標

カウントダウン後に取得したカーソル座標を表示する。

```text
[INFO] cursor position: X=636, Y=2240
```

---

## 6. Target Window表示

## 6.1 概要

`[Target Window]` では、対象要素が所属するトップレベルウィンドウの情報を表示する。

## 6.2 表示形式

```text
[Target Window]
  title: 電卓
  class_name: ApplicationFrameWindow
  process_name: CalculatorApp.exe
  process_id: 12345
  handle: 0x2E20F46
```

## 6.3 表示項目

| 項目             | 説明               |
| -------------- | ---------------- |
| `title`        | トップレベルウィンドウのタイトル |
| `class_name`   | ウィンドウのクラス名       |
| `process_name` | プロセス名            |
| `process_id`   | プロセスID           |
| `handle`       | ウィンドウハンドル        |

## 6.4 取得できない場合

対象ウィンドウを特定できない場合は、以下のように表示する。

```text
[Target Window]
  title: (None)
  class_name: (None)
  process_name: (None)
  process_id: (None)
  handle: (None)
```

ただし、対象ウィンドウを特定できない場合、セレクター候補のヒット件数評価ができない可能性がある。

---

## 7. Backend要素情報表示

## 7.1 Win32 Backend

Win32 Backendで取得した対象要素の情報を表示する。

```text
[Backend]
[Win32]
  window_text: OK
  control_type: (None)
  automation_id: (None)
  class_name: Button
  friendly_class_name: Button
  control_id: 1
  children_count: 0
  depth: 3
  rectangle: L=100, T=200, R=180, B=230, W=80, H=30
  is_visible: True
  is_enabled: True
  handle: 0x00123456
  process_id: 12345
  process_name: sample.exe
```

### 表示項目

| 項目                    | 説明                              |
| --------------------- | ------------------------------- |
| `window_text`         | 要素の表示文字列                        |
| `control_type`        | コントロール種別。Win32では取得できない場合がある     |
| `automation_id`       | AutomationId。Win32では取得できない場合がある |
| `class_name`          | クラス名                            |
| `friendly_class_name` | pywinauto上のfriendly class name  |
| `control_id`          | Win32 control id                |
| `children_count`      | 子要素数                            |
| `depth`               | トップレベルウィンドウからの深さ                |
| `rectangle`           | 要素の矩形                           |
| `is_visible`          | 可視状態                            |
| `is_enabled`          | 有効状態                            |
| `handle`              | 要素のハンドル                         |
| `process_id`          | プロセスID                          |
| `process_name`        | プロセス名                           |

## 7.2 UIA Backend

UIA Backendで取得した対象要素の情報を表示する。

```text
[Backend]
[UIA]
  window_text: 1
  control_type: Button
  automation_id: num1Button
  class_name: Button
  friendly_class_name: Button
  children_count: 0
  depth: 6
  rectangle: L=598, T=2218, R=675, B=2269, W=77, H=51
  is_visible: True
  is_enabled: True
  handle: (None)
  process_id: 12345
  process_name: CalculatorApp.exe
```

### 表示項目

| 項目                    | 説明                             |
| --------------------- | ------------------------------ |
| `window_text`         | 要素の表示文字列                       |
| `control_type`        | UIA ControlType                |
| `automation_id`       | AutomationId                   |
| `class_name`          | クラス名                           |
| `friendly_class_name` | pywinauto上のfriendly class name |
| `children_count`      | 子要素数                           |
| `depth`               | トップレベルウィンドウからの深さ               |
| `rectangle`           | 要素の矩形                          |
| `is_visible`          | 可視状態                           |
| `is_enabled`          | 有効状態                           |
| `handle`              | 要素のハンドル。UIAでは取得できない場合がある       |
| `process_id`          | プロセスID                         |
| `process_name`        | プロセス名                          |

## 7.3 取得失敗時

片方のバックエンドで取得に失敗した場合は、以下のように表示する。

```text
[Backend]
[Win32]
  status: failed
  message: カーソル下の子要素を取得できませんでした
```

もう片方のバックエンドで取得できている場合は、処理を継続する。

両方のバックエンドで取得に失敗した場合は、エラーとして終了する。

---

## 8. Hierarchy表示

## 8.1 概要

`[Hierarchy]` では、対象要素までの親階層を表示する。

バックエンドごとに階層が異なる場合があるため、Win32とUIAは別々に表示する。

```text
[Hierarchy]
[Win32]
...

[UIA]
...
```

## 8.2 通常表示形式

通常表示では、1行に以下を表示する。

```text
階層番号 種別 "window_text" 主要属性
```

表示例。

```text
[Hierarchy]
[UIA]
  0 Window  "電卓"
  1 Pane    ""
  2 Group   "Number pad"
  3 Button  "1"  auto_id="num1Button"
```

Win32の例。

```text
[Hierarchy]
[Win32]
  0 Window  "電卓"  class_name="ApplicationFrameWindow"
  1 Pane    ""      class_name="Windows.UI.Core.CoreWindow"
  2 Button  "OK"    class_name="Button" control_id=1
```

## 8.3 詳細表示

`--detail` 指定時は、必要に応じて追加属性を表示してよい。

```text
[Hierarchy]
[UIA]
  0 Window  "電卓"  control_type="Window" class_name="ApplicationFrameWindow" rectangle=L=100,T=100,R=500,B=800
  1 Pane    ""      control_type="Pane" auto_id="MainPanel" rectangle=L=100,T=150,R=500,B=800
  2 Button  "1"     control_type="Button" auto_id="num1Button" rectangle=L=200,T=600,R=250,B=650
```

## 8.4 取得できない場合

親階層を取得できない場合は、以下のように表示する。

```text
[Hierarchy]
[UIA]
  status: failed
  message: 親階層を取得できませんでした
```

---

## 9. Selector Candidates表示

## 9.1 概要

`[Selector Candidates]` では、pywinautoで利用可能なセレクター候補を表示する。

表示対象は以下。

* セレクター候補
* ヒット件数
* warningがある場合のwarning

表示しないもの。

* 星評価
* スコア
* recommended
* unique
* 通常時のreason
* 採用理由

## 9.2 表示順

`--backend both` の場合、表示順は以下とする。

```text
1. [Selector Candidates] > [Win32]
2. [Selector Candidates] > [UIA]
```

各バックエンド内の候補表示順は、`04_selector_generation_spec.md` に従う。

## 9.3 基本表示形式

```text
[Selector Candidates]
[Win32]

[1] hits: 1
    dlg.child_window(control_id=1, class_name="Button")

[2] hits: 5
    dlg.child_window(class_name="Button")
    warning: 複数要素にヒットします
```

UIAの例。

```text
[Selector Candidates]
[UIA]

[1] hits: 1
    dlg.child_window(auto_id="num1Button", control_type="Button")

[2] hits: 24
    dlg.child_window(control_type="Button")
    warning: 複数要素にヒットします
```

## 9.4 ヒット件数

ヒット件数は以下の形式で表示する。

```text
[1] hits: 1
```

ヒット件数が取得できない場合は `(Error)` と表示する。

```text
[1] hits: (Error)
    dlg.child_window(control_id=1, class_name="Button")
    warning: セレクター評価に失敗しました
```

タイムアウトした場合は `(Timeout)` と表示する。

```text
[1] hits: (Timeout)
    dlg.child_window(class_name="Button")
    warning: セレクター評価がタイムアウトしました
```

## 9.5 warning表示

warningがある場合のみ、候補の下に `warning:` を表示する。

```text
[3] hits: 1
    dlg.child_window(class_name="Button", found_index=3)
    warning: found_index は画面構成や表示順の変更に弱い可能性があります
```

warningが複数ある場合は、複数行で表示する。

```text
[4] hits: 5
    dlg.child_window(class_name="Button", found_index=2)
    warning: 複数要素にヒットします
    warning: found_index は画面構成や表示順の変更に弱い可能性があります
```

## 9.6 warning表示条件

以下の場合はwarningを表示する。

| 条件                    | warning文言                             |
| --------------------- | ------------------------------------- |
| `hits = 0`            | `この候補では対象要素にヒットしません`                  |
| `hits > 1`            | `複数要素にヒットします`                         |
| `found_index` を使用している | `found_index は画面構成や表示順の変更に弱い可能性があります` |
| `handle` を使用している      | `handle はアプリ起動ごとに変わる可能性があります`         |
| セレクター評価に失敗した          | `セレクター評価に失敗しました`                      |
| セレクター評価がタイムアウトした      | `セレクター評価がタイムアウトしました`                  |
| 探索上限に達した              | `探索上限に達したため、ヒット件数が実際より少ない可能性があります`    |
| 対象要素が非表示              | `対象要素は非表示です`                          |
| 対象要素が無効状態             | `対象要素は無効状態です`                         |

## 9.7 title / window_text依存のwarning

`title` または `window_text` を使用した候補については、通常表示ではwarningを出さない。

理由は、Windowsアプリでは表示文字列を使ったセレクターが頻出し、常にwarningを出すと一覧性が下がるためである。

ただし、`--detail` 指定時は以下のwarningを表示してもよい。

```text
warning: title/window_text は表示文言変更の影響を受ける可能性があります
```

## 9.8 handle候補

handleを使用する候補は、常に候補一覧の最後に表示する。

```text
[8] hits: 1
    dlg.window(handle=0x00123456)
    warning: handle はアプリ起動ごとに変わる可能性があります
```

## 9.9 候補が生成できない場合

セレクター候補を生成できない場合は、以下のように表示する。

```text
[Selector Candidates]
[Win32]
  status: no candidates
```

または。

```text
[Selector Candidates]
[UIA]
  status: no candidates
```

---

## 10. Code Snippet表示

## 10.1 概要

`[Code Snippet]` では、pywinautoで対象ウィンドウへ接続し、候補セレクターを使う最小コード例を表示する。

コードスニペットは補助的な表示であり、セレクター候補一覧が主である。

## 10.2 Win32の表示例

```text
[Code Snippet]
[Win32]
from pywinauto import Desktop

dlg = Desktop(backend="win32").window(title="電卓")
target = dlg.child_window(control_id=1, class_name="Button")
```

## 10.3 UIAの表示例

```text
[Code Snippet]
[UIA]
from pywinauto import Desktop

dlg = Desktop(backend="uia").window(title="電卓")
target = dlg.child_window(auto_id="num1Button", control_type="Button")
```

## 10.4 使用する候補

コードスニペットでは、原則として各バックエンドの先頭候補を使用する。

ただし、先頭候補の `hits` が0または評価失敗の場合は、次に利用可能な候補を使用してもよい。

## 10.5 操作コード

初期版では、以下のような操作コードは表示しない。

```python
target.click_input()
target.set_text("...")
```

コードスニペットは、対象要素の取得までに留める。

---

## 11. treeコマンドの出力

## 11.1 概要

`tree` コマンドでは、指定した起点からUI要素ツリーを表示する。

## 11.2 表示形式

```text
[Tree]
[Win32]
  0 Window  "電卓"  class_name="ApplicationFrameWindow"
  1 Pane    ""      class_name="Windows.UI.Core.CoreWindow"
  2 Button  "OK"    class_name="Button" control_id=1
  2 Button  "Cancel" class_name="Button" control_id=2
```

UIAの例。

```text
[Tree]
[UIA]
  0 Window  "電卓"  control_type="Window"
  1 Pane    ""      control_type="Pane"
  2 Group   "Number pad" control_type="Group"
  3 Button  "1"     control_type="Button" auto_id="num1Button"
```

## 11.3 深度の表現

先頭の数値は、起点からの相対深度を表す。

```text
0 起点要素
1 起点要素の子
2 孫要素
```

## 11.4 max-itemsに達した場合

`--max-items` に達した場合は、末尾に以下を表示する。

```text
[WARN] max-items に達したため、以降の要素表示を省略しました。
```

---

## 12. エラー出力

## 12.1 カーソル下要素を取得できない場合

```text
[ERROR] カーソル下のUI要素を取得できませんでした。
  cursor: X=1200, Y=800
  backend: both
```

## 12.2 対象ウィンドウを特定できない場合

```text
[ERROR] 対象ウィンドウを特定できませんでした。
  cursor: X=1200, Y=800
```

## 12.3 片方のバックエンドのみ失敗した場合

片方のバックエンドのみ失敗した場合は、警告として表示し、処理は継続する。

```text
[WARN] Win32 Backendではカーソル下の要素を取得できませんでした。
[INFO] UIA Backendの結果のみ表示します。
```

## 12.4 引数エラー

```text
[ERROR] invalid argument: --backend must be one of win32, uia, both
```

---

## 13. inspect出力例

```text
[INFO] pyselector started
[INFO] countdown: 5 sec
[INFO] cursor position: X=636, Y=2240

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
  process_id: 12345
  process_name: CalculatorApp.exe

[UIA]
  window_text: 1
  control_type: Button
  automation_id: num1Button
  class_name: Button
  friendly_class_name: Button
  children_count: 0
  depth: 6
  rectangle: L=598, T=2218, R=675, B=2269, W=77, H=51
  is_visible: True
  is_enabled: True
  handle: (None)
  process_id: 12345
  process_name: CalculatorApp.exe

[Hierarchy]
[UIA]
  0 Window  "電卓"
  1 Pane    ""
  2 Group   "Number pad"
  3 Button  "1"  auto_id="num1Button"

[Selector Candidates]
[Win32]

[1] hits: 1
    dlg.child_window(class_name="Windows.UI.Core.CoreWindow")

[2] hits: 1
    dlg.window(handle=0x2E20F46)
    warning: handle はアプリ起動ごとに変わる可能性があります

[UIA]

[1] hits: 1
    dlg.child_window(auto_id="num1Button", control_type="Button")

[2] hits: 1
    dlg.child_window(title="1", auto_id="num1Button", control_type="Button")

[3] hits: 24
    dlg.child_window(control_type="Button")
    warning: 複数要素にヒットします

[Code Snippet]
[Win32]
from pywinauto import Desktop

dlg = Desktop(backend="win32").window(title="電卓")
target = dlg.child_window(class_name="Windows.UI.Core.CoreWindow")

[UIA]
from pywinauto import Desktop

dlg = Desktop(backend="uia").window(title="電卓")
target = dlg.child_window(auto_id="num1Button", control_type="Button")
```

---

## 14. 出力仕様上の注意

## 14.1 出力は安定させる

表示項目名は、実装後に不用意に変更しない。

特に以下は、ユーザーが目視確認やコピーに使うため、安定させる。

```text
[Selector Candidates]
[Win32]
[UIA]
hits:
warning:
```

## 14.2 候補一覧をうるさくしすぎない

warningは必要な場合のみ表示する。

通常候補に対して、採用理由や説明文は表示しない。

## 14.3 バックエンド差異をそのまま表示する

Win32とUIAでは取得できる要素が異なることがある。

本ツールでは、差異を無理に統合せず、バックエンドごとに表示する。

## 14.4 handleは最後に表示する

handle候補はデバッグ用途としては有用だが、ハードコードには向かない。

そのため、セレクター候補一覧では常に最後に表示し、warningを付ける。
