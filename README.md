# pyselector

pyselector は、Windows の UI 要素を調査し、pywinauto のセレクター候補を生成する CLI ツールです。

pywinauto による自動化でデスクトップ UI 要素を特定する必要がある、QA エンジニア、テスト自動化開発者、RPA スクリプト作成者向けです。

## インストール

```bash
pip install .
```

開発用:

```bash
pip install -e .
```

## コマンド

```bash
pyselector --help
pyselector version
pyselector inspect
pyselector inspect --delay 0
pyselector inspect --backend win32
pyselector inspect --backend uia
pyselector tree --cursor
pyselector tree --window-title "電卓"
```

サブコマンドを指定しない場合は、`inspect` が使用されます。

## Inspect

`inspect` は設定された遅延時間だけ待機し、現在のカーソル位置を読み取ったうえで、カーソル下の UI 要素を Win32 と UIA のバックエンドで調査します。

```bash
pyselector inspect --delay 5 --backend both --scope window
```

出力には次の情報が含まれます。

- カーソル位置
- 対象ウィンドウの情報
- Win32 / UIA 要素の属性
- 親階層
- pywinauto セレクター候補
- ヒット数と警告
- 最小限の pywinauto コードスニペット

## Tree

`tree` は、カーソル位置の要素またはウィンドウタイトルを起点に、コンパクトな UI 要素ツリーを出力します。

```bash
pyselector tree --window-title "電卓" --backend uia --depth 3
```

## 注意事項

この初期バージョンでは、JSON 出力、ファイル出力、クリップボードへのコピー、GUI モード、常駐モード、クリックや入力などの UI 操作は意図的に提供していません。このツールは、調査、セレクター候補、ヒット数の確認に重点を置いています。
