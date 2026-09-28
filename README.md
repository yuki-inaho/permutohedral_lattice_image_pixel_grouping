# Permutohedral segmentation lab

C++17の包含単体探索をnanobindから呼び出す画像領域分割の研究用プロジェクトです。位置だけの三角形状分割、位置＋RGBの直接分割、明示的な隣接領域併合を分離しています。SLICや学習済みモデルは使用しません。

## この配布物の検証状態

**計算部分とPython側の処理は検証済みですが、nanobindの実ビルドとuvによる依存解決は未検証です。** 作成環境からPyPIへ接続できず、`uv sync --all-groups` がDNSエラーで停止しました。そのため **`uv.lock` は未生成** です。手作業で解決済みに見せたロックファイルや、未検証のwheelは含めていません。

C++本体をテスト専用のC ABI経由で呼び出し、121件のPythonテスト、旧版22条件との全画素ラベル一致、3冊のNotebookを確認しました。nanobind固有の8テストは明示的にスキップしています。実行済みNotebookの冒頭にも使用した接続方式を表示しています。テスト専用の接続は、通常のインストール先には含まれません。

詳細は [検証結果](docs/VALIDATION.md)、[作業記録](docs/WORKLOG.md)、[実コマンドと終了コード](reports/verification.json) を参照してください。

## 初回セットアップ

Python 3.11以上、uv 0.10以上、C++17対応コンパイラ、Python開発用ヘッダー、インターネット接続が必要です。標準の開発用Pythonは `.python-version` で3.13を選択しています。OS別の前提は [可搬性・環境管理](docs/PORTABILITY.md) にあります。

アーカイブを展開し、プロジェクトのルートで実行します。

```sh
python scripts/verify_manifest.py
python scripts/bootstrap.py
uv run --locked --all-groups python scripts/verify.py --notebooks
uv run --locked --all-groups jupyter lab
```

`bootstrap.py` はロックファイルがなければ `uv lock` を実行し、続いて `uv sync --locked --all-groups` を実行します。生成された **`uv.lock` を `pyproject.toml` と一緒に版管理してください**。既存のロックがある場合は勝手に更新せず、整合性を確認して同期します。初回の依存解決結果は作成環境では検証できていません。

JupyterLabから `notebooks/01_spatial_partition.ipynb` を開いてください。通常実行ではnanobindを使用します。`PERMUTOHEDRAL_TEST_BRIDGE` を設定する必要はありません。全Notebookの非対話実行には `scripts/run_notebooks.py` を使用できます。

## Pythonからの利用

```python
from permutohedral_segmentation import LatticeConfig, MergeConfig, segment
from permutohedral_segmentation.datasets import load_example
from permutohedral_segmentation.io import save_result

image = load_example("peppers")

# 位置だけによる包含単体への直接割り当て。領域併合はしません。
triangles = segment(image, lattice=LatticeConfig(mode="xy", spatial_scale=0.025))
assert triangles.region_count == 405

# 位置＋RGBの単体分割と、その後の明示的な隣接領域併合。
regions = segment(
    image,
    lattice=LatticeConfig(mode="xyrgb", spatial_scale=0.025, color_scale=0.01),
    merge=MergeConfig(target_regions=300),
)
assert regions.region_count == 300
save_result("outputs/peppers-300", image, regions)
```

入力画像は `(高さ, 幅, 3)` のRGB、`uint8`、値域0～255です。`float` の画像を暗黙に255倍しません。位置は画素中心 `(x+0.5, y+0.5)` を使用します。尺度は特徴量への倍率であり、領域数ではありません。

`result.labels` は読み取り専用の `int32` 配列です。変更する際は `.copy()` を使います。`simplex_count` は単体IDの種類数、`component_count` は併合前の4近傍連結成分数、`region_count` は最終出力ラベル数です。直接分割では同じIDが画像上で非連結になることがあります。

任意の1～8次元の特徴量には `label_features(features)` を使えます。`locate_simplices(features)` は包含単体の頂点、重心座標、埋め込み後の位置を返します。APIの境界と制約は [設計](docs/ARCHITECTURE.md) に記載しています。

## コマンドライン

```sh
uv run --locked permutohedral --example peppers --mode xy --spatial-scale 0.025 --output outputs/triangles
uv run --locked permutohedral --input path/to/image.png --mode xyrgb --target-regions 300 --output outputs/regions
uv run --locked --all-groups python scripts/reproduce.py
uv run --locked --all-groups python scripts/run_notebooks.py
```

`experiments.toml` が22条件の設定の唯一の定義です。`scripts/reproduce.py` は同じPython APIで実験を実行し、`reference/golden/` の旧版ラベルと厳密比較します。`results/` 内の既存結果は上書きされるため、過去の計測を残す場合は先に別の場所へ保存してください。

各結果は `labels.npz`、`metadata.json`、`regions.png`、`overlay.png`、`mean.png`、`mean_boundaries.png` からなります。PNGは確認用で、後続処理には整数ラベルのNPZを使います。今回の実測値は `results/manifest.json` にあります。

## 構成

```text
cpp/                  C++17の計算本体とnanobind接続
src/permutohedral_segmentation/
  config.py           検証付きの不変な設定
  api.py              共通の公開API
  features.py         画像から特徴量を構成
  io.py               PNG・NPZ・JSONの入出力
  visualization.py    ラベル表示・境界・領域平均色
notebooks/            再実行用のNotebook 3冊
reports/notebooks/    出力を保存した実行済みNotebook
experiments.toml      再現する実験条件
results/              22条件の再実行結果
tests/                Python・C++・回帰・nanobind境界のテスト
reference/            旧コード・基準ラベル・元ファイルのSHA-256
scripts/              環境構築・検証・再実験・配布物作成
reports/              実行ログ・環境・機械可読の検証記録
docs/                設計・運用・検証・作業記録
```

計算はC++本体に一度だけ実装しています。コマンドラインとNotebookは同じPython APIを使い、計算処理を再実装しません。必要のない継承階層や汎用的な部品登録機構は導入していません。

## 開発と配布

```sh
uv run --locked --all-groups pytest
uv run --locked --all-groups ruff check src scripts tests
uv run --locked --all-groups mypy
uv build
python scripts/package_release.py --output ../permutohedral-lab-0.2.0.tar.zst
```

Ruff・mypy・wheel/sdist作成は設定と手順を用意していますが、今回の環境では実行できていません。C++を変更した場合の再ビルドとNotebookカーネルの再起動は [可搬性・環境管理](docs/PORTABILITY.md) を確認してください。

配布スクリプトには外部コマンド `zstd` が必要です。ファイル順・時刻・所有者情報を固定し、SHA-256一覧と圧縮ファイルの検査用ハッシュを生成します。`.venv`、ビルド成果物、キャッシュ、共有ライブラリ、フォントは配布物に含めません。圧縮物はソースと作業記録の引き渡し用であり、ネット接続不要の完成済み実行環境ではありません。

新規コードのライセンスはMIT、継承した単体探索には元のBSD通知を維持しています。同梱画像の権利は新規に付与していません。公開配布前に [第三者の権利・出典](THIRD_PARTY_NOTICES.md) を確認してください。
