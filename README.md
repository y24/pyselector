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
| `pyselector expect` | 要素の存在・件数・値・状態を検証する |
| `pyselector shot` | ウィンドウ・要素・画面を PNG に撮る |
| `pyselector launch` | アプリを起動して主ウィンドウを待つ（既定で無効） |
| `pyselector close` | ウィンドウを閉じる（既定で無効） |
| `pyselector record` | 操作と検証を記録し、pywinauto コードを生成する |
| `pyselector batch` | 複数コマンドを 1 プロセスで順に実行する |
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

`act` は実際のデスクトップを操作します。このコマンドには、**2 段階の明示的な許可**が必要です。

1. カレントディレクトリの `.env` に `PYSELECTOR_ALLOW_ACTIONS=true` を書く
2. 実行時に `--allow-actions` を付ける

どちらか欠けていれば何も実行せず、終了コード 7（`action_not_allowed`）で終わります。

```bash
# .env（このファイルはリポジトリに含めない）
PYSELECTOR_ALLOW_ACTIONS=true
```

`.env` が無い場合はプロセスの環境変数 `PYSELECTOR_ALLOW_ACTIONS` を見ます。両方にある場合は `.env` の値を採用します。`true` / `1` / `yes` / `on` が許可、`false` / `0` / `no` / `off` が拒否で、それ以外の値はエラーになります。

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

### 常駐モード（任意・既定では無効）

`pyselector` は 1 コマンドごとにプロセスを起動するため、Python と pywinauto の import に約 0.55 秒の固定コストがかかります。常駐モードはこれを消し、加えて **要素参照（ref）をコマンドをまたいで使えるようにします**。

**既定では無効です。設定を書かない限り、これまでとまったく同じ動作をします。** 常駐プロセスも生まれません。

有効にするには `pyselector_config.json` に次を書きます。

```json
{ "server": { "enabled": true } }
```

これだけで、以降は必要になった時点でサーバーが自動起動し、無操作 300 秒で自ら終了します。**利用者がサーバーを手で起動する必要はありません。** コマンドの書き方も変わりません。

```bash
pyselector find --json --window-handle 0x2E20F46 --control-type Button
```

サーバーが動いていなければ、これまでどおりその場で実行されます。

#### ref による対象指定

常駐モードの主目的はこちらです。サーバー経由で実行すると、各要素に `ref` が付きます。

```bash
pyselector find --json --window-handle 0x2E20F46 --auto-id saveBtn   # → "ref": "uia:7f3a2b:42"
pyselector act  --json --ref uia:7f3a2b:42 --click --allow-actions
```

座標も再検索も要らず、`act` の対象が曖昧になる余地が消えます。`--ref` は `inspect` / `tree` / `find` / `act` で使え、`--at` / `--window-handle` / `--window-title` とは排他です。

`ref` が指す要素は画面が変われば無効になります。使うたびに生存確認を行い、失敗した場合は**何も操作せず**終了コード 9（`stale_ref`）で失敗します。サーバーを再起動した後の古い `ref` も同様です。

**`ref` はサーバー経由のときだけ出力されます。** ローカル実行の `ref` はプロセス終了とともに消えるため、出力すると誤解を招くからです。

#### サーバーを経由する条件

| 条件 | 経由するか |
| --- | --- |
| `--json` を指定した `inspect` / `tree` / `windows` / `find` / `act` / `diff` / `version` | する |
| テキスト出力（`--json` なし） | しない。進捗ログが逐次表示されることに意味があるため |
| オーバーレイやカウントダウンで対象を選ぶ実行 | しない |
| `serve` / `install-skills` | しない |

`--server` で明示的に切り替えられます。

```text
--server auto      繋がれば使う。繋がらなければローカル実行（設定で有効化したときの既定）
--server off       常にローカル実行（設定に関わらず）
--server require   サーバーが必須。繋がらなければ終了コード 11 で失敗する
```

`require` は、`ref` を確実に使いたいエージェントのためにあります。`auto` で黙ってローカルに落ちると `ref` が返らないため、その判別手段になります。

#### サーバーの管理

```bash
pyselector serve                      # フォアグラウンドで起動
pyselector serve --idle-timeout 600   # 無操作 600 秒で自動終了（既定 300）
pyselector serve --allow-actions      # このサーバーに act の実行を許す
pyselector serve --status             # 稼働状況を表示（--json 可）
pyselector serve --stop               # 停止を要求する
```

プロセスを自分で管理したい場合は `server.auto_start` を `false` にします。

孤児プロセスを残さないよう、アイドルタイムアウト・`--stop`・状態ファイルの掃除（`--status` は死んだ pid の記録を消します）の 3 つを用意しています。

#### 常駐モードと `act`

`act` の 2 つの関門（`.env` の `PYSELECTOR_ALLOW_ACTIONS` と `--allow-actions`）は、常駐モードでもそのまま効きます。`.env` はサーバーではなく**クライアントのカレントディレクトリ**を基準に、要求ごとに評価されるため、判定はローカル実行と完全に同じです。

これに加えて、サーバー自身が UI を操作できるかどうかという上限があります。「その操作を許すか」ではなく「**このデーモンに UI を触らせるか**」という別の軸の設定です。

```bash
pyselector serve                    # act を拒否する（読み取り専用のデーモン）
pyselector serve --allow-actions    # act を許可する
```

**手動起動は既定で拒否、自動起動は `.env` に書かれた同意を引き継ぎます。** つまり `PYSELECTOR_ALLOW_ACTIONS=true` を書いたディレクトリから自動起動されたサーバーは `act` を実行できます。

`act` を許可していないディレクトリから先にサーバーが自動起動されていると、後から `act` を許可した別のディレクトリで実行しても上限に阻まれます。その場合は次で起動し直してください。

```bash
pyselector serve --stop
```

#### 安全性について

通信には名前付きパイプ（`\\.\pipe\pyselector-<SID>`）を使い、ACL を実行ユーザーと SYSTEM に限定しています。認証はカーネルが SID で強制するため、こちら側に漏れて困る秘密情報がありません。TCP ポートは開きません。

**常駐化によってできることは増えません。** 同じユーザーで動く他のプロセスは、パイプに繋がなくても最初から `pyselector` を直接実行できるからです。

#### バージョン不一致

要求にはクライアントの版数が入ります。サーバーと異なる場合、サーバーは実行を拒み、クライアントはローカル実行にフォールバックしたうえで標準エラーにその旨を出します。`pip install -e .` で更新した後に古いサーバーが結果を返し続ける事故を防ぐためです。

### `expect`（検証）

要素がどうあるべきかを判定します。`find` と同じ条件で対象を指定し、判定をちょうど 1 つ指定します。

```bash
pyselector expect --json --window-handle 0x2E20F46 --auto-id saveBtn --exists
pyselector expect --json --window-handle 0x2E20F46 --auto-id dialog --not-exists
pyselector expect --json --window-handle 0x2E20F46 --control-type Button --count 5
pyselector expect --json --window-handle 0x2E20F46 --auto-id nameBox --value-equals "山田"
pyselector expect --json --window-handle 0x2E20F46 --auto-id agree --checked
pyselector expect --json --window-handle 0x2E20F46 --auto-id submit --enabled
```

| 判定 | 対象が一意である必要 |
| --- | --- |
| `--exists` / `--not-exists` / `--count N` | 不要 |
| `--value-equals` / `--value-contains` | 必要 |
| `--checked` / `--unchecked` | 必要 |
| `--enabled` / `--disabled` | 必要 |

**判定が成立しないことと、判定を実行できないことは別物です。**

```text
status=success, satisfied=true   判定が成立した            終了コード 0
status=success, satisfied=false  判定は動いたが成立しない  終了コード 12
status=error                     判定そのものが実行できない（ウィンドウが無い等）
```

要素の値やチェック状態は、走査時ではなく判定に必要になった時点で読みます。`find` で状態を見たい場合は `--with-state` を付けます（出力する要素だけを読むため、走査そのものの速度は変わりません）。

3 値のチェックボックスが「不定」のとき `is_checked` は `null` になり、`--checked` も `--unchecked` も成立しません。`false` として報告すると、チェックが外れていることを確かめたテストが誤って通るためです。

win32 バックエンドでは `value` を読みません。表示テキストと区別が付かず、誤って通るアサーションを誘発するためです。

### 待機

画面は操作が返った瞬間に描き終わっているとは限りません。固定の sleep ではなく、期待する状態を指定して待ちます。

```bash
pyselector find   --json --window-handle 0x2E20F46 --auto-id dialog --wait 5
pyselector find   --json --window-handle 0x2E20F46 --auto-id spinner --wait-gone 5
pyselector expect --json --window-handle 0x2E20F46 --auto-id result --value-contains "完了" --wait 10
pyselector act    --json --ref uia:7f3a2b:42 --click --allow-actions --settle 3
```

タイムアウトはエラーにしません。最後の試行の結果をそのまま返すので、`find --wait` なら 0 件、`expect --wait` なら `satisfied=false` として現れます。出力には `waited` / `attempts` / `timed_out` が付きます。

`act --settle` は「連続 2 回の観測が一致するまで」待ちます。変化の無い画面では即座に返り、`--diff` と併用したときは安定した後のツリーを操作後として使います。

### `shot`（スクリーンショット）

要素ツリーは、自前描画のコントロールやアイコンだけのボタン、描画崩れを表現できません。

```bash
pyselector shot --json --window-handle 0x2E20F46 --out shot.png
pyselector shot --json --ref uia:7f3a2b:42 --out button.png
pyselector shot --json --screen --out desktop.png
pyselector shot --json --window-handle 0x2E20F46 --annotate --control-type Button --out buttons.png
```

`--annotate` は `find` と同じ条件で一致した要素に番号付きの枠を描き込み、番号と要素の対応を JSON に返します。「画像の 3 番が探しているボタン」という形の対話が成立します。

`origin` は画像の左上に対応する画面座標です。要素の `rectangle` と画像内の位置を突き合わせられます。既存ファイルは `--force` が無ければ上書きしません。

判定は行いません。画面を見て判断するのは呼び出し側の役目です。

### `launch` / `close`（アプリのライフサイクル / 既定で無効）

どちらもマシンの状態を変えるため、**`act` と同じ 2 段階の許可**（`.env` の `PYSELECTOR_ALLOW_ACTIONS=true` と `--allow-actions`）が必要です。`--dry-run` も同じように使えます。

```bash
pyselector launch --json --exe "C:\Windows\System32\calc.exe" --wait-title-re "^電卓$" --allow-actions
pyselector launch --json --app calculator --allow-actions
pyselector close  --json --window-handle 0x2E20F46 --allow-actions
```

`launch` は起動したプロセスの `pid` と、見つかった主ウィンドウの `handle` を返します。**この handle をそのまま以降のコマンドに渡せる**ことが `launch` の主な価値です。

よく使うアプリは設定ファイルに書いておけます。

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

主ウィンドウの特定にはタイトルの正規表現を使ってください。`calc.exe` のように、起動したプロセスとは別のプロセスがウィンドウを出すアプリでは pid が一致しません。

`--attach-existing` は、既に起動していれば起動せず接続します。

`close` は既定でウィンドウに閉じるよう頼みます。`--force` はプロセスを終了させるため、保存していない作業を失う可能性があります。

### `record`（記録とコード生成）

記録中は、成功した `act` と成立した `expect` が 1 手順ずつ蓄積され、最後に **pywinauto だけで動くテスト**を書き出せます。**生成されたファイルは pyselector に依存しません。**

```bash
pyselector record start --name "計算結果の確認"
# ... launch / act / expect を普段どおり実行 ...
pyselector record show --json
pyselector record stop --emit pytest --out tests/test_calc.py
```

| 記録する | 記録しない |
| --- | --- |
| 実際に実行した `act` | `act --dry-run` |
| 成立した `expect` | 成立しなかった `expect` |
| `launch` / `close` | `find` / `tree` / `inspect` / `shot` |

探索は手順ではなく、テストに残す必要が無いため記録しません。成立しなかった判定を記録しないのは、生成コードに書き出せば必ず落ちる assert になるからです。

記録中の `act` と `expect` は、解決済みの要素に対してセレクター候補の生成と評価まで行い、**評価済みの最良の候補**を記録します。CLI に渡した条件をそのままコードにしても良いセレクターになるとは限らないためです（`--text` は表示文言に、`--index` は並び順に依存します）。この追加コストは記録中だけで、記録していないときの `act` の速度は変わりません。

適切な候補が見つからなかった場合は、生成コードにコメントと `NotImplementedError` を残します。**推測でそれらしいコードを出力しません。**

生成コードに待機を入れたい場合は `expect --wait N` を使ってください。記録に無い待機を勝手に挿入することはありません。

```bash
pyselector record stop --emit pytest   # 既定。window フィクスチャ付きのテスト
pyselector record stop --emit plain    # pytest に依存しない単一スクリプト
pyselector record stop --emit none     # 記録を JSON のまま出す
```

記録はユーザーにつき 1 つです。デスクトップは共有資源であり、同時に 2 つの操作シナリオを記録することは原理的にできません。

### `batch`（複数コマンドの一括実行）

常駐モードが消したのはプロセス起動の約 0.55 秒ですが、AI エージェントにとっての実コストは **1 コマンド = 1 ツール呼び出しの往復**です。

```bash
pyselector batch --json steps.json
cat steps.json | pyselector batch --json -
```

```json
{
  "steps": [
    { "command": "act",    "args": ["--ref", "uia:7f3a2b:42", "--click", "--allow-actions"] },
    { "command": "expect", "args": ["--window-handle", "0x2E20F46", "--auto-id", "dialog", "--exists", "--wait", "5"] }
  ]
}
```

各ステップは必ず `--json` で実行され、エンベロープがそのまま `steps[].result` に入ります。既定では最初の失敗で停止し、その終了コードを返します（`--continue-on-error` で最後まで走ります）。`batch` / `serve` / `install-skills` はステップに指定できません。

**ステップ間の変数展開はありません。** 小さなテンプレート言語を発明すれば、その仕様・エラー・デバッグ手段を維持する必要が出ます。前のステップの結果を見て次を組み立てられるなら、その判断を貧弱な式言語に移す理由がありません。

### JSON の共通仕様

`--json` の出力には必ず `schema_version` / `command` / `status` / `served` が含まれます。`served` は、その結果を常駐サーバーが返したかどうかです。

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

状態を変えるのは `act` / `launch` / `close` の 3 つだけです。いずれも同じ 2 段階の許可（`.env` の `PYSELECTOR_ALLOW_ACTIONS=true` と `--allow-actions`）がなければ何も実行しません。関門を増やすと覚えることが増えるだけなので、**スイッチは 1 つのまま**にしています。

`shot` と `record` はファイルを書きますが、アプリの状態は変えないため許可は要りません。

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
    "backend": "uia",
    "depth": 8,
    "max_items": 200,
    "only_visible": true
  },
  "selector": {
    "evaluation_max_items": 10,
    "found_index_trial_count": 3
  },
  "server": {
    "enabled": false,
    "auto_start": true,
    "idle_timeout": 300,
    "max_refs": 5000,
    "connect_timeout": 30
  }
}
```

`server.enabled` が `false` の間、クライアントはサーバーを探しにいきません。`auto_start` は `enabled` が `true` のときだけ意味を持ちます。

別の場所の設定ファイルを使う場合は、環境変数 `PYSELECTOR_CONFIG` にパスを指定できます。

## テスト

pytest を使ってテストを実行します。pytest が未インストールの場合は、先にインストールしてください。

```bash
pip install pytest
python -m pytest
```

`pyproject.toml` でテスト対象は `tests` ディレクトリに設定されています。
