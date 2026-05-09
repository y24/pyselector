# 02_cli_spec.md

# pyselector CLI仕様書

## 1. 目的

本書は、pywinauto Selector Inspector CLI のコマンドライン仕様を定義する。

本ツールは、Windowsアプリケーション上のUI要素をカーソル位置から特定し、pywinautoで利用可能なセレクター候補とヒット件数を表示するCLIツールである。

本書では以下を定義する。

- コマンド構成
- サブコマンド
- オプション
- 既定値
- 実行例
- 終了コード
- CLIとして提供しない機能

---

## 2. コマンド名

コマンド名は以下とする。

```bash
pyselector
````

インストール後、任意のターミナルから実行できること。

```bash
pyselector --help
pyselector inspect
```

---

## 3. コマンド構成

本ツールは以下のサブコマンドを提供する。

```text
pyselector
  inspect   カーソル下のUI要素を調査し、属性情報とセレクター候補を表示する
  tree      対象ウィンドウまたはカーソル下要素を起点にUI要素ツリーを表示する
  version   ツールのバージョンを表示する
```

サブコマンドを省略した場合は、`inspect` を実行したものとして扱う。

```bash
pyselector
```

これは以下と同義である。

```bash
pyselector inspect
```

---

## 4. 共通仕様

## 4.1 対応シェル

以下で実行できること。

* Command Prompt
* PowerShell
* Windows Terminal

## 4.2 文字コード

標準出力はUTF-8を前提とする。

日本語の `window_text`、ウィンドウタイトル、プロセス名を可能な限りそのまま表示する。

## 4.3 標準出力と標準エラー

通常の結果は標準出力へ表示する。

```text
stdout:
  - 要素情報
  - 階層情報
  - セレクター候補
  - ヒット件数
  - コードスニペット
```

エラー、警告、詳細ログは標準エラーへ出力してよい。

```text
stderr:
  - 致命的エラー
  - 例外概要
  - verboseログ
```

ただし、通常利用時の見やすさを優先し、警告をすべてstderrへ分離する必要はない。
セレクター候補に付随する `warning:` は、候補一覧の一部として標準出力に表示する。

---

# 5. inspect コマンド

## 5.1 概要

`inspect` は、一定時間のカウントダウン後に現在のマウスカーソル座標を取得し、その座標上のUI要素を調査する。

取得した要素について、以下を表示する。

* カーソル座標
* 対象ウィンドウ情報
* Win32 Backendの要素情報
* UIA Backendの要素情報
* 親階層
* セレクター候補
* 各セレクター候補のヒット件数
* warningがある場合のwarning
* 最小コードスニペット

## 5.2 基本構文

```bash
pyselector inspect [options]
```

サブコマンド省略時は `inspect` として扱う。

```bash
pyselector [options]
```

## 5.3 オプション一覧

| オプション              |                        値 |      既定値 | 説明                     |
| ------------------ | -----------------------: | -------: | ---------------------- |
| `--delay`          |                       秒数 |      `5` | カーソル位置を取得するまでの待機秒数     |
| `--backend`        | `win32` / `uia` / `both` |   `both` | 使用するバックエンド             |
| `--scope`          |     `window` / `desktop` | `window` | セレクター候補のヒット件数を確認する探索範囲 |
| `--detail`         |                       なし |  `false` | 詳細情報を表示する              |
| `--verbose`        |                       なし |  `false` | 詳細ログを表示する              |
| `--timeout`        |                       秒数 |      `5` | 要素取得・探索処理のタイムアウト秒数     |
| `--max-items`      |                       件数 |       なし | 探索・表示する最大要素数           |
| `--only-visible`   |                       なし |   `true` | 可視要素のみを対象にする           |
| `--include-hidden` |                       なし |  `false` | 非表示要素も対象にする            |

## 5.4 `--delay`

カーソル位置を取得するまでの待機秒数を指定する。

```bash
pyselector inspect --delay 3
```

### 仕様

* 既定値は `5`
* `0` を指定した場合は即時取得する
* 負数は指定不可
* 小数は指定不可
* Ctrl+Cで中断できる
* 中断時の終了コードは `130`

### 表示例

```text
[INFO] 5秒後にカーソル下のUI要素を取得します
[INFO] 5...
[INFO] 4...
[INFO] 3...
[INFO] 2...
[INFO] 1...
```

---

## 5.5 `--backend`

使用するpywinautoバックエンドを指定する。

```bash
pyselector inspect --backend both
pyselector inspect --backend win32
pyselector inspect --backend uia
```

### 指定可能値

| 値       | 説明                                |
| ------- | --------------------------------- |
| `win32` | Win32 Backendのみ使用する               |
| `uia`   | UIA Backendのみ使用する                 |
| `both`  | Win32 BackendとUIA Backendの両方を使用する |

### 既定値

```text
both
```

### 表示順

`both` の場合、セレクター候補は以下の順に表示する。

```text
1. Win32 Backend
2. UIA Backend
```

理由は、従来型のWindowsデスクトップアプリケーションでは、Win32 Backendのほうがパフォーマンス面で有利な場合が多いためである。

---

## 5.6 `--scope`

セレクター候補のヒット件数を確認する探索範囲を指定する。

```bash
pyselector inspect --scope window
pyselector inspect --scope desktop
```

### 指定可能値

| 値         | 説明                          |
| --------- | --------------------------- |
| `window`  | 対象要素が所属するトップレベルウィンドウ配下を探索する |
| `desktop` | デスクトップ全体を探索する               |

### 既定値

```text
window
```

### 方針

通常は `window` を使用する。

`desktop` は探索範囲が広く、処理時間が長くなる可能性があるため、明示指定時のみ使用する。

---

## 5.7 `--detail`

詳細情報を表示する。

```bash
pyselector inspect --detail
```

### 通常表示

通常表示では、要素特定とセレクター生成に必要な主要項目のみを表示する。

### 詳細表示

`--detail` 指定時は、取得できる範囲で以下のような追加情報を表示してよい。

* runtime_id
* framework_id
* localized_control_type
* legacy_properties
* parent情報
* sibling情報
* rectangle詳細
* raw property値

ただし、実装初期段階では主要項目の表示を優先する。

---

## 5.8 `--verbose`

詳細ログを表示する。

```bash
pyselector inspect --verbose
```

### 表示してよい情報

* 使用バックエンド
* カーソル座標取得結果
* 要素取得の試行結果
* トップレベルウィンドウ推定結果
* セレクター候補生成件数
* ヒット件数評価の処理時間
* 例外の概要

通常利用時の出力が読みにくくならないよう、`--verbose` 指定時のみ表示する。

---

## 5.9 `--timeout`

要素取得・探索処理のタイムアウト秒数を指定する。

```bash
pyselector inspect --timeout 10
```

### 仕様

* 既定値は `5`
* 対象は以下の処理とする

  * カーソル下要素の取得
  * 親階層の取得
  * セレクター候補のヒット件数評価
* タイムアウトした場合は、取得済みの情報を可能な範囲で表示する
* タイムアウトした候補には `warning:` を表示する

### 表示例

```text
warning: セレクター評価がタイムアウトしました
```

---

## 5.10 `--max-items`

探索・表示する最大要素数を指定する。

```bash
pyselector inspect --max-items 300
```

### 用途

大量のUI要素を持つ画面で、探索処理が重くなりすぎることを防ぐ。

### 仕様

* 未指定の場合は、実装側の既定値を使用する
* 値は正の整数とする
* 上限に達した場合は、該当候補に `warning:` を表示してよい

### 表示例

```text
warning: 探索上限に達したため、ヒット件数が実際より少ない可能性があります
```

---

## 5.11 `--only-visible` / `--include-hidden`

既定では可視要素のみを対象にする。

```bash
pyselector inspect --only-visible
```

非表示要素も含めたい場合は以下を指定する。

```bash
pyselector inspect --include-hidden
```

### 仕様

* 既定は `--only-visible`
* `--include-hidden` 指定時は非表示要素も探索対象に含める
* 両方が指定された場合は引数エラーとする

---

# 6. tree コマンド

## 6.1 概要

`tree` は、指定した起点からUI要素ツリーを表示する。

主に以下の用途で使用する。

* 対象画面のUI階層を確認する
* `inspect` で取れた要素の周辺構造を確認する
* セレクター候補を考えるために親子関係を見る

## 6.2 基本構文

```bash
pyselector tree [options]
```

## 6.3 起点指定

`tree` コマンドでは、以下のいずれかで起点を指定する。

```text
1. --cursor
2. --window-title
```

どちらも指定されていない場合は引数エラーとする。

両方が指定された場合も引数エラーとする。

---

## 6.4 オプション一覧

| オプション              |               値 |     既定値 | 説明                          |
| ------------------ | --------------: | ------: | --------------------------- |
| `--cursor`         |              なし | `false` | カーソル下要素を起点にする               |
| `--window-title`   |             文字列 |      なし | 対象ウィンドウタイトル                 |
| `--title-re`       |              なし | `false` | `--window-title` を正規表現として扱う |
| `--backend`        | `win32` / `uia` | `win32` | 使用するバックエンド                  |
| `--depth`          |              数値 |     `3` | 表示する探索深度                    |
| `--max-items`      |              件数 |   `200` | 最大表示件数                      |
| `--only-visible`   |              なし |  `true` | 可視要素のみ表示する                  |
| `--include-hidden` |              なし | `false` | 非表示要素も表示する                  |
| `--detail`         |              なし | `false` | 詳細情報を表示する                   |
| `--delay`          |              秒数 |     `5` | `--cursor` 指定時の待機秒数         |

---

## 6.5 `--cursor`

カーソル下の要素を起点にツリーを表示する。

```bash
pyselector tree --cursor
```

`--cursor` 指定時は、`inspect` と同様にカウントダウン後のカーソル位置を使用する。

```bash
pyselector tree --cursor --delay 3
```

---

## 6.6 `--window-title`

指定したタイトルのトップレベルウィンドウを起点にツリーを表示する。

```bash
pyselector tree --window-title "電卓"
```

### 部分一致

既定では完全一致ではなく、実装しやすさと実用性を考慮して部分一致としてよい。

ただし、複数ウィンドウが一致した場合は、候補を表示してエラー終了する。

### 正規表現

`--title-re` を指定した場合、`--window-title` を正規表現として扱う。

```bash
pyselector tree --window-title ".*電卓.*" --title-re
```

---

## 6.7 `--backend`

`tree` コマンドで使用するバックエンドを指定する。

```bash
pyselector tree --window-title "電卓" --backend win32
pyselector tree --window-title "電卓" --backend uia
```

### 指定可能値

| 値       | 説明                 |
| ------- | ------------------ |
| `win32` | Win32 Backendを使用する |
| `uia`   | UIA Backendを使用する   |

### 既定値

```text
win32
```

`tree` は大量要素を表示しやすいため、既定ではWin32を使用する。

---

## 6.8 `--depth`

表示するツリーの深度を指定する。

```bash
pyselector tree --window-title "電卓" --depth 3
```

### 仕様

* 既定値は `3`
* `0` の場合は起点要素のみ表示する
* 負数は指定不可
* 非常に大きな値を指定した場合でも、`--max-items` により表示件数を制限する

---

## 6.9 `--max-items`

最大表示件数を指定する。

```bash
pyselector tree --window-title "電卓" --max-items 300
```

### 仕様

* 既定値は `200`
* 上限に達した場合は、その旨を表示する

表示例。

```text
[WARN] max-items に達したため、以降の要素表示を省略しました。
```

---

# 7. version コマンド

## 7.1 概要

ツールのバージョンを表示する。

## 7.2 基本構文

```bash
pyselector version
```

## 7.3 表示例

```text
pyselector 0.1.0
```

---

# 8. help 表示

## 8.1 ルートヘルプ

```bash
pyselector --help
```

表示内容。

```text
Usage:
  pyselector [command] [options]

Commands:
  inspect   Inspect UI element under cursor
  tree      Show UI element tree
  version   Show version

Options:
  -h, --help  Show help
```

## 8.2 inspect ヘルプ

```bash
pyselector inspect --help
```

表示内容には、`inspect` で利用可能なオプションを含める。

## 8.3 tree ヘルプ

```bash
pyselector tree --help
```

表示内容には、`tree` で利用可能なオプションを含める。

---

# 9. 実行例

## 9.1 基本inspect

```bash
pyselector inspect
```

または。

```bash
pyselector
```

## 9.2 3秒後に取得

```bash
pyselector inspect --delay 3
```

## 9.3 即時取得

```bash
pyselector inspect --delay 0
```

## 9.4 Win32のみで取得

```bash
pyselector inspect --backend win32
```

## 9.5 UIAのみで取得

```bash
pyselector inspect --backend uia
```

## 9.6 デスクトップ全体でヒット件数確認

```bash
pyselector inspect --scope desktop
```

## 9.7 詳細表示

```bash
pyselector inspect --detail
```

## 9.8 詳細ログ表示

```bash
pyselector inspect --verbose
```

## 9.9 カーソル下要素を起点にツリー表示

```bash
pyselector tree --cursor
```

## 9.10 ウィンドウタイトル指定でツリー表示

```bash
pyselector tree --window-title "電卓"
```

## 9.11 UIAでツリー表示

```bash
pyselector tree --window-title "電卓" --backend uia
```

## 9.12 深度指定

```bash
pyselector tree --window-title "電卓" --depth 5
```

---

# 10. 終了コード

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

## 10.1 片方のバックエンドのみ失敗した場合

`--backend both` 指定時、片方のバックエンドで取得に失敗しても、もう片方で取得できた場合は正常終了として扱う。

```text
exit code: 0
```

ただし、取得に失敗したバックエンドについては警告を表示する。

## 10.2 両方のバックエンドで失敗した場合

`--backend both` 指定時、UIA / Win32 の両方で取得に失敗した場合は異常終了とする。

```text
exit code: 1
```

---

# 11. 引数エラー条件

以下の場合は引数エラーとする。

```text
- 未定義のサブコマンドを指定した
- 未定義のオプションを指定した
- --backend に許可されていない値を指定した
- --scope に許可されていない値を指定した
- --delay に負数を指定した
- --timeout に0以下の値を指定した
- --max-items に0以下の値を指定した
- treeで --cursor と --window-title を同時に指定した
- treeで --cursor と --window-title のどちらも指定していない
- --only-visible と --include-hidden を同時に指定した
```

引数エラー時の終了コードは `10` とする。

---

# 12. 提供しないCLI機能

初期版では以下のCLI機能を提供しない。

```text
- --json
- --output
- --copy
- クリップボードコピー
- JSON出力
- ファイル出力
- 操作実行
- 常駐モード
- GUI起動
```

## 12.1 JSON出力を提供しない理由

初期版では、人間がCLI上で確認する用途を優先する。

JSON出力を提供すると、出力スキーマの互換性維持が必要になるため、MVPには含めない。

## 12.2 クリップボードコピーを提供しない理由

初期版では、標準出力から手動でコピーする運用で十分とする。

クリップボード操作は環境差分や依存が増えるため、MVPには含めない。

---

# 13. インストール後の確認コマンド

`pip install .` 後、以下が実行できること。

```bash
pyselector --help
```

```bash
pyselector version
```

```bash
pyselector inspect --delay 0
```

---

# 14. CLI仕様上の優先方針

本ツールのCLIは、以下を優先する。

```text
- コマンドを短くする
- 既定値でそのまま使えるようにする
- inspectを最短で実行できるようにする
- Win32を優先しつつ、UIAも確認できるようにする
- 出力は人間が読む前提にする
- 余計な推奨ラベルや理由説明は表示しない
- warningが必要な場合のみ表示する
```
