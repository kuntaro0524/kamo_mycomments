# kuri04 接続引き継ぎ情報 — 2026-09-11

> 更新: 本文は接続確認直後の調査前記録。列挙した未確認事項の後続結果は
> [kuri04初期調査](kuri04-environment-survey-20260911.md)、
> [代表ノード調査](kuri-node-survey-20260911.md)、
> [共有runtime構築](kuri-shared-runtime-20260911.md)を参照する。

## 接続

- 接続元: robo04
- 接続先: `kuri04.spring8.or.jp`
- ユーザー: `target`
- 結果: hostname 取得まで成功
- 接続確認に使った秘密鍵: robo04 の `/home/kuntaro/.ssh/id_ed25519`
- host key: 事前に fingerprint を確認し、`known_hosts` に登録済み

```bash
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes \
  target@kuri04.spring8.or.jp hostname
```

接続時に target の tcsh が `TERM: 定義されていない変数です.` と出すことがある。
これはシェル初期化の警告で、接続失敗ではない。

## まだ確認していないこと

- target の書き込み可能な共有ディレクトリ
- login / compute node 間のパス可視性
- OS / architecture、module の有無と内容
- Slurm の partition、sbatch / squeue の実体と制限
- DIALS / XDS / CCP4 等の既存配置
- KAMO や diffraction data の配置

上記は次回、対象範囲を限定して調査する。データの再帰探索・解析は行わない。

## 導入方針

ユーザー管理の共有ディレクトリへ固定した DIALS と、GitHub Fork の
`integration/upstream-20260911` から取得した KAMO を置く。Slurm 計算ノードから
同じ絶対パスで実行できるかを最小ジョブで確認する。module 管理を必須とはしない。
インストールやジョブ投入はこの引き継ぎ情報の作成時点では未実施。
