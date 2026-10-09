# kuri04 OS・共有パス・Slurm 初期調査 — 2026-09-11

## 作業情報

| 項目 | 値 |
| --- | --- |
| 日時 | 2026-09-11 14:24 JST |
| login host | `kuri04.spring8.or.jp` |
| 目的 | OS、共有ディレクトリ、Slurm、計算ノードからのパス可視性だけを確認する |
| branch | `integration/upstream-20260911` |
| 作業開始時 HEAD | `93109fc9ef2a30a0c9e2caf7c38e1b4890f4331e` |
| upstream 統合コード commit | `c811f9f21a177bc97e9f21066d3585474aa880a1`（既存記録による） |
| 開始時 dirty state | clean |
| 終了時 dirty state | `doc/operations/README.md` を変更、本記録・検証スクリプト・検証ログを新規作成 |
| コード変更 | なし |

指定された運用文書を先に読んだ。データの探索・解析、既存解析ソフトの探索、
DIALS/KAMO の導入・起動は行っていない。

## login host の観測

- OS: Ubuntu 24.04.4 LTS (Noble Numbat)
- kernel: `7.0.0-28-generic`
- architecture: `x86_64`
- login host: `kuri04.spring8.or.jp`
- 実行ユーザー: `target` (`uid=10030`, `gid=10030`, supplementary group `blstaff`)

`/staff/Common/kuntaro/kamodev/kamo` は `/staff` 配下、`/user/target` は `/user`
配下にあり、login host ではいずれも CephFS として read-write mount されていた。
両者は同じ Ceph filesystem ID を示した。容量表示は調査時点で約 2.5 PiB 中 74% 使用。
この値は実機固有の瞬間値であり、導入要件にはしない。

## Slurm の観測

- Slurm client version: `24.11.2`
- cluster name: `kuri`
- controller: `kuri-core`
- scheduler: `sched/backfill`
- selection: `select/cons_tres`, `CR_CPU_MEMORY,CR_LLN`
- task isolation/placement: `task/cgroup,task/affinity`
- default partition: `kuri`
- additional partition: `debug` (`kuri-c13`)
- 調査時の `kuri` node state: 8 idle、1 mixed、2 down
- 両 partition の表示上の time limit: `infinite`

`scontrol show partition -o` では両 partition の AllowGroups / AllowAccounts が `ALL`、
memory default/max は `UNLIMITED` と表示された。ただしサイト運用上の account、推奨 resource、
ジョブ数等の規則を確認済みという意味ではない。

## 計算ノードからのパス可視性

環境確認だけを行う 1 CPU・2分上限のジョブを `debug` partition に投入した。

- job ID: `550708`
- node: `kuri-c13.spring8.or.jp`
- state / exit code / elapsed: `COMPLETED` / `0:0` / `00:00:01`
- compute OS: Ubuntu 24.04.4 LTS、kernel `7.0.0-28-generic`、`x86_64`
- submit cwd: `/staff/Common/kuntaro/kamodev/kamo`
- `/staff/Common/kuntaro/kamodev/kamo`: 同じ絶対パスで可視、CephFS read-write mount
- `/user/target`: 同じ絶対パスで可視、CephFS read-write mount
- repository の evidence directory に一時ファイルを作成でき、削除にも成功

少なくとも `debug` partition の `kuri-c13` では、login host と同じ絶対パスで対象の
`/staff` および `/user` が見え、作業 repository への書き込みができることを確認した。
他の `kuri` node、node-local scratch、将来配置する runtime、入力・出力領域は未確認。

## 実行コマンドと終了状態

以下はいずれも終了コード 0。`find` や再帰的なデータ列挙は使用していない。

```bash
hostname
uname -a
cat /etc/os-release
git status --short --branch
git log -1 --format='%H%n%ad%n%s' --date=iso-strict
git remote -v
pwd -P
id
df -T /staff/Common/kuntaro/kamodev/kamo /user/target /tmp
findmnt -T /staff/Common/kuntaro/kamodev/kamo
findmnt -T /user/target
command -v sbatch squeue sinfo scontrol
sbatch --version
sinfo -o '%P|%a|%l|%D|%t|%N'
scontrol show partition -o
scontrol show config
sbatch --parsable doc/operations/evidence/20260911-kuri04-path-visibility.sbatch
squeue -j 550708 -o '%i|%T|%P|%N|%R'
sacct -j 550708 --format=JobID,JobName,Partition,State,ExitCode,Elapsed,NodeList -n -P
sha256sum doc/operations/evidence/20260911-kuri04-path-visibility.sbatch \
  doc/operations/evidence/20260911-kuri04-path-visibility-550708.txt
```

保存 evidence:

- `evidence/20260911-kuri04-path-visibility.sbatch`
  - SHA-256: `6fa8afdd9a8c6a5e86d643e062280dc4739087ea5a1be2501c99c7db7249168c`
- `evidence/20260911-kuri04-path-visibility-550708.txt`
  - SHA-256: `95f723214a4dbe18910f6a1193d800a0392b955a889c463c80a884b442f0a1a9`

Ceph mount options の secret は `findmnt` により `<hidden>` と表示され、秘密情報は保存されていない。

## 判断と未完了事項

ユーザー管理 runtime / checkout の固定配置候補として、現在の
`/staff/Common/kuntaro/kamodev/` 配下は `kuri-c13` から参照・書き込み可能だった。
ただし配置場所を確定せず、runtime の導入も行わない。

次はユーザーの指示を受けて対象 node 種別を決め、同じ非解析 probe で `kuri` partition の
代表 node からの可視性を確認する。その後に DIALS 導入場所と version を記録し、固定 KAMO
checkout を準備する。実データは由来・用途・許可パスを合意するまで探索も解析もしない。
