# pyselector inspect オーバーレイ方式への改修計画

## 1. 改修目的

現在の `inspect` は、実行後に5秒カウントダウンし、終了時点のマウス座標から要素を取得している。

この方式を廃止し、次の操作に変更する。

```text
pyselector または pyselector inspect を実行
  ↓
画面全体に半透明オーバーレイを表示
  ↓
マウス位置に十字線を表示
  ↓
ユーザーが対象位置を左クリック
  ↓
クリック座標を記録
  ↓
オーバーレイを即座に閉じる
  ↓
その座標の要素を pywinauto で取得
  ↓
要素情報・候補セレクターを出力
```

`pick` のような新サブコマンドは追加しない。
**既存の `inspect` の体験を置き換える**方針にする。

---

# 2. 最終的なコマンド仕様

## 基本コマンド

```bash
pyselector
```

上記は以下と同じ動作にする。

```bash
pyselector inspect
```

## inspect コマンド

```bash
pyselector inspect
```

実行すると、オーバーレイによるクリック選択モードを開始する。

## backend 指定

既存仕様に合わせて、必要なら次を維持する。

```bash
pyselector inspect --backend uia
pyselector inspect --backend win32
pyselector inspect --backend both
```

デフォルトは、既存仕様に合わせる。
まだ未確定なら `uia` をデフォルトにするのが無難。

```text
default backend = uia
```

## 廃止する仕様

次は廃止する。

```text
5秒カウントダウン
カウントダウン終了時点のマウス座標取得
--delay
--countdown
```

既に `--delay` や `--countdown` が存在する場合は、すぐ削除してもよいが、既存利用者がいるなら一時的に警告扱いにする。

```text
Warning: countdown-based inspect has been removed. Overlay click selection is now used.
```

---

# 3. 操作仕様

## 対応操作

| 操作    | 動作                      |
| ----- | ----------------------- |
| 左クリック | クリック位置を確定し、即座に要素取得を開始する |
| Esc   | キャンセルして終了する             |

## 対応しない操作

| 操作        | 方針             |
| --------- | -------------- |
| Enter     | 確定操作として使わない    |
| Backspace | キャンセル操作として使わない |

ユーザーにとっては、**クリックしたらすぐ取得開始**に見えることを重視する。

内部的には、クリック直後に座標だけ保存して、オーバーレイを閉じてから `from_point()` を実行する。

```text
クリック
  ↓
座標保存
  ↓
オーバーレイ終了
  ↓
短い待機
  ↓
Desktop(...).from_point(x, y)
```

この短い待機は、オーバーレイ自身をpywinautoが拾わないようにするためのもの。

---

# 4. 推奨アーキテクチャ

既存構成が不明なので、責務ベースで分ける。

```text
pyselector/
  cli.py
  commands/
    inspect.py
  overlay/
    selector_overlay.py
  core/
    element_inspector.py
    selector_generator.py
    output_formatter.py
  utils/
    dpi.py
    errors.py
```

## `cli.py`

責務。

```text
pyselector 単体実行時に inspect を呼び出す
pyselector inspect を定義する
backend / output / verbose などのオプションを受け取る
```

改修内容。

```text
pyselector のデフォルトコマンドを inspect にする
pick は追加しない
countdown 関連オプションを削除または非推奨化する
```

---

## `commands/inspect.py`

責務。

```text
inspect コマンドの全体制御
オーバーレイ起動
クリック座標の受け取り
pywinautoによる要素取得
結果出力
```

処理イメージ。

```python
def run_inspect(args):
    setup_dpi_awareness()

    point = show_overlay_and_wait_for_click()

    if point is None:
        return 1

    x, y = point

    result = inspect_element_at_point(
        x=x,
        y=y,
        backend=args.backend,
    )

    print_result(result, output=args.output)

    return 0
```

---

## `overlay/selector_overlay.py`

責務。

```text
全モニターを覆う半透明オーバーレイを表示する
マウス位置に十字線を描画する
左クリック座標を取得する
Escキャンセルを扱う
クリック後は即座に閉じる
```

推奨ライブラリは `PySide6`。

理由は、半透明ウィンドウ、フルスクリーン、独自描画、マルチモニター対応がやりやすいため。

最低限のインターフェースはこう。

```python
def select_point_with_overlay() -> tuple[int, int] | None:
    """
    Returns:
        (x, y): left click position in screen coordinates
        None: canceled
    """
```

ここはpywinautoに依存させない方がいい。
ただの「座標選択UI」として分離する。

---

## `core/element_inspector.py`

責務。

```text
座標からpywinauto要素を取得する
backendごとの差異を吸収する
取得失敗時のエラーを整理する
```

処理イメージ。

```python
from pywinauto import Desktop

def inspect_element_at_point(x: int, y: int, backend: str):
    if backend == "both":
        return {
            "uia": inspect_with_backend(x, y, "uia"),
            "win32": inspect_with_backend(x, y, "win32"),
        }

    return {
        backend: inspect_with_backend(x, y, backend),
    }


def inspect_with_backend(x: int, y: int, backend: str):
    desktop = Desktop(backend=backend)
    element = desktop.from_point(x, y)

    return build_element_result(element, x, y, backend)
```

---

## `core/selector_generator.py`

責務。

```text
取得した要素から候補セレクターを生成する
親階層をたどる
auto_id / title / control_type / class_name / control_id などを組み合わせる
```

この改修では、セレクター生成ロジック自体は原則変更しない。
入力が「カウントダウン終了時の座標」から「クリック座標」に変わるだけ。

ただし、オーバーレイ方式に変えることでクリック対象が明確になるので、出力の先頭にクリック座標を出すとよい。

```text
[Point]
x=1234
y=567
```

---

## `utils/dpi.py`

責務。

```text
WindowsのDPIスケーリングによる座標ズレを抑える
```

起動直後にDPI awarenessを設定する。

候補。

```python
import ctypes

def setup_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
```

DPI問題は後から妙なバグになりがち。
少しだけ地味だけど、ここは最初に入れておいた方がいい。

---

# 5. 実装ステップ

## Step 1: 既存 inspect 処理の整理

目的。

```text
現在のカウントダウン処理と要素取得処理を分離する
```

作業。

```text
カウントダウン処理の場所を特定する
マウス座標取得処理を特定する
座標から要素取得する処理を関数化する
出力処理を関数化する
```

この時点で、次の形にしておく。

```python
point = get_point_somehow()
result = inspect_element_at_point(point.x, point.y, backend)
print_result(result)
```

この `get_point_somehow()` を後でオーバーレイに置き換える。

---

## Step 2: カウントダウン処理の廃止

目的。

```text
5秒待機方式を削除する
```

作業。

```text
time.sleep(5) 等の待機処理を削除
カウントダウン表示を削除
--delay / --countdown があれば削除または非推奨化
関連テストを削除または更新
```

移行期間を設けるなら、オプションは残して警告だけ出す。

```text
--delay is ignored because inspect now uses overlay click selection.
```

ただし、社内ツールなら最初から削除でもいいと思う。
この手の互換性は、過保護にすると仕様が濁ることがある。

---

## Step 3: オーバーレイUIの追加

目的。

```text
クリック座標を取得するための透明オーバーレイを実装する
```

作業。

```text
PySide6を依存関係に追加
全モニターを覆うオーバーレイウィンドウを表示
半透明マスクを描画
マウス位置に縦横の十字線を描画
左クリック時にグローバル座標を保存
クリック後に即座にオーバーレイを閉じる
Escでキャンセル可能にする
```

最低限の見た目。

```text
画面全体: 薄い黒または灰色の半透明マスク
マウス位置: 縦線・横線
カーソル: 通常カーソルまたはクロスカーソル
```

最初から凝りすぎなくていい。
大事なのは「どこを選んでいるか分かること」。

---

## Step 4: inspect コマンドに統合

目的。

```text
pyselector / pyselector inspect からオーバーレイ方式を起動する
```

作業。

```text
pyselector 単体実行時に inspect を呼び出す
inspect 実行時に select_point_with_overlay() を呼び出す
クリック座標取得後、オーバーレイ終了を待つ
短い待機を入れる
Desktop(...).from_point(x, y) を実行する
結果を出力する
```

内部フロー。

```python
point = select_point_with_overlay()

if point is None:
    return 1

x, y = point

time.sleep(0.05)

result = inspect_element_at_point(x, y, backend)

print_result(result)
```

`time.sleep(0.05)` は定数化しておくとよい。

```python
OVERLAY_CLOSE_WAIT_SECONDS = 0.05
```

---

## Step 5: 出力内容の確認・調整

目的。

```text
クリック方式になっても既存の出力体験を壊さない
```

出力に含めるもの。

```text
クリック座標
backend
対象要素の基本情報
親階層
候補セレクター
取得失敗時の理由
```

例。

```text
[Point]
x=1240
y=582

[Backend]
uia

[Element]
name="OK"
control_type="Button"
automation_id="btnOK"
class_name="Button"
rectangle=(1201, 560, 1288, 594)

[Selector Candidates]
1. app.window(title="設定").child_window(auto_id="btnOK", control_type="Button")
2. app.window(title_re=".*設定.*").child_window(title="OK", control_type="Button")
3. parent.child_window(auto_id="btnOK")
```

---

# 6. テスト計画

## 単体テスト

対象。

```text
inspect_element_at_point()
出力フォーマッター
backend指定の分岐
キャンセル時の終了コード
CLI引数解釈
```

観点。

```text
backend=uia
backend=win32
backend=both
クリックキャンセル時
要素取得失敗時
出力形式 text/json
```

オーバーレイ自体はGUIなので、完全な自動テストは難しい。
ここはロジックを分離して、座標選択部分をモックできるようにする。

```python
def run_inspect(args, point_selector=select_point_with_overlay):
    point = point_selector()
```

こうしておけば、テストでは疑似座標を返せる。

---

## 手動テスト

最低限、以下は確認する。

| No | 観点                      | 期待結果                  |
| -- | ----------------------- | --------------------- |
| 1  | `pyselector` 単体起動       | オーバーレイが表示される          |
| 2  | `pyselector inspect` 起動 | オーバーレイが表示される          |
| 3  | 左クリック                   | 即座にオーバーレイが閉じ、要素取得が始まる |
| 4  | Enter押下                 | 確定されない                |
| 5  | Backspace押下             | キャンセルされない             |
| 6  | Esc押下                   | キャンセル終了する             |
| 7  | `--backend uia`         | UIAで取得される             |
| 8  | `--backend win32`       | Win32で取得される           |
| 9  | `--backend both`        | 両方の取得結果が出る            |
| 10 | 125% / 150% DPI         | 座標ズレが大きくない            |
| 11 | マルチモニター                 | どの画面でもクリック座標を取得できる    |
| 12 | 管理者権限アプリ                | 必要に応じて権限差による失敗を説明できる  |

---

# 7. 受け入れ条件

この改修の完了条件は、次でよい。

```text
pyselector 単体で inspect が起動する
pyselector inspect でも同じ動作になる
カウントダウンが表示されない
画面全体に半透明オーバーレイが表示される
マウス位置に十字線が表示される
左クリックすると確認なしで即座に要素取得が始まる
Enterでは確定されない
Backspaceではキャンセルされない
クリックした座標に対して pywinauto の from_point が実行される
取得結果として要素情報・親階層・候補セレクターが表示される
Escでキャンセルできる
```

---

# 8. 主なリスクと対策

## リスク1: オーバーレイ自身を取得してしまう

対策。

```text
クリック時点では座標のみ保存する
オーバーレイを閉じる
50ms程度待つ
その後 from_point() を実行する
```

---

## リスク2: DPIスケーリングで座標がズレる

対策。

```text
プロセス起動直後にDPI awarenessを設定する
100% / 125% / 150% で手動確認する
```

---

## リスク3: マルチモニターで片方にしかオーバーレイが出ない

対策。

```text
Qtのscreen一覧を使って全スクリーンを覆う
または仮想デスクトップ全体のgeometryを使う
```

---

## リスク4: 管理者権限アプリの要素が取れない

対策。

```text
ツール側も管理者権限で起動する必要があることをエラーメッセージに出す
```

例。

```text
Element access failed. If the target application is running as administrator, run pyselector as administrator.
```

---

## リスク5: RDPや仮想環境で座標・表示が不安定

対策。

```text
RDP接続中の表示状態で手動確認する
RDP切断中は対象外または制約として明記する
```

---

# 9. 実装優先順位

おすすめの順番はこれ。

```text
1. inspect の座標取得処理を差し替え可能にする
2. カウントダウン処理を削除する
3. PySide6オーバーレイでクリック座標を取得する
4. inspect に統合する
5. DPI awareness を入れる
6. マルチモニター対応を確認する
7. 出力・エラーメッセージを整える
8. テストとREADMEを更新する
```

最初からハイライトや高度なショートカットは入れなくていい。
まずは「クリックして即取得」が成立することを優先する。

---

# 10. 実装担当AIエージェント向け指示案

そのまま渡すなら、こんな指示でよさそう。

```markdown
# 改修指示: inspect コマンドをオーバーレイ方式に変更する

## 目的

`pyselector` / `pyselector inspect` の実行時に、従来の5秒カウントダウン方式を廃止し、画面全体の半透明オーバーレイ上でクリックした座標から要素を取得する方式へ変更する。

## 方針

- `pick` などの新サブコマンドは追加しない。
- `pyselector` 単体実行時は `pyselector inspect` と同じ動作にする。
- `inspect` は起動後すぐにオーバーレイを表示する。
- オーバーレイには現在のマウス位置に追従する十字線を表示する。
- 左クリックしたら、その座標を確定し、確認操作なしで即座に取得処理を開始する。
- Enterによる確定は実装しない。
- Backspaceによるキャンセルは実装しない。
- Escによるキャンセルは実装してよい。
- クリック時には座標だけを保存し、オーバーレイを閉じた後に `pywinauto.Desktop(...).from_point(x, y)` を実行する。
- カウントダウン表示とカウントダウン待機は削除する。

## 受け入れ条件

- `pyselector` でオーバーレイが起動する。
- `pyselector inspect` でオーバーレイが起動する。
- カウントダウンは表示されない。
- 左クリックするとオーバーレイが閉じ、クリック座標の要素取得が始まる。
- Enterを押しても確定されない。
- Backspaceを押してもキャンセルされない。
- 取得結果にクリック座標、要素情報、候補セレクターが出力される。
```
