# 実行記録の索引

`verification.json` は現在の一括検証の実コマンド、開始時刻、終了コード、所要時間です。`logs/pytest.txt` と `pytest.xml` が最終のPython検証結果です。`logs/pytest-offline-native.txt` は途中時点の旧い118件の記録です。

`native-variants.json` はGNUのASan/UBSan付きビルドとClang Releaseの確認です。`notebooks/execution.json` と同じ場所の3冊のNotebookは、C ABIの検証専用接続を使った実行済み出力です。通常のnanobind経由で実行できたという記録ではありません。

`environment.json` は実行に利用した既存環境のソフトウェア版です。`uv.lock` の代替ではありません。nanobindなど取得できなかったものはnullです。`logs/uv-sync-attempt.txt` は実際の取得失敗ログです。

`relocation.json` は配布候補を別の空白入りパスへ展開して再ビルド・テストした記録です。そこで記録する候補のハッシュは、後からこの記録を追加する最終アーカイブのハッシュとは異なります。最終ハッシュは圧縮ファイルと一緒に渡す `.sha256` にあります。

`coverage.xml` はPython実行文のカバレッジです。C++・nanobind・分岐の網羅率を示しません。`results/manifest.json` は一つ上の結果ディレクトリにあり、22条件の数値結果と接続方式を記録しています。
