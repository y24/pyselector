# セレクター候補パターン一覧

このドキュメントは、現在の実装でセレクター候補として生成され、ヒット数チェックの対象になる `child_window(...)` 条件の組み合わせをまとめる。

対象実装:

- `pyselector/selector/win32_generator.py`
- `pyselector/selector/uia_generator.py`
- `pyselector/selector/evaluator.py`
- `pyselector/inspect_runner.py`

## 評価フロー

`inspect` 実行時は、バックエンドごとに以下の順で候補を評価する。

1. 通常候補を生成してヒット数を評価する。
2. `hits == 1` の候補がない場合、親要素の `class_name + found_index` を使うフォールバック候補を追加する。
3. 複数ヒットした候補のうち、対応する `found_index` 候補を生成できるものを追加する。
4. 重複排除と表示順ソート後、候補全体を再評価する。
5. `hits == 0` の候補と、失敗した親 `class_name + found_index` 試行候補は表示対象から除外する。

`found_index` の試行数は既定で `0..2` の3件分。
設定値が渡された場合は、その件数分を `0` から順に試行する。

## 共通ルール

- 空値は候補生成に使わない。
- `window_text` は selector 上では `title` として出力する。
- UIA の `automation_id` は selector 上では `auto_id` として出力する。
- `control_id` と `handle` は、現在の候補生成では使用しない。
- 親要素経由候補は、直近の親要素だけをスコープとして使う。
- 重複判定は `(backend, selector_text)` の完全一致。

## Win32 候補

### 通常候補

| selector_kind | セレクター条件 | 生成条件 | display_order |
| --- | --- | --- | ---: |
| `win32_title_class_name` | `title + class_name` | 対象要素の `window_text` と `class_name` がある | 20 |
| `win32_title` | `title` | 対象要素の `window_text` がある | 70 |

例:

```python
dlg.child_window(title="OK", class_name="Button")
dlg.child_window(title="OK")
```

### 親要素経由候補

親条件と子条件の直積で候補を作る。

親条件:

| parent_kind | 親セレクター条件 | 生成条件 |
| --- | --- | --- |
| `title_class_name` | `title + class_name` | 親要素の `window_text` と `class_name` がある |

子条件:

| target_kind | 子セレクター条件 | 生成条件 |
| --- | --- | --- |
| `title_class_name` | `title + class_name` | 対象要素の `window_text` と `class_name` がある |
| `title` | `title` | 対象要素の `window_text` がある |

生成される `selector_kind`:

| selector_kind | セレクター条件 |
| --- | --- |
| `win32_parent_title_class_name_target_title_class_name` | 親 `title + class_name` -> 子 `title + class_name` |
| `win32_parent_title_class_name_target_title` | 親 `title + class_name` -> 子 `title` |

例:

```python
dlg.child_window(title="Combo", class_name="ComboBox").child_window(title="Value", class_name="Edit")
dlg.child_window(title="Combo", class_name="ComboBox").child_window(title="Value")
```

### 親 found_index フォールバック候補

通常候補が存在しない場合、または通常候補の初回評価で `hits == 1` がない場合に生成される。

| selector_kind | セレクター条件 | 生成条件 |
| --- | --- | --- |
| `win32_parent_class_name_found_index_target_class_name` | 親 `class_name + found_index` -> 子 `class_name` | 親要素と対象要素の `class_name` がある |

例:

```python
dlg.child_window(class_name="ComboBox", found_index=0).child_window(class_name="Edit")
dlg.child_window(class_name="ComboBox", found_index=1).child_window(class_name="Edit")
dlg.child_window(class_name="ComboBox", found_index=2).child_window(class_name="Edit")
```

### 後追加 found_index 候補

初回評価で複数ヒットした候補から、対象要素の位置を特定できた場合だけ追加される。

| 元の selector_kind | 追加される selector_kind | セレクター条件 |
| --- | --- | --- |
| `win32_title` | `win32_title_found_index` | `title + found_index` |

`win32_class_name_found_index` のビルダーは存在するが、現在の通常候補では `win32_class_name` を生成していないため、通常フローでは追加元がない。

例:

```python
dlg.child_window(title="OK", found_index=1)
```

## UIA 候補

### 通常候補

| selector_kind | セレクター条件 | 生成条件 | display_order |
| --- | --- | --- | ---: |
| `uia_auto_id_control_type` | `auto_id + control_type` | 対象要素の `automation_id` と `control_type` がある | 10 |
| `uia_title_auto_id_control_type` | `title + auto_id + control_type` | 対象要素の `window_text`, `automation_id`, `control_type` がある | 20 |
| `uia_auto_id` | `auto_id` | 対象要素の `automation_id` がある | 30 |
| `uia_title_control_type` | `title + control_type` | 対象要素の `window_text` と `control_type` がある | 40 |
| `uia_title_re_control_type` | `title_re + control_type` | 対象要素の `window_text` と `control_type` がある | 50 |
| `uia_title` | `title` | 対象要素の `window_text` がある | 70 |

例:

```python
dlg.child_window(auto_id="num1Button", control_type="Button")
dlg.child_window(title="1", auto_id="num1Button", control_type="Button")
dlg.child_window(auto_id="num1Button")
dlg.child_window(title="1", control_type="Button")
dlg.child_window(title_re="^1$", control_type="Button")
dlg.child_window(title="1")
```

### 親要素経由候補

親条件と子条件の直積で候補を作る。
ただし、親条件は最大4種類、子条件は最大3種類に制限される。

親条件:

| parent_kind | 親セレクター条件 | 生成条件 |
| --- | --- | --- |
| `auto_id_control_type` | `auto_id + control_type` | 親要素の `automation_id` と `control_type` がある |
| `title_auto_id_control_type` | `title + auto_id + control_type` | 親要素の `window_text`, `automation_id`, `control_type` がある |
| `auto_id` | `auto_id` | 親要素の `automation_id` がある |
| `title_control_type` | `title + control_type` | 親要素の `window_text` と `control_type` がある |

子条件:

| target_kind | 子セレクター条件 | 生成条件 |
| --- | --- | --- |
| `auto_id_control_type` | `auto_id + control_type` | 対象要素の `automation_id` と `control_type` がある |
| `title_control_type` | `title + control_type` | 対象要素の `window_text` と `control_type` がある |
| `auto_id` | `auto_id` | 対象要素の `automation_id` がある |
| `title` | `title` | 対象要素の `window_text` がある |

子条件は先頭3件だけが使われるため、`title` は `auto_id_control_type`, `title_control_type`, `auto_id` がすべて生成できる場合は親要素経由候補には含まれない。

生成される `selector_kind` は次の形式になる。

```text
uia_parent_<parent_kind>_target_<target_kind>
```

例:

```python
dlg.child_window(auto_id="parent", control_type="Pane").child_window(auto_id="child", control_type="Button")
dlg.child_window(title="Parent", control_type="Pane").child_window(title="Open", control_type="Button")
dlg.child_window(auto_id="parent").child_window(auto_id="child")
```

### 親 found_index フォールバック候補

通常候補が存在しない場合、または通常候補の初回評価で `hits == 1` がない場合に生成される。

親条件は `class_name + found_index` 固定。
子条件は通常の UIA 子条件に加え、対象要素の `class_name` がある場合は最後に `class_name` が追加される。

| selector_kind | セレクター条件 |
| --- | --- |
| `uia_parent_class_name_found_index_target_auto_id_control_type` | 親 `class_name + found_index` -> 子 `auto_id + control_type` |
| `uia_parent_class_name_found_index_target_title_control_type` | 親 `class_name + found_index` -> 子 `title + control_type` |
| `uia_parent_class_name_found_index_target_auto_id` | 親 `class_name + found_index` -> 子 `auto_id` |
| `uia_parent_class_name_found_index_target_title` | 親 `class_name + found_index` -> 子 `title` |
| `uia_parent_class_name_found_index_target_class_name` | 親 `class_name + found_index` -> 子 `class_name` |

例:

```python
dlg.child_window(class_name="ComboBox", found_index=0).child_window(auto_id="DropDown", control_type="Button")
dlg.child_window(class_name="ComboBox", found_index=1).child_window(title="Open", control_type="Button")
dlg.child_window(class_name="ComboBox", found_index=2).child_window(class_name="Button")
```

### 後追加 found_index 候補

初回評価で複数ヒットした候補から、対象要素の位置を特定できた場合だけ追加される。

| 元の selector_kind | 追加される selector_kind | セレクター条件 |
| --- | --- | --- |
| `uia_control_type` | `uia_control_type_found_index` | `control_type + found_index` |

`uia_control_type_found_index` のビルダーは存在するが、現在の通常候補では `uia_control_type` を生成していないため、通常フローでは追加元がない。

例:

```python
dlg.child_window(control_type="Button", found_index=3)
```

## ヒット数チェックの方法

単体候補は `candidate.condition` をそのまま使って探索し、見つかった件数を `hits` とする。

```python
dlg.child_window(title="OK", class_name="Button")
```

親要素経由候補は `steps` を順に評価する。
この場合は、親条件に一致した件数が `parent_hits` にも入る。

```python
dlg.child_window(title="Parent", class_name="Pane").child_window(title="OK", class_name="Button")
```

`found_index` 付き候補は、まず `found_index` を除いた条件で一覧を取得し、そのインデックスに要素があれば `hits = 1`、なければ `hits = 0` とする。

```python
dlg.child_window(title="OK", found_index=1)
```

再評価時は、`hits == 1` でも対象要素またはカーソル位置と一致しない場合は `hits = 0` に補正される。
