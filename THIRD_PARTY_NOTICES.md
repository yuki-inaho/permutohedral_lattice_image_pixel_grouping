# 第三者の権利と出典

## 包含単体探索

本体の単体探索は、ユーザー提供の `probreg-master(2).zip` 内の `third_party/permutohedral/permutohedral.cpp` と、前回作成した `lattice_segment.cpp` の系統を引き継いでいます。原著作権者の表示は **Copyright (c) 2013, Philipp Krähenbühl** です。元ファイルにあるBSD形式の通知を `cpp/include/permutohedral/lattice.hpp` と `LICENSES/permutohedral-BSD-3-Clause.txt` に保持しています。

旧版と元アーカイブのSHA-256は `reference/provenance.json` にあります。旧版の単体探索コードと既存の通知は `reference/legacy/` に保持しています。probregの上位プロジェクトのライセンスだけで、この第三者ファイルの個別通知を置き換えていません。

## nanobindとその依存

本プロジェクトのビルド用依存はnanobind 3.1.0です。作成環境ではパッケージを取得できず、nanobind本体やバイナリは同梱していません。公式 `v3.1.0` のLICENSEを確認し、`LICENSES/nanobind-BSD-3-Clause.txt` に収録しました。元ファイルのGit blob SHAは `3d3426d400064d53d291c028457f699b3edf9b7c` です。

nanobindの公式 `.gitmodules` が参照する `Tessil/robin-map` のMIT通知は `LICENSES/robin-map-MIT.txt` に収録しました。確認したLICENSEのGit blob SHAは `e9c5ae95f36a6b4e4e9937adcc674b155f8011c8` です。将来wheelをビルドする場合も、同梱対象となるコードの実バージョンに対応する通知を確認してください。`wheel.license-files` は本ファイルと `LICENSES/` を含める設定です。

NumPy、Pillow、uv、scikit-build-core、Jupyter、および開発ツールの実体は、このソースアーカイブには同梱していません。それぞれの配布物に含まれるライセンスが適用されます。インストール済み環境や依存コードを本プロジェクトの新規コードとして再ライセンスしていません。

## 画像と計算結果

`data/peppers.png`、`data/cow.png` は、この会話でユーザーが提供した画像を用いた前回実験から引き継いでいます。権利者や第三者への再配布許諾は確認していません。本配布で新しい画像ライセンスを付与するものではありません。

画像を含むNotebook出力、結果PNG、サンプル画像入りwheelを第三者に公開する場合は、画像について別途権利を確認してください。これはユーザーへの作業結果の返却用アーカイブです。新規コードのMIT通知を画像にも適用したと解釈しないでください。

## 参考のみの資料

会話で参照された `MiguelMonteiro/permutohedral_lattice`、`ufoym/recursive-bf`、論文図は手法の検討資料です。本プロジェクトでこれらのパッケージを実行・内包したと主張していません。特に再帰型両側フィルタを今回の分割処理に使用していません。論文の結果を再現したとする主張や、SLICとの優劣評価も含めていません。
