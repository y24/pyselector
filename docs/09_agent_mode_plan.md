# pyselector AI エージェント自律探索モード 追加計画

## 1. 改修目的

現在の pyselector は「人間が UI 自動テストを開発するときに、調べたい場所をクリックして要素を調べる」ためのツールになっている。

- `inspect` はオーバーレイのクリック、または `--delay` 後のカーソル位置に依存する
- `tree` は調査対象のウィンドウタイトルを人間が知っていることが前提になっている
- どちらも「人間が対象を指し示す」ことが探索の起点になっている

一方、AI エージェントが CLI ツールを自分で叩きながら状況を探索していく使い方が増えている。エージェントには次のものが無い。

```text
マウスが無い
画面が見えない
どのウィンドウが開いているか知らない
対象要素の正確なタイトルを知らない
```

そのため現状のままでは、エージェントは `pyselector` の入口に立てない。

本計画では、**既存の人間向け機能は一切変更せず**、AI エージェントが自律的に

```text
どんなウィンドウがあるか調べる
  ↓
そのウィンドウの中を絞り込み検索する
  ↓
見つけた要素のセレクター候補を確定させる
  ↓
pywinauto コードを書く
```

というループを回せるように、非対話コマンドとオプションを追加する。

---

## 2. 現状のギャップ整理

| エージェントに必要なこと | 現状 | 対応方針 |
| --- | --- | --- |
| 開いているウィンドウの一覧を知る | 手段が無い | `windows` サブコマンドを追加 |
| ウィンドウを一意に指定する | `--window-title` のみ。一致件数が 1 件でないと `find_window_by_title` がエラー | `--window-handle` を追加 |
| 条件で要素を絞り込む | `tree` の全ダンプのみ | `find` サブコマンドを追加 |
| クリックせずに要素を特定する | 不可（オーバーレイ / カーソル必須） | `inspect --at X,Y` / `--handle` を追加 |
| 出力を機械的に解釈する | `--json` はあるがスキーマ版数が無い | `schema_version` を付与 |
| エラーを機械的に解釈する | `[ERROR] ...` を stderr にテキスト出力 | `--json` 時は JSON エラーエンベロープを stdout に出力 |
| 出力トークン量を抑える | `tree` の出力が肥大しやすい | `--compact` / `--summary` / 既定 `--max-items` |
| 次に何をすべきか判断する | 情報なし | `find` の結果に再利用可能な `point` と `selector` を含める |

重要な前提として、**UIA 要素は `handle` が `None` のことが多い**。したがってエージェント向けの「要素の指し示し方」は handle 一本では成立しない。本計画では次の 2 系統を正とする。

- `point`（要素矩形の中心座標。物理ピクセル）… 全バックエンド共通で使える
- `handle`（win32 で有効）… 取得できたときのみ使う

`setup_dpi_awareness()` 済みのため、`find` が返す矩形座標はそのまま `inspect --at` に渡せる。この座標系の一貫性を仕様として明記する。

---

## 3. 設計方針

1. **既存挙動を変えない。** `pyselector` / `pyselector inspect` / `pyselector tree` の既定動作、既定値、出力フォーマットは現状維持する。
2. **追加のみで構成する。** 新サブコマンド（`windows` / `find`）と、既存サブコマンドへの新オプション（`inspect --at` 等）のみを足す。
3. **非対話であることを保証する。** 新機能はオーバーレイもカウントダウンもカーソル取得も行わない。人間の操作を一切待たない。
4. **人間にも読める形で出す。** 新コマンドもテキスト出力を持つ。`--json` は既存同様のオプトインとする。
5. **既存パイプラインを再利用する。** セレクター生成・評価・警告付与・スニペット生成は `run_inspect` と同じ経路を通す。エージェント専用の別ロジックを作らない。
6. **書き込み系は本計画の対象外に置く。** クリックや入力による UI 操作は「9. 将来的な拡張」に切り出し、既定では読み取り専用を維持する。

---

## 4. コマンド仕様

### 4.1 `windows` サブコマンド（新規）

開いているトップレベルウィンドウを列挙する。エージェントの探索の起点になる。

```bash
pyselector windows --json
```

オプション:

```text
--title <str>           タイトル部分一致で絞り込む
--title-re              --title を正規表現として扱う
--process <str>         プロセス名で絞り込む（例: notepad.exe）
--pid <int>             プロセスIDで絞り込む
--backend win32|uia     既定は win32
--include-hidden        非表示ウィンドウも含める
--max-items <int>       既定 50
--json                  JSON 出力
```

出力に含める項目:

```text
title / class_name / process_name / process_id / handle
rectangle / is_visible / is_enabled
```

補足:

- 既定を `win32` にするのは、トップレベル列挙の速度と安定性のため。`uia` は明示指定時のみ。
- 一致 0 件でもエラーにせず、空配列と終了コード 1 を返す（エージェントが「無い」ことを判定できるようにする）。

### 4.2 `find` サブコマンド（新規）

指定ウィンドウ配下を条件で絞り込み検索する。**人間のクリックを置き換える中心機能**。

```bash
pyselector find --window-handle 0x2E20F46 --control-type Button --text "保存" --json
```

対象範囲の指定（いずれか必須）:

```text
--window-handle <hex|int>   windows コマンドで得た handle
--window-title <str>        既存 tree と同じ探索
--title-re                  --window-title を正規表現として扱う
--at X,Y                    その座標の要素を起点にする
```

絞り込み条件（すべて AND、省略時は無条件）:

```text
--text <str>            window_text の部分一致
--text-re <regex>       window_text の正規表現一致
--auto-id <str>         automation_id の完全一致
--control-type <str>    control_type の完全一致
--class-name <str>      class_name の完全一致
--enabled-only          is_enabled が True のものだけ
```

探索範囲と出力量:

```text
--backend win32|uia|both  既定は config.find.backend（初期値 uia）
--depth <int>             既定 8
--max-items <int>         走査上限。既定 200
--limit <int>             出力する一致件数の上限。既定 20
--include-hidden          非表示要素も含める
--compact                 1 要素あたりの項目を最小限にする
--json
```

セレクター確定:

```text
--with-selectors          一致要素についてセレクター候補まで生成・評価する
--selector-limit <int>    候補生成する要素数の上限。既定 3
```

各一致要素の出力に必ず次を含める。これがエージェントの「次の一手」になる。

```text
point: {x, y}    要素矩形の中心座標（そのまま inspect --at に渡せる）
handle           取得できた場合のみ
depth            起点からの深さ
```

`--with-selectors` を付けた場合は、その要素について `run_inspect` と同じ

```text
target_window / element / hierarchy / selector_candidates / code_snippet
```

を返す。つまり `find --with-selectors` 1 回で「探す → 確定する」が完結する。

### 4.3 `inspect` への追加オプション

既存の `inspect` に、非対話の座標指定手段を追加する。既定動作（オーバーレイ）は変更しない。

```bash
pyselector inspect --at 636,2240 --json
pyselector inspect --handle 0x2E20F46 --json
```

```text
--at X,Y        指定座標の要素を調べる。オーバーレイもカウントダウンも行わない
--handle <hex>  ウィンドウハンドルから要素を特定する（win32 向け）
```

排他関係:

```text
--at と --handle は同時指定不可
--at / --handle と --delay は同時指定不可
```

実装上は `run_inspect` の `point_selector` 引数（既に存在する注入口）に、固定座標を返す関数を渡すだけで済む。`--handle` は矩形中心を座標に変換して同じ経路に流す。

### 4.4 `tree` への追加オプション

```text
--window-handle <hex>   タイトル一致に依存せずウィンドウを指定する
--summary               control_type / class_name ごとの件数集計だけを出す
--compact               1 ノードあたりの項目を最小限にする
```

`--summary` は、エージェントが大きなウィンドウに対して「まず全体像だけ掴む」ために使う。数千ノードの JSON を読ませずに済ませることが目的。

### 4.5 共通オプション

```text
--schema-version   出力 JSON のスキーマ版数を表示して終了する
```

---

## 5. 出力契約（エージェント向け）

### 5.1 スキーマ版数

`--json` の全出力のトップレベルに追加する。既存キーは削除も改名もしない（後方互換）。

```json
{
  "schema_version": 1,
  "command": "find",
  "status": "success",
  "...": "既存キーはそのまま"
}
```

### 5.2 エラーエンベロープ

現状、`PySelectorError` は `[ERROR] ...` を stderr に出して終了コードを返す。`--json` 指定時はこれに加えて stdout に JSON を出す。

```json
{
  "schema_version": 1,
  "command": "find",
  "status": "error",
  "error": {
    "code": "element_not_found",
    "exit_code": 1,
    "message": "一致するウィンドウ数が 3 件です"
  }
}
```

`code` は `utils/errors.py` の例外クラスに 1 対 1 で対応させる。終了コードは既存の値を変更しない。

### 5.3 ゼロ件と失敗の区別

エージェントが誤判定しないよう、次を明確に分ける。

```text
status=success, matches=[]  … 探索は成功したが該当なし（終了コード 1）
status=error                … 探索そのものが失敗（終了コードは既存の分類に従う）
```

### 5.4 出力順序の決定性

同じ画面状態に対して同じ順序を返す。`find` の一致要素は `depth → 矩形の top → left` の順で安定ソートする。

---

## 6. エージェントの探索ループ（想定シナリオ）

```text
1. pyselector windows --json
     → 開いているウィンドウと handle を得る

2. pyselector tree --window-handle 0x... --summary --json
     → そのウィンドウの規模と control_type の分布を掴む

3. pyselector find --window-handle 0x... --control-type Button --json
     → 候補要素と point を得る

4. pyselector find --window-handle 0x... --text "保存" --with-selectors --json
     → セレクター候補と code_snippet を確定する

5. 候補が曖昧なら
     pyselector inspect --at <point.x>,<point.y> --json
     → 単一要素に対して完全な評価を行う
```

このループは全て非対話で、標準出力の JSON だけで完結する。

---

## 7. アーキテクチャへの影響

### `pyselector/cli.py`

- `windows` / `find` のサブパーサーを追加する
- `inspect` に `--at` / `--handle`、`tree` に `--window-handle` / `--summary` / `--compact` を追加する
- `--at` の `X,Y` パース関数（`_point` 型）を追加する。書式不正は `ArgumentError` にする
- 排他検証（`--at` と `--delay` 等）を `_validate_visible_options` と同じ位置に追加する
- 既存の「引数なし → `inspect` を補完する」挙動は維持する。`windows` / `find` は明示指定を必須にする

### `pyselector/backends/base.py` / `common.py`

追加する抽象メソッド:

```text
list_windows(filters) -> list[ElementInfo]
element_from_handle(handle) -> ElementInfo
find_window_by_handle(handle) -> ElementInfo
```

`find` の実装は新規探索ロジックを書かず、`walk_tree` を再利用したうえで述語フィルタをかける方針とする。ただし現状の `walk_tree` は `HierarchyNode` しか返さないため、次の対応が要る。

- 走査中の wrapper を `_remember()` でハンドルキャッシュに載せる
- 一致要素については `element_from_wrapper()` で `ElementInfo` を作る
- そうすることで、その後の `get_hierarchy()` / `generate_candidates()` が既存のまま動く

`_wrapper_for()` は `handle` キャッシュか `_last_wrapper` に依存しているため、**複数一致要素に対して順にセレクター生成する場合はキャッシュ経由の解決が必須**になる。ここが実装上いちばん壊れやすい箇所なので、`--selector-limit` で件数を絞る前提とし、テストで固定する。

### `pyselector/inspect_runner.py`

- `run_windows(args)` / `run_find(args)` を追加する
- `run_inspect` は変更しない。`--at` / `--handle` は `point_selector` を差し込む形で吸収する
- `run_find --with-selectors` は、`run_inspect` 内のセレクター生成〜評価〜警告付与〜スニペット生成の一連を関数として切り出して共有する（`_build_backend_inspection(element, inspector, args)` 相当）。ここは既存挙動を変えないリファクタリングなので、先にテストで現状出力を固定してから行う

### `pyselector/model/`

- `WindowSummary`（`windows` の 1 行）
- `FindMatch`（要素 + `point` + 任意の `BackendInspection`）
- `FindResult` / `WindowsResult`

### `pyselector/output/json_output.py` / `text_output.py`

- `format_windows_result_json` / `format_find_result_json` / それぞれのテキスト版
- 全 JSON 出力に `schema_version` / `command` / `status` を付与するラッパーを 1 箇所に集約する
- `--compact` 用の項目間引き

### `pyselector/output/log_file.py`

`save_inspection_log` は `InspectionResult` 前提。`windows` / `find` はログ保存対象外とする（探索ループで大量実行されるため、`.pyselector-log` を汚さない）。

### `pyselector/config.py`

セクション未知キーを拒否する実装のため、追加セクションの登録が必須。

```json
{
  "windows": {
    "backend": "win32",
    "max_items": 50,
    "only_visible": true
  },
  "find": {
    "backend": "uia",
    "depth": 8,
    "max_items": 200,
    "limit": 20,
    "selector_limit": 3,
    "only_visible": true
  }
}
```

### `pyselector/install.py`

- skill の内容に `windows` / `find` / `inspect --at` を追記し、6 章の探索ループを手順として明記する
- `install-skills --copilot`（`.github/skills/pyselector-cli/SKILL.md`）と `install-skills --claude`（`.claude/skills/pyselector-cli/SKILL.md`）を用意する
- skill 本文の方針を「常に `--json`」から「常に `--json`、かつ探索は `windows` → `find` の順」に更新する

---

## 8. 実装ステップ

### Phase 1: 出力契約の整備（他フェーズの土台）

```text
schema_version / command / status の付与
--json 時の JSON エラーエンベロープ
既存 JSON 出力のリグレッションテスト
```

既存キーを壊していないことをテストで固定してから次へ進む。

### Phase 2: 非対話の入口

```text
windows サブコマンド
inspect --at / --handle
tree --window-handle
```

この時点で、エージェントは「ウィンドウを見つけて座標指定で調べる」ことができるようになる。

### Phase 3: 絞り込み検索

```text
run_inspect のセレクター生成部の関数切り出し
find サブコマンド（--with-selectors なし）
find --with-selectors
```

ここが本計画の中心。Phase 2 までで動作確認できる状態を作ってから着手する。

### Phase 4: 出力量の制御

```text
tree --summary / --compact
find --compact
既定 max-items / limit の調整
```

### Phase 5: エージェント向けドキュメント

```text
install-skills サブコマンド（--copilot / --claude）
skill 本文の更新
README にエージェント向けセクションを追加
```

---

## 9. 将来的な拡張（本計画のスコープ外）

9.1 と 9.2 は後から実装した（15 章）。9.3 は未着手。

### 9.1 UI 操作（`act`） / 9.2 状態差分（`diff`）

**実装済み。** 「15. act / diff の実装」を参照。

### 9.3 常駐モード / MCP

現状は 1 コマンドごとに Python 起動と pywinauto の import が走る。探索ループでは往復回数が多く、この起動コストが支配的になる可能性がある。

```bash
pyselector serve --stdio
```

wrapper キャッシュを保持したまま複数リクエストを処理できれば、`find` → `inspect` の連携も安定する。MCP サーバー化も同じ土台に載る。

**Phase 3 完了時点で 1 コマンドあたりの実測所要時間を計測し、常駐モードを前倒しすべきか判断する。**

---

## 10. テスト計画

### 単体テスト

既存テストは `FakeInspector` 系のクラスを差し込む方式（`tests/test_inspect_runner.py`）。この方式を踏襲する。

```text
test_cli_agent_options.py
  --at のパース（正常 / 不正書式）
  --at と --delay の排他
  --at と --handle の排他
  windows / find の必須引数検証

test_windows_command.py
  フィルタ（title / title-re / process / pid）
  0 件時に status=success かつ終了コード 1
  JSON / テキスト両方の形

test_find_command.py
  述語 AND の組み合わせ
  depth / max-items / limit の打ち切り
  出力順序の決定性
  --with-selectors 時に selector_limit 件だけ候補生成されること
  複数一致要素に対して wrapper 解決が破綻しないこと

test_json_envelope.py
  schema_version / command / status の付与
  エラー時の JSON エンベロープと終了コードの対応
  既存 inspect / tree の JSON キーが変わっていないこと（リグレッション）

test_config.py（既存に追加）
  windows / find セクションの読み込みと不正値の拒否
```

### 手動テスト

```text
電卓（UWP / UIA）で windows → find --control-type Button → --with-selectors
メモ帳（win32）で同じ流れ
複数ディスプレイ・DPI 混在環境で find の point が inspect --at と一致すること
非表示要素を含むウィンドウでの --include-hidden
存在しないウィンドウ指定時のエラー JSON
```

DPI 混在環境の座標一致は過去に対応した箇所（`utils/dpi.py`）に関わるため、`find` の `point` → `inspect --at` の往復は必ず実機確認する。

---

## 11. 受け入れ条件

```text
既存の pyselector / inspect / tree の出力とオプションが変わっていない
既存テストが全て通る
エージェントがマウス操作なしで、windows → find → セレクター確定まで到達できる
--json 出力が全コマンドで schema_version を持つ
エラーが --json 指定時に JSON として stdout から読める
0 件と失敗が区別できる
find の point をそのまま inspect --at に渡して同じ要素が取れる
config の新セクションが検証付きで読み込める
GitHub Copilot / Claude Code 向け skill に新しい探索手順が記載されている
```

---

## 12. 主なリスクと対策

### リスク1: UIA 要素に handle が無く、要素を指し示せない

対策: `point`（矩形中心）を第一の識別手段とする。handle は取得できたときの補助に留める。矩形が取得できない要素は `point: null` とし、その旨を出力に含める。

### リスク2: wrapper キャッシュ依存で複数要素のセレクター生成が壊れる

`_wrapper_for()` は `_wrapper_by_handle` か `_last_wrapper` に依存している。UIA で handle が無い要素が複数あると、意図しない要素の階層を取りかねない。

対策: `find --with-selectors` では走査時の wrapper を要素ごとに保持し、`_last_wrapper` に頼らず解決する。`--selector-limit`（既定 3）で対象を絞る。この挙動はテストで固定する。

### リスク3: 出力が肥大しエージェントのコンテキストを圧迫する

対策: `find` の既定 `--limit 20`、`tree --summary`、`--compact` を用意する。skill 文書で「まず `--summary`、次に `find`、最後に `--with-selectors`」の順を明示する。

### リスク4: 探索ループで実行回数が増え、起動コストが支配的になる

対策: Phase 3 完了時に実測する。必要なら 9.3 の常駐モードを前倒しする。当面は skill 文書で `--backend` を明示させ、不要な `both` を避けさせる。

### リスク5: 画面状態が変わり、前回の point や handle が無効になる

対策: `inspect --at` / `--handle` が期待と異なる要素を返しうることを仕様として明記する。取得結果の `window_text` / `control_type` を照合するようエージェントに促す文言を skill に入れる。

### リスク6: 既存機能への副作用

`run_inspect` からセレクター生成部を切り出すリファクタリングが唯一の既存コード変更点になる。

対策: Phase 1 で既存 JSON 出力のリグレッションテストを先に置き、切り出し前後で出力が完全一致することを確認してから進める。

---

## 13. 実装担当 AI エージェント向け指示案

```text
# 改修指示: pyselector に AI エージェント向けの非対話探索機能を追加する

## 目的
AI エージェントがマウス操作なしに Windows UI を探索し、
pywinauto セレクターを確定できるようにする。

## 方針
既存の pyselector / inspect / tree の挙動は変更しない。
windows / find サブコマンドと、inspect --at / --handle を追加する。
セレクター生成は既存パイプラインを再利用する。
書き込み系（クリック・入力）は実装しない。

## 順序
Phase 1（出力契約）を先に完了させ、既存 JSON のリグレッションテストを
置いてから Phase 2 以降に進むこと。

## 受け入れ条件
docs/09_agent_mode_plan.md の「11. 受け入れ条件」に従う。
```

---

## 14. 実装結果と計画からの変更点

Phase 1〜5 を実装済み。以下は実装中に判明した事実により、計画から変更した点。

### 14.1 `--schema-version` は `version --json` に変更

引数なし実行時に `inspect` を補完する既存処理と、ルートパーサーのグローバルフラグは相性が悪い。スキーマ版数は `pyselector version --json` で返す形にした。`pyselector version` のテキスト出力は従来のまま変更していない。

### 14.2 `windows` は既定でタイトルなしウィンドウを除外

実機で確認したところ、トップレベルウィンドウ 23 件のうち 11 件が `ThumbnailDeviceHelperWnd` のようなタイトルなしの 1x1 ヘルパーウィンドウだった。既定の `--max-items 50` がノイズで埋まるため、タイトルを持つウィンドウのみを既定とし、`--include-untitled` で従来どおり全件を出せるようにした。

### 14.3 `tasklist` を Win32 API に置き換え（既存機能の性能改善）

`utils/process.py` はプロセス名の取得に `tasklist` を起動していたが、開発機での実測で **1 回あたり約 29.7 秒**かかっていた。`windows` は多数の PID を解決するため致命的で、既存の `inspect` も同じコストを払っていた。

`OpenProcess` + `QueryFullProcessImageNameW` を ctypes で直接呼ぶ実装に変更した。`windows --json` は 30.2 秒から 0.59 秒になった。取得できない場合（他ユーザーや保護されたプロセス）は従来どおり `None` を返す。

### 14.4 要素の参照 ID（リスク2 への対処）

`ElementInfo` に `ref` フィールドを追加し、`PywinautoInspectorMixin` が `_wrapper_by_ref` で wrapper を保持するようにした。`_wrapper_for()` は ref → handle → `_last_wrapper` の順に解決する。

これにより、handle を持たない UIA 要素が複数一致しても、要素ごとに正しい階層とセレクター候補が得られる。`ref` はプロセス内でのみ有効な内部識別子のため、JSON には出力していない。

### 14.5 `run_tree` に `setup_dpi_awareness()` を追加

`find` の `point` を `inspect --at` にそのまま渡せるという保証には、全コマンドで座標系が一致している必要がある。`run_tree` だけが DPI 対応を行っていなかったため追加した。高 DPI 環境では `tree --detail` の矩形が論理座標から物理座標に変わる。

### 14.6 対象要素がウィンドウ自身のときのコードスニペット

`inspect --handle` はウィンドウ自身を対象にするため、既存のセレクター候補生成では候補が 0 件になり、出力が空になっていた。`build_window_snippet()` を追加し、この場合に限りウィンドウだけのスニペットを返すようにした。子要素の候補が全滅したケースの挙動（`code_snippet: null`）は変えていない。

### 14.7 引数エラーも JSON エンベロープで返す

計画では `PySelectorError` のみを想定していたが、`--json` 利用時に argparse のエラーだけテキストで返るのは一貫性を欠く。`ArgumentParseExit` を導入し、引数エラーも同じ形の JSON で標準出力に返すようにした。

### 14.8 `find_window_by_title` のエラーメッセージ

一致件数が 1 件でないときのメッセージに、一致したタイトル（最大 5 件）を含めるようにした。エージェントが `windows` に切り替える判断をしやすくするため。

### 14.9 実測値

開発機（Windows 11、エクスプローラーのウィンドウを対象）での参考値。

```text
windows --json                                     0.59 秒
tree --window-handle --summary --backend win32     0.60 秒
find --control-type Button --backend uia           1.57 秒（走査 227 件 / 一致 25 件）
find --auto-id backButton --with-selectors         2.20 秒
inspect --at                                       1.21 秒
```

9.3 の常駐モードを前倒しする必要はない水準と判断した。

### 14.10 skill の配布先を GitHub Copilot と Claude Code に変更

Roo Code は廃止されたため、対象から外した。配布先は次の 2 つ。

```text
.github/skills/pyselector-cli/SKILL.md    （GitHub Copilot）
.claude/skills/pyselector-cli/SKILL.md    （Claude Code）
```

どちらも Agent Skills 形式（`name` / `description` の frontmatter を持つ SKILL.md）で、本文は共通。必要なときだけ読み込まれるため、常時コンテキストに載る `.github/copilot-instructions.md` 方式より無駄が少ない。

### 14.11 `install` を `install-skills` に改名

`pyselector install` は pyselector 自体のインストールと誤解されるため、`pyselector install-skills` に改名した。オプションは `--copilot` / `--claude` で、同時指定もできる。旧 `install` は互換のためのエイリアスを残していない（誤解を招く名前を残す意味がないため）。

### 14.12 ロゴを対話的な端末のみに限定

起動時のロゴは、AI エージェントがパイプ越しに実行したときに解析対象の出力へ混ざるノイズになる。削除はせず、`sys.stdout.isatty()` が真のときだけ表示するようにした。

```text
人がターミナルで実行         → ロゴあり（従来どおり）
パイプ・リダイレクト・--json → ロゴなし
```

`[INFO]` 行は情報としての意味があるため対象外とし、従来どおり `--json` 指定時のみ抑止する。

### 14.13 テスト

79 件から 172 件に増加。追加した内容は「10. テスト計画」のとおり。既存 JSON のリグレッションテスト（`tests/test_json_envelope.py`）を含む。

---

## 15. act / diff の実装（9.1 / 9.2）

読み取り専用の探索が動いたのち、9.1 と 9.2 を実装した。テストは 172 件から 233 件になった。

### 15.1 なぜ必要だったか

電卓での実測で、UIA から見える要素は 52 件だった。ナビゲーションを開くと 22 要素が現れ、そこで初めて「関数電卓」「プログラマー」などの画面が見えるようになる。**閉じている UI の中身は、開くまで存在しない。** 読み取り専用のままでは、エージェントの探索範囲は「人が今表示している画面」に限られる。

### 15.2 `act` の安全設計

`act` は唯一の書き込み系コマンドで、既定では何もしない。計画どおり二重のゲートを実装した。

```text
1. pyselector_config.json に {"act": {"allow_actions": true}}
2. 実行時に --allow-actions
```

どちらか欠ければ終了コード 7（`action_not_allowed`）で、対象の解決すら行わない。設定はリポジトリの持ち主が置くもので、エージェントが勝手に書き換えてはいけない旨を skill 文書に明記した。

加えて、事故を減らすために次を入れた。

- `--dry-run`: 対象を解決して報告するだけ。許可は不要なので、エージェントはまずこれを実行できる
- **一意性の強制**: 条件に複数一致した場合は実行せず、終了コード 6（`ambiguous_target`）で候補を列挙する。`--index N` で明示的に選んだ場合のみ実行する
- `--backend` から `both` を除外（両バックエンドで 2 回実行してしまうため）
- 1 コマンド 1 操作。複数の操作フラグを同時指定するとエラー

### 15.3 対象の指定方法

計画の `--selector "dlg.child_window(...)"` は採用しなかった。Python 式の文字列を受け取って解釈する形になり、脆いうえに危険なため。`find` と同じ述語（`--auto-id` / `--text` / `--control-type` / `--class-name` など）に統一し、探索と操作で同じ語彙を使えるようにした。

`--at X,Y` は対象を直接指すため、他の条件とは併用不可にしている。

### 15.4 操作の実行方法

pywinauto はバックエンドやコントロール種別で使えるメソッドが違う。`pyselector/actions.py` に「操作名 → 試すメソッドの優先順リスト」を置き、順に試して最初に成功したものを採用する。実際に使われたメソッド名は出力の `method` に含める。

```text
click        → click_input, click
invoke       → invoke, click, click_input
set_text     → set_edit_text, set_text
send_keys    → type_keys
```

`--invoke` は UIA の invoke パターンで、物理マウスを動かさずに済む。可能ならこちらを使うよう skill 文書で推奨している。

### 15.5 `diff` の同一性判定

ノードの同一性は `(depth, control_type, class_name, automation_id)` に出現順の連番を組み合わせたキーで判定する。`window_text` をキーに含めないのは、テキストの変化こそ検出したい対象だからである。同じキーの兄弟要素（電卓のボタン群のような）は出現順で対応付ける。

比較する属性は `window_text` / `rectangle` / `handle` / `control_id` / `friendly_class_name`。

`--summary` で取得した出力には `nodes` が無いため比較できない。その場合はエラーではなく、理由を `message` に入れた `status: failed` を返す。

終了コードは、差分があれば 0、完全に同じなら 1 とした。「探索して見つかったら 0」という他コマンドの規約と揃えている。

### 15.6 `act --diff`

計画ではファイル比較のみだったが、操作の前後を自分で撮るオプションを足した。エージェントの往復が 4 コマンドから 1 コマンドに減る。

```bash
pyselector act --window-handle 0x... --auto-id TogglePaneButton --click --allow-actions --diff
```

前後のスナップショットはそれぞれ新しいインスペクターで取り直す。操作によって wrapper のキャッシュが古くなるため。

### 15.7 実測（電卓）

```text
act --auto-id num5Button --click --diff
  → changed: 1 … "表示は 0 です" -> "表示は 5 です"

act --auto-id TogglePaneButton --click --diff
  → added: 22 … 標準 / 関数電卓 / グラフ計算 / プログラマー / 日付の計算 …

act --auto-id NumberPad --send-keys "7" --diff
  → changed: 1 … "表示は 5 です" -> "表示は 57 です"
```

### 15.8 追加した終了コード

```text
6  ambiguous_target      操作対象が一意に定まらない
7  action_not_allowed    UI 操作が許可されていない
8  action_failed         操作の実行そのものが失敗
```
