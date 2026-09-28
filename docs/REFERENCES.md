# 参照資料

確認日: 2026-09-27。ビルド・環境管理の設定は以下の公式資料を参照しています。ページ内容の参照ができたことと、実行環境から依存パッケージを取得できたことは別です。

- nanobind: パッケージ作成とscikit-build-coreとの接続
  https://nanobind.readthedocs.io/en/latest/packaging.html
- nanobind: NumPy配列、型・連続性、所有権、GIL
  https://nanobind.readthedocs.io/en/latest/ndarray.html
- nanobind 3.1.0: パッケージ情報
  https://pypi.org/project/nanobind/3.1.0/
- scikit-build-core: 設定
  https://scikit-build-core.readthedocs.io/en/latest/configuration/index.html
- scikit-build-core 1.1.0: パッケージ情報
  https://pypi.org/project/scikit-build-core/1.1.0/
- uv: 同期とロックの扱い
  https://docs.astral.sh/uv/concepts/projects/sync/
- uv: Jupyterとの利用
  https://docs.astral.sh/uv/guides/integration/jupyter/
- uv: ビルド
  https://docs.astral.sh/uv/concepts/projects/build/
- uv: GitHub Actionsとの利用
  https://docs.astral.sh/uv/guides/integration/github/
- nbclient: Notebookの実行
  https://nbclient.readthedocs.io/en/latest/client.html
- nanobindのLICENSE（v3.1.0）
  https://github.com/wjakob/nanobind/blob/v3.1.0/LICENSE
- robin-mapのLICENSE
  https://github.com/Tessil/robin-map/blob/master/LICENSE

幾何アルゴリズムの背景: Andrew Adams, Jongmin Baek, and Myers Abraham Davis, “Fast High-Dimensional Filtering Using the Permutohedral Lattice”, 2010.
https://graphics.stanford.edu/papers/permutohedral/

今回の移行に直接使用したコードは、ユーザー提供アーカイブと前回成果物です。ファイル単位の由来と旧版との比較は `reference/provenance.json` と `reference/golden/manifest.json` に記録しています。参考論文の格子の向きや画像正規化まで同一にした厳密再現ではありません。
