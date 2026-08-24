# pyselector テスト実装支援モード 追加計画

`docs/09_agent_mode_plan.md` で「エージェントが要素を探せる」ところまで到達した。本計画は、その次の段階、**エージェントが pywinauto の自動テストを最後まで書き切れる**ようにするための追加設計である。

Microsoft の [AutoGenesis](https://github.com/microsoft/autogenesis)（MCP ベースの AI 自動テストフレームワーク）を調査し、pyselector に欠けている能力を洗い出した結果を出発点にしている。

---

## 1. 改修目的

現在の pyselector でエージェントができるのは、次の 3 つである。

```text
ウィンドウを見つける     windows
要素を絞り込む           find / tree
セレクターを確定する     inspect --with-selectors
UI を操作して画面を進める act
```

しかしこれは「調べる」までであって、「テストを書く」ではない。テストとして成立するために足りないものが 4 つある。

| テストに必要な要素 | 現状 |
| --- | --- |
| **前提条件を作る**（アプリを起動して既知の状態にする） | 手段が無い。人があらかじめ開いておく前提 |
| **画面の変化を待つ** | 手段が無い。`find` は一発走査のみ |
| **結果を検証する** | 手段が無い。要素の値・チェック状態を取得すらできない |
| **手順をコードとして残す** | 要素 1 個ずつのスニペットのみ。一連の操作をまとめる機構が無い |

エージェントが今できるのは、**探索して、断片的なスニペットを人に渡す**ところまでである。探索の成果が一本の実行可能なテストにならず、最後の組み立てが人の手作業として残っている。

本計画は、この 4 つを埋めて次のループを閉じる。

```text
アプリを起動する（launch）
  ↓
要素を探す（windows / find / inspect）
  ↓
操作する（act）
  ↓
画面が変わるのを待つ（--wait）
  ↓
結果を検証する（expect）
  ↓
ここまでの手順を pywinauto コードとして書き出す（record）
```

---

## 2. AutoGenesis 調査から得た判断

### 2.1 参考にする点

AutoGenesis は `.feature`（Gherkin）のシナリオをエージェントに読ませ、MCP ツールを 1 ステップずつ叩かせ、**成功したツール呼び出しを記録して**、最後に behave の step 定義ファイルを生成する。

この「**探索の副産物として実行可能なコードが残る**」という発想が中核であり、pyselector に最も欠けているものである。本計画の `record` はこれに対応する。

そのほか、次の機能が pyselector に無い形で存在していた。

| AutoGenesis | pyselector | 本計画での対応 |
| --- | --- | --- |
| `app_launch` / `app_close` / `app_wait` | 無し | `launch` / `close` |
| `element.exists(timeout=N)` | 無し（一発走査） | `--wait` / `--wait-gone` / `--settle` |
| `verify_element_exists` / `verify_element_value` / `verify_checkbox_state` | 無し | `expect` |
| `get_value()` / `get_toggle_state()` の取得 | `ElementInfo` に無い | 状態属性の追加 |
| `app_screenshot` | 無し | `shot` |
| `before_gen_code` / `preview_code_changes` / `confirm_code_changes` | 無し | `record start` / `show` / `stop` |

### 2.2 参考にしない点

**生成コードが MCP 呼び出しの再生になっている。** AutoGenesis が生成する step 定義には pywinauto が一行も入らない。

```python
# AutoGenesis が生成するコード
@when('I click the search box in NTP page')
def step_impl(context):
    result = call_tool_sync(context, context.session.call_tool(
        name="element_click",
        arguments={'name': '...', 'control_type': 'Edit', ...}
    ))
    assert result_json.get("status") == "success", ...
```

生成物は「MCP ツール呼び出しの再生スクリプト」であり、テストの実行時にも MCP サーバーと `.vscode/mcp.json` が必要になる。`docs/10 §1.1` で MCP への依存を避けた pyselector が、テストのランタイムにまでその依存を持ち込むのは筋が通らない。

**したがって `record` の生成物は素の pywinauto コードとする。生成されたテストは pyselector がインストールされていない環境で動く。** これは既存の `[Code Snippet]`（調べた結果を自分のコードに貼る）の思想の延長であり、本計画で最も重要な設計判断である。

そのほか、次は取り入れない。

- **BDD / behave への結合**: フレームワーク中立を保つ。生成形式は `--emit` で選ばせる。
- **サーバー内での LLM による画面判定**（`verify_visual_task`）: 呼び出し側が既に LLM である。pyselector は PNG を渡すところまでを担い、判定はしない。
- **全ツール呼び出しが全ツリーのスナップショットを返す設計**（`need_snapshot=1` が既定、上限 800KB）: 出力量の制御は pyselector の既存の強みであり、崩さない。
- **「成功するまで別手段を試し続けろ」という指示**: 実デスクトップを操作するツールでは危険である。理解できていない画面に対して代替手段を試し続けるエージェントは、誤った要素を操作する。

---

## 3. 設計方針

### 3.1 既存の契約を壊さない

追加するコマンドとオプションはすべて加算であり、既存コマンドの出力キーの削除・改名は行わない。`schema_version` は `2` のまま据え置き、キーの追加のみで対応する（`docs/09 §5.1` の方針を継続）。

### 3.2 状態の取得コストは出力量に比例させる

要素の状態（値・チェック状態）は UIA のパターン呼び出しを伴い、1 要素あたりのコストが無視できない。`walk_elements` は 200 要素以上を走査するため、**全走査要素に対して状態を読むと探索が目に見えて遅くなる**。

そこで、走査（`element_from_wrapper`）には手を入れず、**出力対象が確定した後に必要な要素だけ状態を読む**。読む対象は次に限る。

```text
inspect      対象要素 1 個
act          操作対象と操作後の要素
expect       判定に必要な要素
find         --with-state を付けたときの、--limit 適用後の一致要素のみ
tree         読まない（ノード数が多すぎる）
```

このため `BackendInspector` に `read_element_state()` を追加する（`§5.1`）。

### 3.3 書き込み系はすべて `act` と同じ関門を通す

新設コマンドのうち、デスクトップの状態を変えるのは `launch` と `close` である。これらは `act` と**同じ 2 段階の許可**（`.env` の `PYSELECTOR_ALLOW_ACTIONS=true` と `--allow-actions`）を要求する。

任意の実行ファイルを起動することは、ボタンを 1 つ押すことより影響が小さいとは言えない。関門を増やすと利用者が覚えることが増えるだけなので、**スイッチは 1 つのまま**にする。

読み取り専用のコマンド（`expect` / `shot` / `record` / `batch` そのもの）に関門は要らない。`batch` は各ステップを既存のコマンドとして実行するため、`act` を含むバッチは `act` の関門にそのまま従う。

### 3.4 記録は 1 ユーザーにつき 1 つ

デスクトップは共有資源であり、同時に 2 つの UI 操作シナリオを記録することは原理的にできない。したがって記録セッションはユーザーにつき 1 つとし、状態ファイルと同じ場所（`§7.2`）に置く。

---

## 4. コマンド一覧（追加分）

| コマンド | 用途 | 状態変更 |
| --- | --- | --- |
| `pyselector expect` | 要素の存在・件数・値・状態を検証する | 無し |
| `pyselector shot` | ウィンドウ / 要素 / 画面全体を PNG に撮る | 無し（ファイル出力のみ） |
| `pyselector launch` | アプリを起動して主ウィンドウを待つ | **あり** |
| `pyselector close` | ウィンドウを閉じる / プロセスを終了する | **あり** |
| `pyselector record` | 操作と検証を記録し、pywinauto コードを生成する | 無し（ファイル出力のみ） |
| `pyselector batch` | 複数コマンドを 1 プロセスで順に実行する | 各ステップに従う |

既存コマンドへの追加オプション。

| コマンド | 追加 |
| --- | --- |
| `find` | `--wait` / `--wait-gone` / `--with-state` |
| `act` | `--settle` / `--note` |
| `inspect` | （状態属性が自動的に付く） |

---

## 5. 要素の状態属性

### 5.1 `ElementInfo` への追加

```python
@dataclass(frozen=True)
class ElementInfo:
    ...
    value: str | None = None            # ValuePattern / get_value()
    is_checked: bool | None = None      # TogglePattern（CheckBox / RadioButton）
    is_selected: bool | None = None     # SelectionItemPattern（ListItem / TabItem）
    is_offscreen: bool | None = None    # 画面外にスクロールアウトしているか
    has_keyboard_focus: bool | None = None
```

いずれも取得できなければ `None`。「取得できなかった」と「値が無い」を区別しないのは既存の属性（`control_type` など）と同じ扱いである。

`is_checked` は UIA の 3 値トグル（off / on / indeterminate）を bool に落とすため、`indeterminate` は `None` とする。**「不定」を `False` と報告するとテストが誤って通る**ため、ここは意図的に情報を落とさない。

### 5.2 取得方法

`BackendInspector.read_element_state(element: ElementInfo) -> ElementInfo` を追加する。既存の wrapper キャッシュから wrapper を引き、`safe_call` で各パターンを試し、埋めた新しい `ElementInfo` を返す。

win32 バックエンドでは `value` に `window_text` 相当が入ることがあるが、UIA の `ValuePattern` とは意味が違うため、**win32 では `value` を埋めない**。埋めると「値が空欄なのにテキストが入っている」ような誤ったアサーションを誘発する。

### 5.3 出力

`--json` の `element` オブジェクトに、状態を読んだときだけ `state` オブジェクトが加わる。常に 5 キーを並べると「取得できなかった」と「読んでいない」が区別できなくなるため、有無そのものを情報にする。`--compact` では省く（compact は要素の同定に必要な最小限という位置づけを維持する）。

テキスト出力では、値が `None` でないものだけを `[Backend]` セクションに追加表示する。

---

## 6. `expect`：検証

### 6.1 位置づけ

エージェントが陥りやすい失敗は、**ツリーのダンプを自分で読んで「検証は通った」と判断すること**である。そのとき参照している情報は操作前の古いスナップショットかもしれず、読み違えもする。

`expect` は「判定をツールに戻す」ための入口である。判定条件をコマンドラインに書かせることで、何を検証したのかが記録に残り（`§7`）、そのままコードに変換できる。

### 6.2 構文

対象の指定は `find` と同じ（`--window-handle` / `--window-title` / `--at` / `--ref` のいずれか 1 つ + 絞り込み条件）。

```bash
pyselector expect --json --window-handle 0x2E20F46 --auto-id saveBtn --exists
pyselector expect --json --window-handle 0x2E20F46 --auto-id dialog --not-exists
pyselector expect --json --window-handle 0x2E20F46 --control-type Button --count 5
pyselector expect --json --window-handle 0x2E20F46 --auto-id nameBox --value-equals "山田"
pyselector expect --json --window-handle 0x2E20F46 --auto-id nameBox --value-contains "山"
pyselector expect --json --window-handle 0x2E20F46 --auto-id agree --checked
pyselector expect --json --window-handle 0x2E20F46 --auto-id submit --enabled
```

判定は**ちょうど 1 つ**指定する。

| 判定 | 意味 | 対象の一意性 |
| --- | --- | --- |
| `--exists` | 一致が 1 件以上 | 不要 |
| `--not-exists` | 一致が 0 件 | 不要 |
| `--count N` | 一致がちょうど N 件 | 不要 |
| `--value-equals TEXT` | 要素の `value` が完全一致 | **必要** |
| `--value-contains TEXT` | 要素の `value` に部分一致 | **必要** |
| `--checked` / `--unchecked` | `is_checked` | **必要** |
| `--enabled` / `--disabled` | `is_enabled` | **必要** |

「対象の一意性が必要」な判定で複数一致した場合は、`act` と同じく `ambiguous_target`（終了コード 6）で候補を提示する。`--index N` で選べる点も `act` と揃える。

### 6.3 出力と終了コード

**「判定が実行できたか」と「判定が満たされたか」は別物**として扱う。これは既存の「探索の成功とヒット 0 件は別物」（`docs/09 §5.3`）と同じ考え方である。

```text
status=success, satisfied=true   判定が成立した            終了コード 0
status=success, satisfied=false  判定は動いたが成立しない  終了コード 12
status=error                     判定そのものが実行できない（ウィンドウが無い等）
```

```json
{
  "schema_version": 2,
  "command": "expect",
  "status": "success",
  "served": false,
  "satisfied": false,
  "expectation": { "kind": "value_equals", "expected": "山田", "actual": "" },
  "matched": 1,
  "waited": 0.0,
  "attempts": 1,
  "results": [ { "backend": "uia", "matches": [ ... ] } ]
}
```

`EXIT_EXPECTATION_FAILED = 12` を追加する。エラーコード名は `expectation_failed`。

---

## 7. 待機

### 7.1 なぜ必要か

現在の `find` は一発走査であり、「クリック後にダイアログが出るまで待つ」手段が無い。AutoGenesis はクリックのたびに `sleep(2)` を固定で入れて凌いでいるが、これは遅い上に不安定である。

**待機の語彙が無いまま生成したコードは、必ず人が手で `wait` を足すことになる。** テスト生成の価値が最後の工程で失われるため、`record` より先にここを埋める。

### 7.2 追加するオプション

```bash
pyselector find   --json --window-handle 0x... --auto-id dialog --wait 5
pyselector find   --json --window-handle 0x... --auto-id spinner --wait-gone 5
pyselector expect --json --window-handle 0x... --auto-id result --value-equals "完了" --wait 10
pyselector act    --json --ref uia:7f3a2b:42 --click --allow-actions --settle 3 --diff
```

| オプション | 意味 |
| --- | --- |
| `find --wait SEC` | 一致が 1 件以上になるまで再走査を繰り返す |
| `find --wait-gone SEC` | 一致が 0 件になるまで再走査を繰り返す |
| `expect --wait SEC` | 判定が成立するまで再評価を繰り返す |
| `act --settle SEC` | 操作後、対象ウィンドウのツリーが変化しなくなるまで待つ |

- ポーリング間隔の既定は 0.3 秒（`wait.poll_interval` で変更可）。走査そのものが 1 秒近くかかるため、間隔を詰めても意味は無い。
- タイムアウトは実時間で測る。最後の試行の結果をそのまま返す（**タイムアウトはエラーにしない**。`find` なら 0 件、`expect` なら `satisfied=false` として返る）。
- 出力に `waited`（実際に待った秒数）と `attempts`（試行回数）を加える。1 回で決まったのか粘ったのかが記録に残り、生成コードの `timeout` 値の根拠になる。
- `--wait` と `--wait-gone` は排他。

`--settle` は「2 回連続で同じツリーが取れたら安定」と定義する。単なる固定 sleep ではないため、速い画面では即座に返る。`--diff` と併用したときは、安定してから操作後スナップショットを取る。

---

## 8. `record`：記録とコード生成

本計画の中心。

### 8.1 記録する対象

記録中は、次が成功したときに 1 エントリを追加する。

| コマンド | 記録するもの |
| --- | --- |
| `launch` | 実行ファイル・引数・待ったウィンドウタイトル |
| `act`（`--dry-run` を除く） | 操作種別・値・**解決済みセレクター**・対象要素・待機設定 |
| `expect` | 判定種別・期待値・**解決済みセレクター**・待機設定 |
| `close` | 対象ウィンドウ |

`find` や `tree` は記録しない。探索は手順ではなく、テストに残す必要が無いためである。

### 8.2 保存場所

```text
<state_dir>/recording.json
```

`state_dir()` は `pyselector/server/state.py` の既存実装（`%LOCALAPPDATA%\pyselector`、`PYSELECTOR_STATE_DIR` で差し替え可）を再利用する。`§3.4` のとおり同時に 1 つだけ存在する。

各コマンドは記録中かどうかをこのファイルの有無で判定する。ファイルが無ければ、記録に関する処理は一切行わない（**記録していないときのオーバーヘッドはファイルの存在確認 1 回のみ**）。

### 8.3 セレクターの記録が要点

`act` は現在、CLI に渡された条件（`--auto-id saveBtn` など）で要素を解決するが、**その条件をそのままコードにしても良いセレクターになるとは限らない**。`--text "保存"` のような条件は表示文言に依存し、`--index 2` は並び順に依存する。

そこで記録時には、解決済みの対象要素に対して既存の `_build_backend_inspection()` を実行し、**評価済みのセレクター候補から最良のもの**（`hits == 1` かつ警告が少ないもの）を選んで記録する。

これは `find --with-selectors` と同じ重い処理だが、**記録中のみ**実行される。記録していないときの `act` の速度は変わらない。

適切な候補が 1 つも無い場合は、その旨（`selector: null`, `selector_warning: "..."`）を記録し、生成コードにはコメントとして残して人に判断を委ねる。**推測でそれらしいコードを出力しない。**

### 8.4 コマンド

```bash
pyselector record start --name "保存フロー" [--json]
pyselector record status --json
pyselector record show --json
pyselector record stop --emit pytest --out tests/test_save_flow.py [--json]
pyselector record cancel
```

- `start`: 既に記録中なら `--force` が無い限り失敗する（意図しない上書きを防ぐ）。
- `show`: 記録内容をそのまま返す。生成前に「何が記録されたか」を確認するための入口。
- `stop --emit`: `pytest`（既定） / `plain` / `none`。`none` は記録を JSON のまま出す。
- `--out` を省略した場合は標準出力に出す。**既存ファイルを黙って上書きしない**（存在する場合は `--force` を要求する）。
- `cancel`: 生成せずに破棄する。

### 8.5 生成コード

`--emit pytest` の出力例。

```python
"""pyselector record が生成したテスト。

記録名: 保存フロー
生成日時: 2026-08-25T10:11:12
このファイルは pyselector に依存しません。pywinauto があれば実行できます。
"""

import pytest
from pywinauto import Application


APP_TITLE_RE = "^電卓$"


@pytest.fixture(scope="module")
def window():
    app = Application(backend="uia").start(r"calc.exe")
    main = Application(backend="uia").connect(title_re=APP_TITLE_RE).window(
        title_re=APP_TITLE_RE, control_type="Window"
    )
    main.wait("exists visible enabled", timeout=30)
    yield main


def test_保存フロー(window):
    # 1. click: "5"
    window.child_window(auto_id="num5Button", control_type="Button").click_input()

    # 2. click: "+"
    window.child_window(auto_id="plusButton", control_type="Button").click_input()

    # 3. click: "3"
    window.child_window(auto_id="num3Button", control_type="Button").click_input()

    # 4. click: "="
    window.child_window(auto_id="equalButton", control_type="Button").click_input()

    # 5. expect: value_equals
    assert window.child_window(auto_id="CalculatorResults", control_type="Text").window_text() == "表示は 8"
```

操作の対応表（`ActResult.method` に記録された、実際に成功した手段をそのまま使う）。

| 記録 | 生成 |
| --- | --- |
| `click` / `click_input` | `.click_input()` |
| `double_click` | `.double_click_input()` |
| `right_click` | `.right_click_input()` |
| `invoke` | `.invoke()` |
| `focus` | `.set_focus()` |
| `set_text` | `.set_edit_text("...")` |
| `send_keys` | `.type_keys("...", with_spaces=True)` |

判定の対応表。

| 記録 | 生成 |
| --- | --- |
| `exists` | `assert w.child_window(...).exists()` |
| `not_exists` | `assert not w.child_window(...).exists()` |
| `count` | `assert len(window.descendants(**kwargs)) == N` |
| `value_equals` | `assert w.child_window(...).get_value() == "..."` |
| `checked` | `assert w.child_window(...).get_toggle_state() == 1` |
| `enabled` | `assert w.child_window(...).is_enabled()` |

待機付きで記録されたものは `wait` に変換する。`find` は記録しないため、生成コードに
待機が入る経路は `expect --wait` だけである。

```python
# expect --auto-id dialog --exists --wait 5 として記録されたもの
window.child_window(auto_id="dialog").wait("exists", timeout=5)
# expect --auto-id spinner --not-exists --wait 5
window.child_window(auto_id="spinner").wait_not("exists", timeout=5)
```

`act --settle` は記録には残るが、コードは生成しない。「画面が落ち着くまで待つ」は
pyselector 側の概念で、pywinauto に対応する表現が無い。相当する待機を生成コードに
入れたければ、続けて `expect --wait` を書くこと。

`--emit plain` は pytest に依存しない単一スクリプト（`def main():` と `if __name__ == "__main__":`）を出す。

### 8.6 生成しないもの

- **記録に無い待機を推測で挿入しない。** 実際に `--wait` を使った箇所だけが `wait` になる。エージェントが待機を書かなかったなら、それはエージェントの手順の問題であり、生成器が埋めるべきものではない。
- **セレクターが確定していない操作を推測で埋めない**（`§8.3`）。

---

## 9. `launch` / `close`

### 9.1 `launch`

```bash
pyselector launch --json --exe "C:\Windows\System32\calc.exe" --wait-title-re "^電卓$" --allow-actions
pyselector launch --json --app calculator --allow-actions
pyselector launch --json --app calculator --dry-run
```

| オプション | 意味 |
| --- | --- |
| `--exe PATH` | 起動する実行ファイル |
| `--args ...` | 引数（`--` 以降をそのまま渡す） |
| `--app NAME` | 設定ファイルの `apps` セクションから引く |
| `--wait-title-re RE` | このタイトルの主ウィンドウが現れるまで待つ |
| `--timeout SEC` | 待機の上限（既定 30） |
| `--attach-existing` | 既に起動していれば起動せず接続する |
| `--dry-run` | 何を起動するかだけ報告する（許可不要） |

出力は起動したプロセスの `pid` と、見つかった主ウィンドウの `handle` / `title`。**この `handle` をそのまま以降のコマンドに渡せる**ことが `launch` の主な価値である。

`--wait-title-re` を省略した場合は、起動したプロセス ID に属する可視のトップレベルウィンドウが現れるまで待つ。

### 9.2 設定ファイル

```json
{
  "apps": {
    "calculator": {
      "exe": "calc.exe",
      "args": [],
      "window_title_re": "^電卓$",
      "timeout": 30
    }
  }
}
```

`apps` は他のセクションと違い任意のキーを持つ辞書なので、`_section()` とは別の検証関数を用意する。

### 9.3 `close`

```bash
pyselector close --json --window-handle 0x2E20F46 --allow-actions
pyselector close --json --window-handle 0x2E20F46 --force --allow-actions
```

既定は `wrapper.close()`（WM_CLOSE 相当）。`--force` はプロセスの終了。テストの後始末に必要なため用意するが、**保存確認ダイアログを潰してデータを失う可能性がある操作**なので、`--dry-run` を同様に用意し、SKILL では「利用者が明示的に頼んだときだけ使う」と書く。

---

## 10. `shot`：スクリーンショット

### 10.1 目的

要素ツリーは、自前描画のコントロール・アイコンだけのボタン・描画崩れを表現できない。マルチモーダルなエージェントにとって、ここは完全な死角になっている。

```bash
pyselector shot --json --window-handle 0x2E20F46 --out shot.png
pyselector shot --json --ref uia:7f3a2b:42 --out button.png
pyselector shot --json --at 636,2240 --out element.png
pyselector shot --json --screen --out desktop.png
```

### 10.2 `--annotate`

`find` と同じ条件を受け取り、**一致した要素に番号付きの枠を描き込む**。

```bash
pyselector shot --json --window-handle 0x2E20F46 --annotate --control-type Button --out buttons.png
```

JSON には番号と要素の対応が入る。

```json
{
  "path": "buttons.png",
  "annotations": [
    { "index": 1, "element": { "window_text": "保存", ... }, "rectangle": { ... } },
    { "index": 2, "element": { "window_text": "キャンセル", ... }, "rectangle": { ... } }
  ]
}
```

これで「画像の 3 番が探しているボタン」という形の対話が成立する。AutoGenesis には無く、pyselector の `find` の上に安く載る機能である。

### 10.3 実装上の注意

- `wrapper.capture_as_image()` は Pillow を必要とする。依存に `pillow` を追加する。
- 画面全体は `PIL.ImageGrab`。
- Pillow が無い環境では、明確なエラーメッセージ（`shot には pillow が必要です`）で失敗させる。他のコマンドは Pillow 無しで動き続ける（**遅延 import** とする）。
- `--out` は相対パスをクライアントの cwd 基準で解決する。常駐サーバーは要求ごとに cwd を移す（`server.py`）ため、ローカル実行と一致する。
- 既存ファイルは `--force` 無しでは上書きしない。

---

## 11. `batch`：複数コマンドの一括実行

### 11.1 目的

常駐モードが消したのはプロセス起動の 0.55 秒だが、**エージェントにとっての実コストは 1 コマンド = 1 ツール呼び出しの往復**である。5 手順の操作は 5 往復になる。

`batch` は複数コマンドを 1 回の呼び出しにまとめる。

```bash
pyselector batch --json steps.json
cat steps.json | pyselector batch --json -
```

```json
{
  "steps": [
    { "command": "act", "args": ["--ref", "uia:7f3a2b:42", "--click", "--allow-actions"] },
    { "command": "expect", "args": ["--window-handle", "0x2E20F46", "--auto-id", "dialog", "--exists", "--wait", "5"] }
  ]
}
```

出力は各ステップのエンベロープを順に格納した配列。

```json
{
  "command": "batch",
  "status": "success",
  "completed": 2,
  "steps": [
    { "index": 0, "argv": [...], "exit_code": 0, "result": { ...act のエンベロープ... } },
    { "index": 1, "argv": [...], "exit_code": 0, "result": { ...expect のエンベロープ... } }
  ]
}
```

- 既定で最初の失敗（終了コード非 0）で停止する。`--continue-on-error` で最後まで走る。
- `batch` 全体の終了コードは、停止させた失敗ステップの終了コードをそのまま返す。全成功なら 0。
- `batch` / `serve` / `install-skills` はステップに指定できない（再帰と、対話的な処理の混入を防ぐ）。
- 各ステップは必ず `--json` として実行する。

### 11.2 変数展開は入れない

「前のステップの結果を次のステップの引数に埋め込む」（`{{steps.0.matches[0].ref}}` のような記法）は**意図的に実装しない**。

小さなテンプレート言語を発明することになり、その言語の仕様・エラー・デバッグ手段を維持する必要が出る。エージェントは既に前のステップの結果を読んで次を組み立てられるのだから、**その判断をツール側の貧弱な式言語に移す理由が無い**。

`batch` が有効なのは「引数がすべて事前に確定している一連の手順」であり、これは記録された手順の再生とちょうど同じ形をしている。

---

## 12. アーキテクチャへの影響

### `pyselector/cli.py`

- `expect` / `shot` / `launch` / `close` / `record` / `batch` のサブパーサーを追加。
- `find` に `--wait` / `--wait-gone` / `--with-state`、`act` に `--settle` / `--note` を追加。
- 検証関数：`_validate_expect_target()`（`find` と共通化）、`_resolve_expectation()`（`_resolve_act_action` と同型）。
- `launch` / `close` は `act` と同じく `args.env_allow_actions` を設定する。

### `pyselector/model/`

- `element_info.py`: 状態属性 5 つを追加。
- `expect_result.py`（新規）: `ExpectResult`。
- `shot_result.py`（新規）: `ShotResult`, `Annotation`。
- `launch_result.py`（新規）: `LaunchResult`, `CloseResult`。
- `batch_result.py`（新規）: `BatchResult`, `BatchStepResult`。

### `pyselector/backends/`

- `base.py`: `read_element_state()` を抽象メソッドに追加。
- `common.py`: `read_element_state()` の実装、`capture_wrapper_image()`。
- `element_from_wrapper()` は変更しない（`§3.2`）。

### `pyselector/inspect_runner.py`

- `run_expect()` / `run_shot()` / `run_launch()` / `run_close()` を追加。
- `run_find()` に待機ループを追加。
- `run_act()` に `--settle` と記録処理を追加。
- 待機ループは `pyselector/wait.py`（新規）に切り出し、`find` と `expect` で共有する。

現状 836 行あり、これ以上の追加は見通しを損なう。**本計画の実装に合わせて分割する。**

```text
pyselector/commands/inspect.py   run_inspect
pyselector/commands/tree.py      run_tree
pyselector/commands/windows.py   run_windows
pyselector/commands/find.py      run_find
pyselector/commands/act.py       run_act
pyselector/commands/expect.py    run_expect
pyselector/commands/shot.py      run_shot
pyselector/commands/lifecycle.py run_launch / run_close
pyselector/commands/batch.py     run_batch
pyselector/commands/common.py    共有処理（_build_backend_inspection など）
```

`inspect_runner` は後方互換のための再エクスポートとして残す（テストと `cli.py` の import 経路を一度に壊さないため）。

### `pyselector/record/`（新規）

```text
model.py     RecordingSession, RecordedStep
store.py     load / save / append / clear
codegen.py   emit_pytest / emit_plain
```

### `pyselector/output/`

- `json_output.py`: 新コマンドのフォーマッタ、`_element_to_dict` に状態属性。
- `text_output.py`: 同上。

### `pyselector/config.py`

- `apps` セクション（辞書形式）。
- `wait` セクション（`poll_interval`）。
- `expect` / `shot` / `record` / `batch` の既定値セクション。

### `pyselector/server/protocol.py`

- `SERVER_COMMANDS` に `expect` / `shot` / `find` 相当の読み取り系を追加する。`launch` / `close` は**サーバーに送らない**（プロセスの親子関係が常駐プロセス配下になり、サーバー終了時の挙動が読みにくくなるため）。`batch` も送らない（各ステップが個別に判断すればよい）。

### `pyselector/install.py`

- SKILL.md に新コマンドと、`§14` の指針を追記。

---

## 13. 実装ステップ

依存関係の順に並べる。各段階は単体で意味があり、途中で止めても壊れない。

### Phase 1: 状態属性と `expect`

1. `ElementInfo` に状態属性を追加
2. `read_element_state()` を両バックエンドに実装
3. `find --with-state` / `inspect` で状態を出力
4. `expect` コマンドと `EXIT_EXPECTATION_FAILED`

**ここまでで、エージェントは初めて「検証」を書けるようになる。**

### Phase 2: 待機

5. `pyselector/wait.py`（ポーリングループ）
6. `find --wait` / `--wait-gone`
7. `expect --wait`
8. `act --settle`

### Phase 3: `inspect_runner` の分割

9. `pyselector/commands/` へ機械的に分割（挙動の変更を伴わない）

Phase 4 以降でさらに 3 コマンド増えるため、ここで分割しておく。

### Phase 4: 記録とコード生成

10. `record` の保存形式と `start` / `status` / `show` / `cancel`
11. `act` / `expect` からの記録（セレクター解決を含む）
12. `codegen`（pytest / plain）と `record stop`

### Phase 5: ライフサイクル

13. `apps` 設定セクション
14. `launch`（`--dry-run` を含む）
15. `close`
16. `record` への `launch` / `close` の記録と、fixture 生成

### Phase 6: スクリーンショット

17. `shot`（ウィンドウ / 要素 / 画面）
18. `--annotate`

### Phase 7: バッチと SKILL

19. `batch`
20. SKILL.md と README の更新

---

## 14. SKILL.md に加える指針

AutoGenesis の SKILL は大半が大文字の強制文言と、自身の不具合の回避手順で占められている。取り入れる価値があるのは次の 3 点に絞られる。

### 14.1 検証は自分の分析でなく、ツールで行う

> Never decide that a check passed by reading a tree dump yourself. A dump is a snapshot of a moment that has already passed. Express the check as an `expect` command so the tool re-reads the live UI and reports the verdict.

現在の SKILL には "Re-read state between actions instead of assuming it" とあるが、「自分でツリーを読んで合格と判断する」という具体的な失敗を禁じていない。`expect` の追加によって、この指示は初めて**従える**ものになる。

### 14.2 一致 0 件からの復帰手順

現在の SKILL は「良いセレクターの選び方」は説明しているが、「`find` が 0 件だったとき次に何をするか」が無い。順序を決めて短く書く。

```text
1. --depth / --max-items を上げる（reached_limit を確認する）
2. 条件を 1 つ落とす（--control-type を外す）
3. --text を --text-re に緩める
4. --backend を切り替える（win32 <-> uia）
5. --include-hidden で隠れ要素を含める
6. tree --summary で構造を見直す
7. まだ画面に出ていない可能性を疑い、act --diff でメニューやタブを開く
8. --wait を付けて、まだ描画されていない可能性を潰す
```

### 14.3 各呼び出しの結果を、次に進む前に明示する

AutoGenesis の ✅ / ❌ の儀式は過剰だが、その下にある規律は正しい。「`act` の後は `status` と終了コードを確認してから次へ進む」という一文にする。

### 14.4 取り入れないもの

- **「成功するまで代替手段を試し続けろ」**（AutoGenesis の PERSISTENCE RULE）。実デスクトップを操作するツールでは、理解できていない画面に対する試行錯誤が誤操作になる。現在の SKILL の「利用者が明示的に頼んでいない確認・送信・削除を行わない」という規律のほうが正しく、両立しない。
- ツール引数への `caller` / `scenario` / `step` の混入。記録は `record` が担い、コマンドの引数を汚さない（唯一の例外が `--note` で、これは任意である）。

---

## 15. 完了後のエージェントのループ

```bash
# 1. 記録を始める
pyselector record start --name "計算結果の確認"

# 2. アプリを既知の状態から起動する
pyselector launch --json --app calculator --allow-actions
#   -> handle 0x2E20F46

# 3. 探索する（記録されない）
pyselector find --json --window-handle 0x2E20F46 --control-type Button --limit 30

# 4. 操作する（記録される）
pyselector act --json --window-handle 0x2E20F46 --auto-id num5Button --click --allow-actions
pyselector act --json --window-handle 0x2E20F46 --auto-id plusButton --click --allow-actions
pyselector act --json --window-handle 0x2E20F46 --auto-id num3Button --click --allow-actions
pyselector act --json --window-handle 0x2E20F46 --auto-id equalButton --click --allow-actions --settle 2

# 5. 検証する（記録される）
pyselector expect --json --window-handle 0x2E20F46 --auto-id CalculatorResults --value-contains "8" --wait 5

# 6. 見えないものは画像で確かめる
pyselector shot --json --window-handle 0x2E20F46 --out result.png

# 7. テストとして書き出す
pyselector record stop --emit pytest --out tests/test_calc.py
```

生成された `tests/test_calc.py` は pywinauto だけで動く。pyselector は**そこに至るまでの道具**であり、成果物には残らない。
