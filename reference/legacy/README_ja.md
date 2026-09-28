# Permutohedral lattice の単体による画像領域分割

提供された図の三角形状の分割を目標にした、実行済みの試作実装です。
分割、連結成分抽出、任意の隣接領域併合、個別PNG出力はC++17で実行します。
SLIC、k-means、学習済みモデル、画像生成モデルは使用していません。

## 最初に見る結果

- `xy_comparison.png`：位置だけによる三角形単体分割。後処理なし。
- `color_comparison.png`：位置＋RGBの直接分割と、300領域への併合後を区別した比較。
- `cow_comparison.png`：牛画像に対する100・300・500領域への併合結果。
- `reference_layout.png`：提示図と同じ7列の特徴量構成による補足比較。

著者の実験画像・コード・座標正規化・格子基底まで一致させた論文の厳密再現ではありません。
提示画像の構成を参考に、元のpermutohedral latticeの単体探索から実装しています。

## 入力画像

`inputs/peppers.png` は提供された512×512画素の画像です。
`inputs/cow.png` は提供された比較図の左上から `[0,418) × [0,235)` を切り出した画像です。
入力はリサイズせずに分割しています。比較図を組む段階だけ、表示寸法を変更しています。
ピーマン画像のRGBの異なる組合せは252通りでした。画像には細かな画素間の色変動があり、
今回の色特徴量による直接分割は多数の微小な連結成分を生じました。

## 方法

### 単体分割：後処理なし

画素の添字を0始まりの `(i,j)` とし、座標は画素中心 `x=i+0.5, y=j+0.5` とします。
RGBは入力の8ビット値、範囲0～255です。

- `xy`：特徴量 `(spatial_scale*x, spatial_scale*y)`、2次元。
- `rgb`：特徴量 `(color_scale*R, color_scale*G, color_scale*B)`、3次元。
- `xyrgb`：位置2成分とRGB3成分を結合した特徴量、5次元。

標準的な実装の係数 `sqrt(2/3)*(D+1)` を含む持ち上げ変換を用います。
これはフィルタ用実装の `with_blur=true` に対応する座標尺度を保持するための係数です。
本実験では、平滑化、splat、blur、slice自体は実行していません。

特徴ベクトルを座標和0の超平面に持ち上げ、丸めと残差の順位から包含単体を求めます。
その単体の `D+1` 個の頂点座標を辞書式順序に並べた組を、単体の識別子にします。
ハッシュ値だけで識別せず、キー全体の一致を確認するため、ハッシュ衝突による誤併合はありません。

「最も近い格子頂点」や「最大重心座標の頂点」だけの識別子ではなく、
**包含単体全体の識別子**を使う点が三角形状の領域を得る要点です。
`xy`では画像内容を使わないため、輪郭には追従しません。
同じ画像寸法・同じ尺度なら、入力の色が変わってもラベル配列は同じです。

この実装の2次元格子では、三角形の一辺は連続座標上で `1/spatial_scale` 画素です。
内部三角形の面積は `sqrt(3)/(4*spatial_scale^2)` なので、
大きな画像では領域数はおおむね `4*N*spatial_scale^2/sqrt(3)` に比例します。
画像端の切断やラスタ化の影響があるため、これは厳密な領域数の式ではありません。
領域数を0.05などの倍率から直接指定する仕組みではありません。

### 任意の後処理：連結成分の隣接併合

`--target K` を0より大きくすると、まず同一単体IDの画素を4近傍の連結成分に分けます。
その後、画像上で隣接する成分だけを貪欲に併合し、K個の連結領域にします。
これは単体探索とは別の処理です。色を加えただけでK個の領域になるわけではありません。

併合では画素ごとの5次元量

`g = (R/48, G/48, B/48, compactness*x/S, compactness*y/S)`

を使います。`S=sqrt(N/K)`、既定の `compactness=0.3` です。
48は `--merge-color-sigma` で変更できます。隣接領域A,Bのコストは、
領域内平方誤差の増分

`cost(A,B) = nA*nB/(nA+nB) * ||mean(gA)-mean(gB)||^2`

です。最小コストの隣接対から併合し、領域の統計と隣接関係を更新します。
グローバル最適解やSLICと同等の品質を保証するものではありません。
Kが初期連結成分数より大きい場合はエラーにし、別の分割を黙って挿入しません。

## ビルドと実行

必要なのはC++17対応コンパイラとlibpngの開発用ファイルです。
OpenCV、Eigen、TensorFlow、CUDAは不要です。

```sh
g++ -std=c++17 -O3 -Wall -Wextra -Wpedantic src/lattice_segment.cpp -lpng -o lattice_segment
./lattice_segment --self-test

# 位置だけ：三角形単体を直接領域にする
./lattice_segment --input inputs/peppers.png --out results/demo_xy \
  --mode xy --spatial-scale 0.05

# 位置＋RGB：単体IDをそのまま出力
./lattice_segment --input inputs/peppers.png --out results/demo_raw \
  --mode xyrgb --spatial-scale 0.025 --color-scale 0.01

# 位置＋RGB：単体分割後に300個の連結領域へ併合
./lattice_segment --input inputs/peppers.png --out results/demo_k300 \
  --mode xyrgb --spatial-scale 0.025 --color-scale 0.01 --target 300
```

CMakeも使用できます。

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
```

同梱の全22条件を再実行する場合は、Python 3.8以上で次を実行します。
Pythonは実行制御のみであり、領域分割の計算はC++です。

```sh
python3 run_experiments.py
```

比較図の再作成はPillowと日本語フォントが必要です。フォントファイルは同梱していません。

```sh
python3 make_comparisons.py --font /path/to/japanese-font.ttf \
  --bold-font /path/to/japanese-bold-font.ttf
```

比較図の見出しにある領域数は同梱条件の実測値です。実験条件を変更した場合は、
`make_comparisons.py` の見出しの数値も新しいJSONの実測値に合わせて変更してください。

## 個別出力

指定した出力接頭辞に対し、次のファイルを出力します。

- `_regions.png`：領域IDの識別用色。意味クラスや元画像の色ではありません。
- `_overlay.png`：元画像に1画素のラスタ境界を重ねた結果。
- `_mean.png`：各ラベルに属する画素のRGB平均色。
- `_mean_boundaries.png`：平均色と境界。
- `_labels.u32`：行優先・リトルエンディアン・符号なし32ビットのラベル配列。0始まり。
- `.json`：幅、高さ、設定、単体ID数、連結成分数、出力ラベル数、処理時間。

ラベル配列は幅×高さ個あり、寸法は同名のJSONに保存されています。
上・左方向の境界と重複して太くならないよう、境界描画は右・下の隣接画素との相違を使っています。
`rgb`や`xyrgb`の直接分割では、同じIDの画素が画像内で離れた場所に存在し得ます。
この場合の `_mean.png` は同一IDの非連結部分をまとめた平均色です。

## 実測結果

ピーマン512×512画素、後処理なし：

| 特徴量 | 尺度 | 単体ID数 | 4近傍連結成分数 |
|---|---|---:|---:|
| xy | 0.050 | 1,590 | 1,590 |
| xy | 0.025 | 405 | 405 |
| xy | 0.010 | 72 | 72 |
| xyRGB | 位置0.025、色0.010 | 16,350 | 90,755 |

最後の条件を隣接併合した結果は、100・300・500個それぞれの連結領域です。
全条件の記録は `results/experiment_manifest.json` にあります。

## 実行時間と検証

CPU単一スレッド、g++ 14.2.0、`-O3` で計測しました。
予備実行1回の後に5回計測し、中央値を採用しています。
読み込み・PNG書き出し・可視化・最終連結性の検査を除外しています。

- xy、尺度0.05：単体ID計算約14.6 ms、連結成分集計などを含む計算部分約16.8 ms。
- xyRGB、直接分割：計算部分約53.1 ms。
- xyRGB、300領域への隣接併合込み：計算部分約742.6 ms。

これはこの環境・この入力・この実装での値です。他手法との速度比較ではありません。
後処理の併合が大半の時間を占めています。
詳細な各回の計測値と環境情報は `tests/benchmark.json` に記録しています。

2・3・5次元について各10,000点で、重心座標の非負性・和が1であること、
頂点の超平面条件、重心座標による元位置の復元、変換の往復、
単体の重心で同じ識別子が得られることを検査しました。
最大の復元誤差は約2.3e-13でした。結果は `tests/geometry.txt` にあります。
出力ラベル数と連結性は別実装でも検査し、`tests/validation.json` に記録しています。
正解領域データはないため、境界再現率やSLICに対する精度の優劣は評価していません。

## 実装の出典と位置づけ

単体探索は、アップロードされたprobregの
`third_party/permutohedral/permutohedral.cpp` のスカラー版を参考にしています。
標準ライブラリ中心の独立実装へ移し、単体の識別子、PNG入出力、
隣接併合、可視化、検証を追加しました。元の著作権表示とライセンスを
ソース先頭および `THIRD_PARTY_NOTICES.txt` に保持しています。

アルゴリズムの一次資料：
Andrew Adams, Jongmin Baek, Abe Davis,
“Fast High-Dimensional Filtering Using the Permutohedral Lattice”, Eurographics 2010.
公式配布元：graphics.stanford.edu/papers/permutohedral/

提示図の資料：
Varun Jampani, “Learning Inference Models for Computer Vision”,
学位論文、2017、arXiv:1709.00069。
資料中の図の画像座標の正規化や格子の向きまでは照合できていません。
今回の結果を論文の厳密再現と扱わないでください。
