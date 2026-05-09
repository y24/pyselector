# 04_selector_generation_spec.md

# pyselector セレクター生成仕様書

## 1. 目的

本書は、pywinauto Selector Inspector CLI におけるセレクター候補の生成仕様を定義する。

本ツールは、カーソル下のUI要素から取得した属性情報をもとに、pywinautoで利用可能なセレクター候補を生成し、各候補のヒット件数を表示する。

本書では以下を定義する。

- セレクター生成の基本方針
- Win32 Backend向け候補の生成ルール
- UIA Backend向け候補の生成ルール
- 候補の表示順
- 候補の重複排除
- ヒット件数の評価方法
- warning判定
- handle / found_index の扱い

---

## 2. 基本方針

## 2.1 生成対象

セレクター候補は、以下のバックエンドごとに生成する。

```text
- Win32 Backend
- UIA Backend
````

`--backend both` の場合は、両方の候補を生成する。

`--backend win32` の場合は、Win32 Backendの候補のみ生成する。

`--backend uia` の場合は、UIA Backendの候補のみ生成する。

---

## 2.2 表示優先順位

セレクター候補は、Win32 Backendを優先して表示する。

```text
1. Win32 Backend
2. UIA Backend
```

理由は、従来型のWindowsデスクトップアプリケーションでは、Win32 Backendのほうが探索・操作のパフォーマンス面で有利な場合が多いためである。

ただし、Win32では対象要素まで取得できず、UIAでのみ詳細な要素が取得できるケースもある。
そのため、既定では `--backend both` とし、両方の情報を表示する。

---

## 2.3 候補生成の考え方

セレクター候補は、取得できた属性情報のみを使用して生成する。

候補生成では、以下を重視する。

```text
- pywinautoでそのまま使える形式であること
- 対象ウィンドウ配下で評価できること
- 可能な限り単純な指定であること
- handleを優先しないこと
- found_indexは必要な場合のみ候補に含めること
```

本ツールは、候補の採用判断を自動では行わない。
候補とヒット件数を表示し、採用判断はユーザーが行う。

---

## 2.4 表示しない情報

セレクター候補には以下を表示しない。

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

## 3. 入力データ

## 3.1 ElementInfo

セレクター生成は、バックエンドごとの `ElementInfo` を入力として行う。

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

## 3.2 TargetWindowInfo

ヒット件数評価では、対象要素が所属するトップレベルウィンドウ情報を使用する。

```text
TargetWindowInfo
  title
  class_name
  process_name
  process_id
  handle
```

既定の探索範囲は、対象トップレベルウィンドウ配下とする。

---

## 4. 値の正規化

## 4.1 空値の扱い

以下の値は、候補生成に使用しない。

```text
- None
- 空文字
- 空白のみの文字列
- "(None)"
- "(Error)"
```

## 4.2 文字列のエスケープ

`title`, `auto_id`, `class_name`, `control_type` などの文字列値は、Python文字列として安全に表示できるようにエスケープする。

例。

```python
dlg.child_window(title="OK")
dlg.child_window(title="\"保存\" ボタン")
```

## 4.3 titleとwindow_text

pywinautoのセレクター候補では、要素の表示文字列は原則として `title` として出力する。

内部的に取得した項目名が `window_text` であっても、候補表示では以下のように出力する。

```python
dlg.child_window(title="OK")
```

## 4.4 automation_idとauto_id

UIAの `automation_id` は、pywinauto候補では `auto_id` として出力する。

```python
dlg.child_window(auto_id="num1Button")
```

## 4.5 handle

handleは16進数で出力する。

```python
dlg.child_window(handle=0x00123456)
```

対象要素がトップレベルウィンドウそのものである場合は、以下の形式を使用してもよい。

```python
Desktop(backend="win32").window(handle=0x00123456)
```

ただし、候補一覧では、原則として `dlg.` 起点の形式を優先する。

---

## 5. Candidateモデル

生成した候補は、内部的には以下の情報を持つ。

```text
SelectorCandidate
  backend
  selector_text
  selector_kind
  uses_title
  uses_title_re
  uses_class_name
  uses_control_id
  uses_auto_id
  uses_control_type
  uses_found_index
  uses_handle
  display_order
```

## 5.1 selector_text

実際に表示するpywinautoセレクター文字列。

例。

```python
dlg.child_window(control_id=1, class_name="Button")
```

## 5.2 selector_kind

候補の種類を表す内部分類。

例。

```text
win32_control_id_class_name
win32_title_class_name
uia_auto_id_control_type
uia_title_control_type
handle
```

## 5.3 display_order

候補の表示順を制御するための内部値。

数値が小さいほど先に表示する。

---

# 6. Win32 Backend向け候補生成

## 6.1 基本方針

Win32 Backendでは、以下の属性を主に使用する。

```text
- control_id
- class_name
- title
- found_index
- handle
```

Win32 Backendでは、`control_id` と `class_name` を優先する。

`handle` はアプリケーション起動ごとに変わる可能性があるため、常に最下位候補とする。

---

## 6.2 Win32候補の生成順

Win32 Backendでは、以下の順で候補を生成する。

```python
dlg.child_window(control_id=..., class_name="...")
dlg.child_window(title="...", class_name="...")
dlg.child_window(control_id=...)
dlg.child_window(class_name="...", found_index=N)
dlg.child_window(title="...", found_index=N)
dlg.child_window(class_name="...")
dlg.child_window(title="...")
dlg.child_window(handle=...)
```

## 6.3 Win32候補の優先順位

| 順位 | 候補                         | 生成条件                               |
| -: | -------------------------- | ---------------------------------- |
|  1 | `control_id + class_name`  | `control_id` と `class_name` が取得できる |
|  2 | `title + class_name`       | `title` と `class_name` が取得できる      |
|  3 | `control_id`               | `control_id` が取得できる                |
|  4 | `class_name + found_index` | `class_name` が取得でき、同一class候補が複数ある  |
|  5 | `title + found_index`      | `title` が取得でき、同一title候補が複数ある       |
|  6 | `class_name`               | `class_name` が取得できる                |
|  7 | `title`                    | `title` が取得できる                     |
|  8 | `handle`                   | `handle` が取得できる                    |

---

## 6.4 `control_id + class_name`

生成例。

```python
dlg.child_window(control_id=1, class_name="Button")
```

### 生成条件

```text
- control_id が取得できる
- class_name が取得できる
```

### 備考

Win32では有力な候補として先頭に表示する。

---

## 6.5 `title + class_name`

生成例。

```python
dlg.child_window(title="OK", class_name="Button")
```

### 生成条件

```text
- title/window_text が取得できる
- class_name が取得できる
```

### 備考

表示文言に依存するが、実務上利用頻度が高いため上位候補とする。

通常表示では、title依存のwarningは表示しない。

---

## 6.6 `control_id`

生成例。

```python
dlg.child_window(control_id=1)
```

### 生成条件

```text
- control_id が取得できる
```

### 備考

単独で一意になることもあるが、同じcontrol_idが別コンテナ配下に存在する可能性もあるため、ヒット件数確認の対象とする。

---

## 6.7 `class_name + found_index`

生成例。

```python
dlg.child_window(class_name="Button", found_index=3)
```

### 生成条件

```text
- class_name が取得できる
- class_name 単独候補が複数ヒットする
- 対象要素の found_index を算出できる
```

### warning

この候補には必ず以下のwarningを付与する。

```text
warning: found_index は画面構成や表示順の変更に弱い可能性があります
```

---

## 6.8 `title + found_index`

生成例。

```python
dlg.child_window(title="OK", found_index=2)
```

### 生成条件

```text
- title/window_text が取得できる
- title単独候補が複数ヒットする
- 対象要素の found_index を算出できる
```

### warning

この候補には必ず以下のwarningを付与する。

```text
warning: found_index は画面構成や表示順の変更に弱い可能性があります
```

---

## 6.9 `class_name`

生成例。

```python
dlg.child_window(class_name="Button")
```

### 生成条件

```text
- class_name が取得できる
```

### 備考

複数ヒットしやすい候補である。
ただし、画面によっては一意になることもあるため候補として表示する。

---

## 6.10 `title`

生成例。

```python
dlg.child_window(title="OK")
```

### 生成条件

```text
- title/window_text が取得できる
```

### 備考

表示文言に依存するが、実務上利用する可能性があるため候補として表示する。

---

## 6.11 `handle`

生成例。

```python
dlg.child_window(handle=0x00123456)
```

### 生成条件

```text
- handle が取得できる
```

### 表示順

handle候補は、常にWin32候補の最後に表示する。

### warning

この候補には必ず以下のwarningを付与する。

```text
warning: handle はアプリ起動ごとに変わる可能性があります
```

---

# 7. UIA Backend向け候補生成

## 7.1 基本方針

UIA Backendでは、以下の属性を主に使用する。

```text
- automation_id / auto_id
- control_type
- title
- title_re
- found_index
```

UIA Backendでは、`auto_id` と `control_type` の組み合わせを優先する。

---

## 7.2 UIA候補の生成順

UIA Backendでは、以下の順で候補を生成する。

```python
dlg.child_window(auto_id="...", control_type="...")
dlg.child_window(title="...", auto_id="...", control_type="...")
dlg.child_window(auto_id="...")
dlg.child_window(title="...", control_type="...")
dlg.child_window(title_re="^...$", control_type="...")
dlg.child_window(control_type="...", found_index=N)
dlg.child_window(title="...")
```

## 7.3 UIA候補の優先順位

| 順位 | 候補                               | 生成条件                                            |
| -: | -------------------------------- | ----------------------------------------------- |
|  1 | `auto_id + control_type`         | `automation_id` と `control_type` が取得できる         |
|  2 | `title + auto_id + control_type` | `title`, `automation_id`, `control_type` が取得できる |
|  3 | `auto_id`                        | `automation_id` が取得できる                          |
|  4 | `title + control_type`           | `title` と `control_type` が取得できる                 |
|  5 | `title_re + control_type`        | `title` と `control_type` が取得できる                 |
|  6 | `control_type + found_index`     | `control_type` が取得でき、同一control_type候補が複数ある      |
|  7 | `title`                          | `title` が取得できる                                  |

---

## 7.4 `auto_id + control_type`

生成例。

```python
dlg.child_window(auto_id="num1Button", control_type="Button")
```

### 生成条件

```text
- automation_id が取得できる
- control_type が取得できる
```

### 備考

UIAにおける有力候補として先頭に表示する。

---

## 7.5 `title + auto_id + control_type`

生成例。

```python
dlg.child_window(title="1", auto_id="num1Button", control_type="Button")
```

### 生成条件

```text
- title/window_text が取得できる
- automation_id が取得できる
- control_type が取得できる
```

### 備考

条件が多いため一意になりやすいが、titleに依存する。

通常表示では、title依存のwarningは表示しない。

---

## 7.6 `auto_id`

生成例。

```python
dlg.child_window(auto_id="num1Button")
```

### 生成条件

```text
- automation_id が取得できる
```

### 備考

`auto_id` 単独で一意になる場合もあるため候補に含める。

---

## 7.7 `title + control_type`

生成例。

```python
dlg.child_window(title="OK", control_type="Button")
```

### 生成条件

```text
- title/window_text が取得できる
- control_type が取得できる
```

---

## 7.8 `title_re + control_type`

生成例。

```python
dlg.child_window(title_re="^OK$", control_type="Button")
```

### 生成条件

```text
- title/window_text が取得できる
- control_type が取得できる
```

### 正規表現生成ルール

完全一致相当の正規表現として生成する。

```text
^<escaped title>$
```

例。

```python
dlg.child_window(title_re="^OK$", control_type="Button")
```

### 備考

`title_re` は、今後部分一致や可変文言に対応したい場合の候補として出力する。

初期版では完全一致形式のみ生成する。

---

## 7.9 `control_type + found_index`

生成例。

```python
dlg.child_window(control_type="Button", found_index=3)
```

### 生成条件

```text
- control_type が取得できる
- control_type 単独候補が複数ヒットする
- 対象要素の found_index を算出できる
```

### warning

この候補には必ず以下のwarningを付与する。

```text
warning: found_index は画面構成や表示順の変更に弱い可能性があります
```

---

## 7.10 `title`

生成例。

```python
dlg.child_window(title="OK")
```

### 生成条件

```text
- title/window_text が取得できる
```

---

# 8. found_index算出仕様

## 8.1 目的

`found_index` は、同じ属性条件に一致する要素が複数存在する場合に、対象要素の位置を指定するために使用する。

## 8.2 基本方針

`found_index` は、他の属性だけでは複数ヒットする候補に対して補助的に使用する。

`found_index` を使った候補は、必ずwarningを表示する。

## 8.3 算出方法

対象トップレベルウィンドウ配下で、同じ条件に一致する要素一覧を取得する。

その一覧の中で、対象要素と同一と判断できる要素のインデックスを `found_index` とする。

```text
found_index = 一致要素一覧内での対象要素の0始まり位置
```

## 8.4 同一要素の判定

同一要素かどうかは、可能な範囲で以下の属性を用いて判断する。

### Win32

```text
1. handle
2. rectangle
3. control_id + class_name + window_text
```

### UIA

```text
1. runtime_id
2. rectangle
3. automation_id + control_type + window_text
```

`runtime_id` が取得できない場合は、rectangleや属性の組み合わせで判定する。

## 8.5 算出できない場合

`found_index` を算出できない場合、その候補は生成しない。

推測で `found_index` を生成してはならない。

---

# 9. ヒット件数評価仕様

## 9.1 目的

各セレクター候補について、探索範囲内で何件のUI要素がヒットするかを評価する。

表示例。

```text
[1] hits: 1
    dlg.child_window(control_id=1, class_name="Button")
```

## 9.2 探索範囲

ヒット件数の探索範囲は、`--scope` によって決定する。

| `--scope` | 探索範囲                   |
| --------- | ---------------------- |
| `window`  | 対象要素が所属するトップレベルウィンドウ配下 |
| `desktop` | デスクトップ全体               |

既定は `window` とする。

## 9.3 評価対象

候補ごとに、内部的な検索条件を使って一致要素数を算出する。

例。

```python
dlg.child_window(control_id=1, class_name="Button")
```

この候補であれば、対象ウィンドウ配下から `control_id=1` かつ `class_name="Button"` に一致する要素数を数える。

## 9.4 found_index付き候補のヒット件数

`found_index` 付き候補は、セレクター自体としては通常1件に解決される。

そのため、表示する `hits` は、`found_index` を含めたセレクターとしてのヒット件数とする。

例。

```text
[4] hits: 1
    dlg.child_window(class_name="Button", found_index=3)
    warning: found_index は画面構成や表示順の変更に弱い可能性があります
```

ただし、`found_index` の安定性には注意が必要なため、必ずwarningを表示する。

## 9.5 handle候補のヒット件数

`handle` 候補は、該当handleが存在すれば通常1件になる。

例。

```text
[8] hits: 1
    dlg.child_window(handle=0x00123456)
    warning: handle はアプリ起動ごとに変わる可能性があります
```

handle候補はヒット件数が1であっても、常にwarningを表示する。

## 9.6 評価失敗

セレクター評価に失敗した場合、ヒット件数は `(Error)` と表示する。

```text
[1] hits: (Error)
    dlg.child_window(control_id=1, class_name="Button")
    warning: セレクター評価に失敗しました
```

## 9.7 タイムアウト

評価がタイムアウトした場合、ヒット件数は `(Timeout)` と表示する。

```text
[1] hits: (Timeout)
    dlg.child_window(class_name="Button")
    warning: セレクター評価がタイムアウトしました
```

## 9.8 探索上限

`--max-items` に達した場合、ヒット件数が実際より少ない可能性がある。

この場合はwarningを表示する。

```text
warning: 探索上限に達したため、ヒット件数が実際より少ない可能性があります
```

---

# 10. warning判定仕様

## 10.1 基本方針

warningは、候補の採用時に注意が必要な場合のみ表示する。

通常候補には説明やreasonを表示しない。

---

## 10.2 warning条件一覧

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

## 10.3 warningの複数表示

1つの候補に複数のwarningが該当する場合は、複数行で表示する。

```text
[4] hits: 5
    dlg.child_window(class_name="Button", found_index=2)
    warning: 複数要素にヒットします
    warning: found_index は画面構成や表示順の変更に弱い可能性があります
```

## 10.4 title / window_text依存のwarning

`title` または `window_text` を使用している候補については、通常表示ではwarningを出さない。

理由は、Windowsアプリでは表示文字列を使ったセレクターが頻出し、常にwarningを表示すると一覧性が下がるためである。

ただし、`--detail` 指定時は以下のwarningを表示してもよい。

```text
warning: title/window_text は表示文言変更の影響を受ける可能性があります
```

---

# 11. 候補の重複排除

## 11.1 基本方針

同一の `selector_text` を持つ候補は、重複表示しない。

## 11.2 重複判定

以下が完全一致する場合、同一候補とみなす。

```text
- backend
- selector_text
```

## 11.3 重複時の扱い

重複候補が生成された場合は、先に生成された候補を残す。

後から生成された重複候補は破棄する。

---

# 12. 候補の最大件数

## 12.1 基本方針

候補数が多すぎると一覧性が下がるため、バックエンドごとに表示件数の上限を設けてもよい。

## 12.2 初期上限

初期版では、バックエンドごとの候補表示数は最大10件程度を目安とする。

```text
Win32: 最大10件
UIA: 最大10件
```

## 12.3 上限を超える場合

上限を超えた候補は表示しない。

ただし、handle候補は生成された場合、常に最後に表示する。

---

# 13. コードスニペット用候補選択

## 13.1 基本方針

`[Code Snippet]` では、各バックエンドの候補一覧から1つを選び、対象要素取得までの最小コードを表示する。

## 13.2 選択ルール

コードスニペットに使う候補は、以下の順で選ぶ。

```text
1. hits = 1 かつ warningがない候補
2. hits = 1 かつ warningがfound_indexのみの候補
3. hits = 1 かつ warningがhandleのみの候補
4. 先頭候補
```

ただし、候補の採用理由は表示しない。

## 13.3 コードスニペット例

Win32。

```python
from pywinauto import Desktop

dlg = Desktop(backend="win32").window(title="電卓")
target = dlg.child_window(control_id=1, class_name="Button")
target.click()
```

UIA。

```python
from pywinauto import Desktop

dlg = Desktop(backend="uia").window(title="電卓")
target = dlg.child_window(auto_id="num1Button", control_type="Button")
target.click()
```

---

# 14. 生成例

## 14.1 Win32要素の例

入力情報。

```text
window_text: OK
class_name: Button
control_id: 1
handle: 0x00123456
```

生成候補。

```text
[Selector Candidates - Win32]

[1] hits: 1
    dlg.child_window(control_id=1, class_name="Button")

[2] hits: 1
    dlg.child_window(title="OK", class_name="Button")

[3] hits: 1
    dlg.child_window(control_id=1)

[4] hits: 5
    dlg.child_window(class_name="Button")
    warning: 複数要素にヒットします

[5] hits: 1
    dlg.child_window(handle=0x00123456)
    warning: handle はアプリ起動ごとに変わる可能性があります
```

---

## 14.2 UIA要素の例

入力情報。

```text
window_text: 1
control_type: Button
automation_id: num1Button
```

生成候補。

```text
[Selector Candidates - UIA]

[1] hits: 1
    dlg.child_window(auto_id="num1Button", control_type="Button")

[2] hits: 1
    dlg.child_window(title="1", auto_id="num1Button", control_type="Button")

[3] hits: 1
    dlg.child_window(auto_id="num1Button")

[4] hits: 1
    dlg.child_window(title="1", control_type="Button")

[5] hits: 1
    dlg.child_window(title_re="^1$", control_type="Button")

[6] hits: 24
    dlg.child_window(control_type="Button")
    warning: 複数要素にヒットします
```

---

## 14.3 found_index候補の例

入力情報。

```text
class_name: Button
class_name単独では5件ヒット
対象要素は4番目
```

生成候補。

```text
[Selector Candidates - Win32]

[1] hits: 5
    dlg.child_window(class_name="Button")
    warning: 複数要素にヒットします

[2] hits: 1
    dlg.child_window(class_name="Button", found_index=3)
    warning: found_index は画面構成や表示順の変更に弱い可能性があります
```

---

# 15. 実装時の注意

## 15.1 推測で候補を作らない

取得できない属性を推測して候補を生成してはならない。

例。

```text
automation_id が取得できないのに auto_id 候補を生成しない
control_id が取得できないのに control_id 候補を生成しない
```

## 15.2 バックエンドを混在させない

Win32 Backendで取得した属性と、UIA Backendで取得した属性を混ぜて1つの候補を作らない。

悪い例。

```python
dlg.child_window(control_id=1, control_type="Button")
```

`control_id` はWin32由来、`control_type` はUIA由来であり、バックエンド混在のため避ける。

## 15.3 handleを上位にしない

handle候補は、ヒット件数が1であっても最上位に表示しない。

常に最下位に表示する。

## 15.4 hitsだけで判断しない

本ツールは候補とヒット件数を表示するが、候補の最終採用はユーザーが判断する。

特に以下は、`hits = 1` でも注意が必要である。

```text
- found_index を使用する候補
- handle を使用する候補
- title/window_text に依存する候補
```

ただし、通常表示ではtitle依存のwarningは表示しない。
