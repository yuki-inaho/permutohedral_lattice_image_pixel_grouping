# 可搬性と環境管理

## 対象と実測済みの範囲

設定上の対象は通常版CPython 3.11～3.14です。標準の開発バージョンは3.13です。今回の実行確認はLinux x86_64、CPython 3.13.5のみです。C++本体はGNU C++ 14.2とClang 17でビルド・テストしました。Windows/macOS、ARM、別のPython版、free-threaded Python、nanobind拡張、wheelの可搬性は未検証です。対応設定と実測済みの対応を混同しないでください。

C++は標準C++17とCMakeを使い、`-march=native` やLinux専用の処理には依存させていません。MSVCとGNU/Clangの警告・浮動小数点オプションは分けています。サンプル画像は `importlib.resources` で参照し、作成環境の絶対パスに依存しません。Notebookの実行器は現在のPythonで一時カーネルを作り、利用者のカーネル登録を変更しません。

## 必要な道具

uvは公式の導入手順に従ってインストールしてください。LinuxではC++コンパイラ・Python開発用ヘッダー、macOSではCommand Line Tools、WindowsではMSVCのC++ビルド環境が必要です。CMake 3.18以上はビルド用設定から要求します。C++側のPNGライブラリやOpenCV、CUDA、TensorFlowは不要です。

一般的なLinux構成では `g++` と `python3-dev` 相当、macOSでは `clang++`、WindowsではVisual StudioのC++ビルドツールを使用します。これらのOS別導入自体は今回実行していません。配布物の再圧縮だけに外部コマンド `zstd` が必要で、通常の画像分割には不要です。

## uvの初回操作と固定

```sh
python scripts/bootstrap.py
```

この配布ではPyPIへの接続失敗により `uv.lock` がありません。上記は初回だけ `uv lock` で依存関係を解決し、`uv sync --locked --all-groups` で構築します。以後は `uv.lock` を版管理し、次の操作を使います。

```sh
uv sync --locked --all-groups
uv run --locked --all-groups python scripts/verify.py --notebooks
```

`--locked` はロックの変更が必要なら失敗する運用です。`--frozen` で変更検出を回避する設定にはしていません。Python版、OS、CPUが異なればwheelは作り直す前提です。ロックファイルもコンパイラやOSライブラリそのものを固定するものではありません。

ビルド用直接依存は `nanobind==3.1.0` と `scikit-build-core==1.1.0` に固定しています。通常依存・開発依存には互換範囲を記述しています。**現時点で依存グラフ全体を固定できたとは主張しません。** `reports/environment.json` は実際に使った既存環境の記録で、uv.lockの代替ではありません。

依存更新は意図的に行い、差分と回帰結果を確認します。

```sh
uv lock --upgrade
uv sync --locked --all-groups
uv run --locked --all-groups python scripts/verify.py --notebooks
```

## C++の変更とNotebook

uvのキャッシュ判定に `cpp/**/*.cpp`、`cpp/**/*.hpp` とCMake設定を含めています。C++を変更した場合は同期後にNotebookのカーネルを再起動してください。必要なら明示的に再インストールします。

```sh
uv sync --locked --all-groups --reinstall-package permutohedral-segmentation
```

Pythonの編集可能インストールであっても、ロード済みの共有ライブラリを安全に差し替える仕組みとは異なります。Notebook内の状態だけを使って再現できたと判断せず、`scripts/run_notebooks.py` で新しいカーネルから再実行します。

## 配布と独立インストールの確認

```sh
uv build
uv venv --python 3.13 wheel-check
uv pip install --python wheel-check/bin/python dist/<実際に生成されたwheelの名前>.whl
wheel-check/bin/python tests/smoke_installed.py
```

WindowsではPythonのパスを `wheel-check/Scripts/python.exe` に読み替えてください。これは独立環境への確認手順であり、この配布作成時には未実行です。PyPIなどへの公開は自動化していません。サンプル画像の権利を確認せずに公開しないでください。

`.github/workflows/ci.yml` は3OS×3Python版のビルド・テスト設定です。まず初回構築で生成した `uv.lock` をコミットしてから使用してください。CIは今回外部サービス上で起動していません。Ruff・mypyの設定もありますが、導入できなかったため未実行です。

## ネット接続できない検証環境での操作

今回使った方式は、必要なNumPy・Pillow・pytest・Jupyter関係のパッケージとC++コンパイラが既に入っている場合に限ります。新しいPCへオフラインで全環境を構築する手順ではありません。

```sh
python scripts/verify.py --offline-native --notebooks
```

または既存のPythonをuv経由で選択します。

```sh
uv run --no-project --python <既存のPython実行ファイル> python scripts/verify.py --offline-native --notebooks
```

`--no-project` はプロジェクトの依存同期を行いません。この実行をもって `uv sync` やnanobindの動作確認済みとは扱いません。接続方式は記録に保存されます。C++本体だけを検証する場合は次の操作です。

```sh
cmake -S . -B build/native -DPERMUTOHEDRAL_BUILD_PYTHON=OFF -DPERMUTOHEDRAL_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build/native --config Release --parallel 2
ctest --test-dir build/native -C Release -V --output-on-failure
python scripts/check_native_variants.py
```

最後の操作はGNU/Clangの存在を確認し、GNUではASan/UBSan、Clangでは通常の最適化ビルドを検証します。OS別のABIや共有ライブラリのPython接続までは対象にしません。

## 結果の可搬性

ラベルはNPZのint32、メタデータはUTF-8 JSONで、旧版の生バイナリのように画像寸法を別途推測する必要はありません。描画にフォントファイルは不要です。格子境界や併合コストのほぼ同値の点は浮動小数点の丸めの影響を受けます。今回の全画素一致は同じLinux環境での旧版との比較であり、任意のコンパイラ・CPU間の完全一致を保証するものではありません。
