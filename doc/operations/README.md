# 運用・バージョン記録

作業ごとの実務記録と、別環境で再開するための入口。

## 現在の版

| 項目 | 値 |
| --- | --- |
| 統合コード commit | c811f9f21a177bc97e9f21066d3585474aa880a1 |
| 作業 branch | integration/upstream-20260911 |
| 統合前 Fork | 662864d474c87d67e351c3599e44a57debc86239 |
| 取り込み済み本家 | b4b12bd979886e50a537e28ab78ad13050776205 |
| 元 Fork の退避 branch | archive/fork-before-upstream-20260911 |
| 検証ホスト | robo04 / Ubuntu 22.04.5 / x86_64 |
| 検証環境 | DIALS 3.23.0-g7aff524e7-release / Python 3.11.11 |
| 段階 | 統合済み、独立 runtime 登録・起動確認済み、実データ baseline 未確立 |
| 公開状態 | 2026-09-11 の本記録作成時点でローカルのみ。push 未実施 |

統合前後の commit は Git merge の両親としても保持されている。
将来この表を更新しても、その時点の値は Git 履歴に残る。

## 記録一覧

- [robo04 初期調査](robo04-survey-20260911.md)（統合前の観測）
- [Fork と本家の比較](fork-upstream-survey-20260911.md)（統合前の調査）
- [統合手順・検証結果](../upstream-integration-20260911.md)
- [実務記録 2026-09-11](worklog-20260911.md)
- [別環境での再開手順](startup.md)
- [独立 runtime 構築・検証](runtime-20260911.md)
- [installation check の保存ログ](evidence/20260911-installation.txt)

各記録には対象コード commit を記載し、記録そのものの版は Git commit で管理する。
