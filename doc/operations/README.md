# 運用・バージョン記録

作業ごとの実務記録と、別環境で再開するための入口。

## 現在の版

| 項目 | 値 |
| --- | --- |
| 統合コード commit | c811f9f21a177bc97e9f21066d3585474aa880a1 |
| 作業 branch | integration/upstream-20260911 |
| 現在の実体・記録 HEAD | `79b1f55`（本同期修正commit前。再開時は `git log -1` を正とする） |
| 統合前 Fork | 662864d474c87d67e351c3599e44a57debc86239 |
| 取り込み済み本家 | b4b12bd979886e50a537e28ab78ad13050776205 |
| 元 Fork の退避 branch | archive/fork-before-upstream-20260911 |
| 検証ホスト | robo04 / Ubuntu 22.04.5、kuri04・kuri05・kuri-c09 / Ubuntu 24.04.4、x86_64 |
| 検証環境 | DIALS 3.23.0-g7aff524e7-release / Python 3.11.11（robo04私有版、kuri共有版） |
| 段階 | 統合済み、kuri共有runtime・XDS 2026/06基本起動確認済み、H5ToXds不合格、実データ baseline未確立 |
| 公開状態 | `79b1f55` まで `origin/integration/upstream-20260911` へpush確認済み（2026-09-11） |

統合前後の commit は Git merge の両親としても保持されている。
将来この表を更新しても、その時点の値は Git 履歴に残る。

## 記録一覧

- [robo04 初期調査](robo04-survey-20260911.md)（統合前の観測）
- [Fork と本家の比較](fork-upstream-survey-20260911.md)（統合前の調査）
- [統合手順・検証結果](../upstream-integration-20260911.md)
- [実務記録 2026-09-11](worklog-20260911.md)
- [別環境での再開手順](startup.md)
- [独立 runtime 構築・検証](runtime-20260911.md)
- [クラスタ・module 環境の調査と起動設計](cluster-environment-design.md)（設計時点の記録。実機結果は後続記録）
- [kuri04 接続引き継ぎ情報](kuri04-connection-20260911.md)（接続直後の記録。調査前状態）
- [kuri04 OS・共有パス・Slurm 初期調査](kuri04-environment-survey-20260911.md)
- [kuri partition 代表ノード調査](kuri-node-survey-20260911.md)
- [kuri Ubuntu 共有 DIALS/KAMO runtime 構築](kuri-shared-runtime-20260911.md)
- [由来未確認データの試験・追加処理停止記録](smoke100-20260911.md)（baseline 不採用）
- [次回再開用 handoff](handoff-20260911.md)
- [GitHub push 記録](push-20260911.md)
- [installation check の保存ログ](evidence/20260911-installation.txt)

各記録には対象コード commit を記載し、記録そのものの版は Git commit で管理する。
