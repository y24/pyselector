# 01_requirements.md

# pywinauto Selector Inspector CLI 要件定義書

## 1. 目的

Windowsアプリケーションをpywinautoで自動化する際に、UI要素を特定するためのセレクター調査を補助するCLIツールを作成する。

Webブラウザ向けにはSelectorsHubのような拡張機能があり、対象要素に対するセレクター候補を簡単に確認できる。
本ツールでは、それと同じような体験をWindowsデスクトップアプリケーション向けに提供する。

ただし、対象はCSS/XPathではなく、pywinautoで利用する以下のような指定方法とする。

```python
dlg.child_window(title="OK", class_name="Button")
dlg.child_window(control_id=1, class_name="Button")
dlg.child_window(auto_id="num1Button", control_type="Button")
```

本ツールは、対象UI要素の属性情報を表示するだけでなく、その要素を特定するために使えそうなpywinautoセレクター候補と、その候補で何件のUI要素がヒットするかを表示する。

---

## 2. 開発動機

pywinautoでWindowsアプリケーションを自動化する場合、UI要素を特定するために以下のような作業が発生する。

* Inspect.exeで属性を確認する
* `print_control_identifiers()` を実行して階層を見る
* UIA / Win32 のどちらのバックエンドを使うべきか試す
* `title`, `class_name`, `control_id`, `auto_id`, `control_type` などの組み合わせを試す
* 候補セレクターで対象要素を一意に絞れるか確認する

これらの作業は毎回手間がかかる。
また、要素の属性を確認できても、「どのセレクターを書けばよいか」は別途判断が必要になる。

そこで、カーソル下のUI要素を起点に、以下をまとめて表示するCLIツールを作る。

```text
- UIA / Win32 両バックエンドで取得できる要素情報
- pywinautoで使えるセレクター候補
- 各セレクター候補のヒット件数
```

既存のElementFinderの後継版として位置づける。
必要に応じて、ElementFinderで実装済みのカーソル位置取得、要素列挙、バックエンド切替、要素情報取得などのロジックは流用する。

---

## 3. 想定ツール名

仮称。

```text
pyselector
```

または既存ツールとの連続性を重視する場合。

```text
elementfinder2
uiaf2
```

本要件定義では、以降 `pyselector` と表記する。

---

## 4. 想定ユーザー

主な利用者は、Windowsデスクトップアプリケーションをpywinautoで自動化するQAエンジニア、テスト自動化担当者、RPAスクリプト作成者とする。

特に以下のような場面を想定する。

* WindowsデスクトップアプリのE2Eテストを作成している
* UI要素の特定に時間がかかっている
* Inspect.exeを見るだけではセレクター候補を決めにくい
* UIAとWin32のどちらで取るべきか判断したい
* 同じ種類のボタンや入力欄が複数あり、一意に特定できる条件を探したい
* pywinautoコードに貼り付けやすいセレクター候補がほしい

---

## 5. 対象範囲

## 5.1 対象

本ツールの対象範囲は以下。

* Windowsデスクトップアプリケーション
* pywinautoで操作可能なUI要素
* UIA Backendによる要素情報取得
* Win32 Backendによる要素情報取得
* カーソル位置からの対象要素特定
* 対象要素の属性表示
* pywinautoセレクター候補の生成
* セレクター候補ごとのヒット件数表示
* CLIでのテキスト出力
* `pip install .` による簡易インストール

---

## 6. 基本コンセプト

本ツールの中核機能は以下の3つ。

```text
1. Inspect
   カーソル下のUI要素の属性を取得する

2. Generate
   pywinautoで使えるセレクター候補を生成する

3. Count
   各セレクター候補で何件ヒットするかを数える
```

本ツールは、セレクターの採用判断を自動で行うものではない。
星評価、推奨ラベル、採用理由などは表示しない。

ユーザーは、表示されたセレクター候補とヒット件数を見て、どの候補を採用するか判断する。

---

## 7. 利用イメージ

## 7.1 最小実行

```bash
pyselector
```

または明示的にサブコマンドを指定する。

```bash
pyselector inspect
```

実行すると5秒のカウントダウンが始まる。
ユーザーはその間に、調査したいUI要素の上へマウスカーソルを移動する。

5秒後、現在のカーソル位置をもとに対象UI要素を特定し、要素情報とセレクター候補を表示する。

---

## 7.2 待機秒数を指定する

```bash
pyselector inspect --delay 3
```

---

## 7.3 使用バックエンドを指定する

```bash
pyselector inspect --backend both
pyselector inspect --backend win32
pyselector inspect --backend uia
```

既定は `both` とする。

ただし、セレクター候補の表示順はWin32を優先する。
理由は、従来型のWindowsデスクトップアプリケーションでは、Win32 Backendのほうがパフォーマンス面で有利な場合が多いため。

---

## 7.4 探索範囲を指定する

```bash
pyselector inspect --scope window
pyselector inspect --scope desktop
```

既定は `window` とする。

通常は、対象要素が所属するトップレベルウィンドウ配下でヒット件数を確認できれば十分と考える。
デスクトップ全体を探索すると重くなりやすく、ノイズも増えるため、明示指定時のみ使用する。

---

# 8. 機能要件

## FR-001 カウントダウンによる対象要素選択

ツールを実行すると、既定で5秒のカウントダウンを表示する。

```text
[INFO] 5秒後にカーソル下のUI要素を取得します
[INFO] 5...
[INFO] 4...
[INFO] 3...
[INFO] 2...
[INFO] 1...
```

### 要件

* 既定の待機時間は5秒とする
* `--delay` で待機秒数を変更できる
* `--delay 0` の場合は即時取得する
* Ctrl+Cで中断できる
* 中断時は終了コード `130` とする

---

## FR-002 カーソル位置からUI要素を特定する

カウントダウン終了時点のマウスカーソル座標を取得し、その座標上にあるUI要素を特定する。

### 要件

* スクリーン座標を取得する
* UIA Backendでカーソル下の要素を取得する
* Win32 Backendでカーソル下の要素を取得する
* `--backend` 指定に応じて使用するバックエンドを切り替える
* UIA / Win32 の取得結果が異なる場合は、両方を表示する
* 片方のバックエンドで取得できなかった場合も、取得できた方を表示する
* 両方で取得できなかった場合は、座標とエラー概要を表示して終了する

---

## FR-003 対象要素の属性情報を表示する

取得したUI要素について、バックエンドごとに属性情報を表示する。

### UIA Backend 表示項目

```text
[UIA Backend]
  window_text: ...
  control_type: ...
  automation_id: ...
  class_name: ...
  friendly_class_name: ...
  children_count: ...
  depth: ...
  rectangle: L=..., T=..., R=..., B=..., W=..., H=...
  is_visible: ...
  is_enabled: ...
  handle: ...
  process_id: ...
  process_name: ...
```

### Win32 Backend 表示項目

```text
[Win32 Backend]
  window_text: ...
  control_type: ...
  automation_id: ...
  class_name: ...
  friendly_class_name: ...
  control_id: ...
  children_count: ...
  depth: ...
  rectangle: L=..., T=..., R=..., B=..., W=..., H=...
  is_visible: ...
  is_enabled: ...
  handle: ...
  process_id: ...
  process_name: ...
```

### 要件

* 取得できない項目は `(None)` と表示する
* 例外が発生した項目は、可能であれば `(Error)` と表示する
* 既定では主要項目のみ表示する
* `--detail` 指定時は取得可能な詳細項目を追加表示する

---

## FR-004 対象ウィンドウ情報を表示する

対象要素が所属するトップレベルウィンドウの情報を表示する。

```text
[Target Window]
  title: 電卓
  class_name: ApplicationFrameWindow
  process_name: CalculatorApp.exe
  process_id: 12345
  handle: 0x000A1234
```

### 要件

* 対象要素のトップレベルウィンドウを推定する
* セレクター候補のヒット件数確認では、既定でこのウィンドウ配下を探索範囲とする
* UIA / Win32でトップレベルウィンドウの取得結果が異なる場合は、バックエンドごとに保持する
* ウィンドウ情報を取得できない場合は、その旨を表示する

---

## FR-005 親階層パスを表示する

対象要素までの親階層を表示する。

```text
[Hierarchy - UIA]
  0 Window  "電卓"
  1 Pane    ""
  2 Group   "Number pad"
  3 Button  "1"  auto_id="num1Button"
```

### 要件

* ルートまたはトップレベルウィンドウから対象要素までの階層を表示する
* バックエンドごとに階層を表示する
* 各階層には、可能な範囲で以下を表示する

  * 種別
  * `window_text`
  * `control_type`
  * `automation_id`
  * `class_name`
* 既定ではコンパクト表示とする
* `--detail` 指定時は `rectangle`, `handle`, `control_id` なども表示する

この親階層は、単体セレクターで一意に絞れない場合に、親要素経由のセレクター候補を作るために使う。

---

## FR-006 pywinautoセレクター候補を生成する

対象要素の属性から、pywinautoで利用できるセレクター候補を生成する。

### 要件

* Win32 Backendの候補を優先して生成・表示する
* UIA Backendの候補も生成・表示する
* 候補は複数表示する
* 候補はpywinautoコードに貼り付けやすい形式で表示する
* 候補生成では、取得できた属性のみを使用する
* 空文字、`None`、不安定な値だけに依存する候補は可能な限り避ける
* `handle` を使った候補は生成してもよいが、常に最下位に表示する

---

# FR-007 セレクター候補ごとのヒット件数とwarningを表示する

各セレクター候補について、探索範囲内で何件のUI要素がヒットするかを表示する。
また、候補に注意点がある場合のみ `warning` を表示する。

## 表示形式

```text
[Selector Candidates - Win32]

[1] hits: 1
    dlg.child_window(control_id=1, class_name="Button")

[2] hits: 5
    dlg.child_window(class_name="Button")
    warning: 複数要素にヒットします

[3] hits: 1
    dlg.child_window(class_name="Button", found_index=3)
    warning: found_index は画面構成や表示順の変更に弱い可能性があります

[4] hits: 1
    dlg.window(handle=0x2E20F46)
    warning: handle はアプリ起動ごとに変わる可能性があります
```

UIA側の例。

```text
[Selector Candidates - UIA]

[1] hits: 1
    dlg.child_window(auto_id="num1Button", control_type="Button")

[2] hits: 24
    dlg.child_window(control_type="Button")
    warning: 複数要素にヒットします
```

## 要件

* セレクター候補とヒット件数を表示する
* warningがある場合のみ、候補の下に `warning:` を表示する
* warningがない候補には、追加説明を表示しない
* 星評価は表示しない
* `recommended` のような推奨ラベルは表示しない
* `unique` のような判定ラベルは表示しない
* 通常候補の `reason` は表示しない
* 採用理由は表示しない
* 表示順はセレクター生成ルールに従う
* 既定の探索範囲は対象トップレベルウィンドウ配下とする
* `--scope desktop` 指定時のみ、デスクトップ全体を探索する

---

# warning表示条件

## 表示するwarning

以下の場合はwarningを表示する。

```text
- hits = 0
- hits > 1
- found_index を使用している
- handle を使用している
- セレクター評価中に例外が発生した
- 対象要素が非表示または無効状態
```

## warning文言例

```text
hits = 0:
  warning: この候補では対象要素にヒットしません

hits > 1:
  warning: 複数要素にヒットします

found_index 使用:
  warning: found_index は画面構成や表示順の変更に弱い可能性があります

handle 使用:
  warning: handle はアプリ起動ごとに変わる可能性があります

評価失敗:
  warning: セレクター評価に失敗しました

非表示要素:
  warning: 対象要素は非表示です

無効要素:
  warning: 対象要素は無効状態です
```

---

# title依存のwarningについて

`title` や `window_text` 依存も厳密には注意点だけど、これを毎回warningにすると出力がかなりうるさくなる。
そのため初期MVPでは、以下の扱いとする。

```text
既定:
  title依存だけではwarningを出さない

--detail指定時:
  title/window_text は表示文言変更の影響を受ける可能性があります
  というwarningを表示してもよい
```

---

## FR-008 セレクター候補の表示順を制御する

候補の採用判断はユーザーが行うが、一覧の見やすさのために表示順は制御する。

### 要件

* 既定ではWin32 Backendの候補を先に表示する
* 次にUIA Backendの候補を表示する
* 各バックエンド内の表示順は、後述のセレクター生成ルールに従う
* `handle` を使った候補は常に最下位に表示する
* スコア、星評価、推奨表示は行わない

---

## FR-009 pywinautoコードスニペットを表示する

対象ウィンドウへの接続例と、候補セレクターの使い方が分かる最小限のコードスニペットを表示する。

ただし、候補一覧が主であり、コードスニペットは補助的な表示とする。

### 表示例

```python
from pywinauto import Desktop

dlg = Desktop(backend="win32").window(title="電卓")
target = dlg.child_window(control_id=1, class_name="Button")
```

### 要件

* Win32 Backend用の接続例を表示する
* UIA Backend用の接続例を表示する
* 取得できたバックエンドのみ表示する
* 操作実行コードは表示しない
* `.click_input()` や `.set_text()` は既定では表示しない

---

## FR-010 要素ツリー表示

単一要素のinspectとは別に、対象ウィンドウまたはカーソル下要素を起点とした要素ツリーを表示できる。

### コマンド例

```bash
pyselector tree --cursor
pyselector tree --window-title "電卓" --depth 3
pyselector tree --window-title ".*設定.*" --title-re --backend uia
```

### 要件

* `tree` サブコマンドを提供する
* カーソル下要素を起点にできる
* ウィンドウタイトルを指定して起点にできる
* 探索深度を指定できる
* UIA / Win32バックエンドを指定できる
* 既定では可視要素のみ表示する
* 大量表示を避けるため、最大件数を指定できる

---

# 9. コマンドライン仕様

## 9.1 inspect

```bash
pyselector inspect [options]
```

| オプション                        | 説明            | 既定       |
| ---------------------------- | ------------- | -------- |
| `--delay <sec>`              | カーソル取得までの待機秒数 | `5`      |
| `--backend uia\|win32\|both` | 使用バックエンド      | `both`   |
| `--scope window\|desktop`    | ヒット件数の探索範囲    | `window` |
| `--detail`                   | 詳細情報を表示する     | false    |
| `--verbose`                  | 詳細ログを表示する     | false    |
| `--timeout <sec>`            | 探索タイムアウト秒数    | `5`      |
| `--max-items <n>`            | 探索最大件数        | none     |
| `--only-visible`             | 可視要素のみ対象にする   | true     |

### 提供しないオプション

以下の機能は提供しない。

```text
--json
--output
--copy
```

---

## 9.2 tree

```bash
pyselector tree [options]
```

| オプション                    | 説明                  | 既定      |
| ------------------------ | ------------------- | ------- |
| `--cursor`               | カーソル下要素を起点にする       | false   |
| `--window-title <title>` | 対象ウィンドウタイトル         | none    |
| `--title-re`             | ウィンドウタイトルを正規表現として扱う | false   |
| `--backend uia\|win32`   | 使用バックエンド            | `win32` |
| `--depth <n>`            | 探索深度                | `3`     |
| `--max-items <n>`        | 最大表示件数              | `200`   |
| `--only-visible`         | 可視要素のみ表示する          | true    |
| `--detail`               | 詳細情報を表示する           | false   |

---

## 9.3 version

```bash
pyselector version
```

ツールのバージョンを表示する。

---

# 10. セレクター生成ルール

## 10.1 基本方針

セレクター生成では、Win32 Backendを優先する。

理由は、従来型のWindowsデスクトップアプリケーションでは、Win32 Backendのほうが探索・操作のパフォーマンス面で有利な場合が多いため。

ただし、アプリケーションによってはWin32では対象要素が十分に見えず、UIAのほうが詳細に取得できる場合がある。
そのため、既定では両方のバックエンドで候補を表示する。

表示順は以下とする。

```text
1. Win32 Backend のセレクター候補
2. UIA Backend のセレクター候補
```

---

## 10.2 Win32向け候補

Win32 Backendでは、以下の順で候補を生成・表示する。

```python
dlg.child_window(control_id=..., class_name="...")
dlg.child_window(title="...", class_name="...")
dlg.child_window(control_id=...)
dlg.child_window(class_name="...", found_index=N)
dlg.child_window(title="...", found_index=N)
dlg.child_window(class_name="...")
dlg.child_window(title="...")
dlg.window(handle=...)
```

### Win32候補の優先順位

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

### 補足

`handle` はアプリケーションの起動ごとに変わる可能性があるため、テストコードにハードコードする用途には向かない。
そのため、候補として表示する場合でも、常に最下位に表示する。

---

## 10.3 UIA向け候補

UIA Backendでは、以下の順で候補を生成・表示する。

```python
dlg.child_window(auto_id="...", control_type="...")
dlg.child_window(title="...", auto_id="...", control_type="...")
dlg.child_window(auto_id="...")
dlg.child_window(title="...", control_type="...")
dlg.child_window(title_re="^...$", control_type="...")
dlg.child_window(control_type="...", found_index=N)
dlg.child_window(title="...")
```

### UIA候補の優先順位

```text
1. automation_id + control_type
2. title + automation_id + control_type
3. automation_id
4. title + control_type
5. title_re + control_type
6. control_type + found_index
7. title
```

---

## 10.4 handle候補

`handle` を使った候補は、Win32 Backendでhandleを取得できる場合のみ生成する。

```python
dlg.window(handle=0x00123456)
```

### 要件

* handle候補は生成してもよい
* handle候補は常に最下位に表示する
* handle候補しか一意にならない場合でも、上位には表示しない
* handle候補に推奨表示は付けない

---

## 10.5 found_index候補

`found_index` は、同じ属性を持つ要素が複数存在する場合に候補として生成する。

```python
dlg.child_window(class_name="Button", found_index=3)
dlg.child_window(control_type="Button", found_index=3)
```

### 要件

* `found_index` 付き候補は生成対象とする
* `handle` よりは上位に表示してよい
* 単独で一意になりやすい属性候補よりは下位に表示する
* 注意文は表示しない

---

# 11. 出力仕様

## 11.1 標準出力

既定では、人間が読みやすいテキスト形式で標準出力に表示する。

表示順は以下。

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

---

## 11.2 出力例

```text
[INFO] pyselector started
[INFO] 座標を決定しました。 X=636, Y=2240

[Target Window]
  title: 電卓
  class_name: ApplicationFrameWindow
  process_name: CalculatorApp.exe
  process_id: 12345
  handle: 0x2E20F46

[Win32 Backend]
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
  process_name: CalculatorApp.exe

[UIA Backend]
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
  process_name: CalculatorApp.exe

[Hierarchy - UIA]
  0 Window  "電卓"
  1 Pane    ""
  2 Group   "Number pad"
  3 Button  "1"  auto_id="num1Button"

[Selector Candidates - Win32]

[1] hits: 1
    dlg.child_window(class_name="Windows.UI.Core.CoreWindow")

[2] hits: 1
    dlg.window(handle=0x2E20F46)

[Selector Candidates - UIA]

[1] hits: 1
    dlg.child_window(auto_id="num1Button", control_type="Button")

[2] hits: 1
    dlg.child_window(title="1", auto_id="num1Button", control_type="Button")

[3] hits: 24
    dlg.child_window(control_type="Button")

[Code Snippet - Win32]
from pywinauto import Desktop

dlg = Desktop(backend="win32").window(title="電卓")
target = dlg.child_window(class_name="Windows.UI.Core.CoreWindow")

[Code Snippet - UIA]
from pywinauto import Desktop

dlg = Desktop(backend="uia").window(title="電卓")
target = dlg.child_window(auto_id="num1Button", control_type="Button")
```

---

# 11.3 表示しない情報

セレクター候補一覧では、以下を表示しない。

```text
- 星評価
- スコア
- recommended
- unique
- 通常候補のreason
- 採用理由
```

ただし、候補に注意点がある場合は `warning` を表示する。

---

# 12. 非機能要件

## NFR-001 対応環境

* Windows 10 / 11
* Python 3.9以上
* pywinauto 0.6.8以上
* cmd / PowerShell / Windows Terminalで実行可能
* 日本語UI要素を扱えること

---

## NFR-002 インストール容易性

セットアップは可能な限り簡単にする。

```bash
git clone <repository>
cd pyselector
pip install .
```

インストール後、以下のように実行できる。

```bash
pyselector --help
pyselector inspect
```

開発時は以下。

```bash
pip install -e .
```

`TestStat-CLI` と同様に、`pyproject.toml` または `setup.py` にconsole scriptを定義し、`pip install .` だけでCLIコマンドが使える構成にする。

### pyproject.toml例

```toml
[project.scripts]
pyselector = "pyselector.cli:main"
```

---

## NFR-003 応答性能

### 目標

* 通常の単一要素inspectは10秒以内に完了する
* セレクター候補生成は3秒以内に完了する
* ヒット件数確認は5秒以内に完了する
* 大規模画面ではタイムアウトしても、取得済みの情報を可能な範囲で表示する

### 方針

* 既定の探索範囲は対象ウィンドウ配下とする
* デスクトップ全体探索は `--scope desktop` 指定時のみ行う
* `--max-items` で探索件数を制限できる
* `--timeout` で探索タイムアウトを指定できる
* 既定表示ではWin32候補を先に出す

---

## NFR-004 安定性

* 片方のバックエンドで取得に失敗しても、もう片方で取得できれば結果を表示する
* COM例外、アクセス拒否、タイムアウトを適切に扱う
* 予期しない例外が発生しても、可能な範囲で原因を表示する
* 対象ウィンドウが最小化されている場合は、取得できない可能性がある
* 対象要素がカウントダウン中に消えた場合は、取得失敗として扱う

---

## NFR-005 読みやすさ

* 既定では重要情報を中心に表示する
* `--detail` 指定時のみ詳細情報を表示する
* 候補一覧はセレクターとヒット件数だけにする
* 不要な説明文を出しすぎない
* Windowsターミナル上で文字化けしないようUTF-8を前提にする
* 日本語の `window_text` をそのまま表示できること

---

# 13. 内部設計方針

## 13.1 モジュール構成案

```text
pyselector/
  __init__.py
  cli.py
  countdown.py
  cursor.py

  backends/
    __init__.py
    uia_inspector.py
    win32_inspector.py

  model/
    element_info.py
    selector_candidate.py
    inspection_result.py

  selector/
    generator.py
    evaluator.py
    formatter.py

  output/
    text_output.py

  utils/
    process.py
    rectangle.py
    logging.py

tests/
  test_selector_generator.py
  test_selector_evaluator.py
  test_text_output.py

pyproject.toml
README.md
```

---

## 13.2 主要内部モデル

### ElementInfo

UI要素の属性情報を保持する。

```text
ElementInfo
  backend
  window_text
  control_type
  automation_id
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

### SelectorCandidate

生成したセレクター候補を保持する。

```text
SelectorCandidate
  backend
  selector_text
  selector_type
  uses_title
  uses_class_name
  uses_control_id
  uses_auto_id
  uses_control_type
  uses_found_index
  uses_handle
  display_order
```

### SelectorEvaluation

候補セレクターのヒット件数を保持する。

```text
SelectorEvaluation
  candidate
  hits
```

### InspectionResult

1回のinspect結果全体を保持する。

```text
InspectionResult
  cursor_position
  target_window
  win32_element
  uia_element
  win32_hierarchy
  uia_hierarchy
  win32_candidates
  uia_candidates
```

---

## 13.3 既存ElementFinderからの流用候補

既存ElementFinderから以下の処理は流用候補とする。

* カーソル位置取得
* カウントダウン
* UIA Backendでの要素取得
* Win32 Backendでの要素取得
* 要素属性の抽出
* 親階層の取得
* 子要素列挙
* 深度制限
* 可視要素フィルタ
* CLI引数処理
* ログ出力

ただし、後継版では「要素列挙」よりも「セレクター候補生成とヒット件数確認」を主目的にする。

---

# 14. エラー処理

## 14.1 終了コード

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

### 補足

片方のバックエンドだけ失敗した場合は、もう片方の結果を表示できるなら終了コード `0` としてよい。
ただし、失敗したバックエンドの概要は表示する。

---

## 14.2 エラー表示例

```text
[WARN] Win32 Backendではカーソル下の子要素を取得できませんでした。
[INFO] UIA Backendの結果のみ表示します。
```

```text
[ERROR] カーソル下のUI要素を取得できませんでした。
  cursor: X=1200, Y=800
  backend: both
```

---

# 15. 受け入れ基準

## AC-001 基本inspect

Windows標準の電卓を対象に `pyselector inspect` を実行し、5秒後のカーソル下要素について要素情報が表示されること。

---

## AC-002 両バックエンド表示

UIA BackendとWin32 Backendの取得結果が表示されること。
片方が取得できない場合も、もう片方の結果が表示されること。

---

## AC-003 Win32候補の優先表示

Win32 Backendで対象要素を取得できた場合、Win32のセレクター候補がUIA候補より先に表示されること。

---

## AC-004 セレクター候補生成

対象要素に対して、取得可能な属性から複数のセレクター候補が表示されること。

---

## AC-005 ヒット件数表示

各候補について、対象ウィンドウ配下でのヒット件数が表示されること。

---

## AC-006 pip install対応

`pip install .` 後に以下が実行できること。

```bash
pyselector --help
pyselector inspect
```

---

# 16. 初期MVP

## 16.1 MVP対象

初期MVPでは以下を実装する。

```text
- pyselector inspect
- 5秒カウントダウン
- カーソル下要素取得
- UIA / Win32 Backendの要素情報表示
- 対象ウィンドウ情報表示
- 親階層表示
- Win32優先のセレクター候補生成
- UIAセレクター候補生成
- セレクター候補ごとのヒット件数表示
- handle候補の最下位表示
- pip install . 対応
```

---

## 16.2 MVP対象外

初期MVPでは以下は実装しない。

```text
- クリップボードコピー
- JSON出力
- GUI版
- 常駐モード
- スクリーンショット保存
- 対象要素への操作実行
- Playwright / Selenium連携
- pytestコード自動生成
- 設定ファイル読み込み
```

---

# 17. 将来拡張候補

MVP後に必要になった場合、以下を検討する。

```text
- 設定ファイル対応
- 候補生成ルールのカスタマイズ
- スクリーンショット保存
- 対象要素のハイライト表示
- pytest/pywinautoコード断片生成
- 複数候補の比較表示
- 取得結果のファイル保存
- 簡易GUI版
```

ただし、JSON出力やクリップボードコピーは初期要件には含めない。
必要性が明確になった時点で、別途検討する。
