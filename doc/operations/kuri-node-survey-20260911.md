# kuri partition 代表ノード調査 — 2026-09-11

## 作業情報

| 項目 | 値 |
| --- | --- |
| 日時 | 2026-09-11 14:32–14:35 JST |
| submit host | `kuri04.spring8.or.jp` |
| 目的 | クラスタのノード構成差、共有パス可視性、ジョブ用一時領域を非解析 probe で確認する |
| branch | `integration/upstream-20260911` |
| 対象 HEAD | `aa90ba536cc741ee563cf73d322aeef23ca9e52d` |
| 開始時 dirty state | clean |
| コード変更 | なし |

データ探索・解析、DIALS/KAMO の導入・起動は行っていない。Slurm 登録情報を読み、
稼働中の3種類の代表ノードへ各1 CPU、2分上限の環境確認ジョブだけを投入した。

## Slurm 登録ノードの概況

調査時点の `kuri` partition は11ノード、1504 CPU。feature / GRES は未設定だった。

| 系統 | Slurm CPU | memory | socket/core/thread | 調査時状態 | 代表 probe |
| --- | ---: | ---: | --- | --- | --- |
| `kuri05-07`, `kuri-c08` | 104 | 192000 MB | 2 × 26 × 2 | idle | `kuri05` |
| `kuri03`, `kuri-c02`, `kuri-c09` | 192 | 約380–385 GB | 4 × 24 × 2 | 前2台 down、c09 idle | `kuri-c09` |
| `kuri-c10-13` | 128 | 250000 MB | 1 × 64 × 2 | c10 mixed、他 idle | `kuri-c11` |

`kuri03` と `kuri-c02` は `DOWN+NOT_RESPONDING` だったため投入対象にしなかった。
`kuri04` は Slurm node としては shutdown/drain 表示だが、今回の login/submit host である。
これらは調査時点の状態であり、恒久的な利用可否を表さない。

各 probe は resource 指定を省略した結果、Slurm の job record 上では 1 CPU と 4000 MB が
要求・割当された。partition 表示の `DefMemPerNode=UNLIMITED` だけから実際の既定 memory
割当を判断してはいけない。

## 代表ノードの実測

| node | CPU | ISA上の主な差 | OS / kernel | `/tmp` 容量（観測時） |
| --- | --- | --- | --- | ---: |
| `kuri05` | Intel Xeon Gold 6230R、2 socket、52 core/104 thread | AVX2、AVX-512、VNNI | Ubuntu 24.04.4 / 7.0.0-28 | 約744 GB available |
| `kuri-c09` | Intel Xeon Platinum 8168、4 socket、96 core/192 thread | AVX2、AVX-512 | Ubuntu 24.04.4 / 7.0.0-28 | 約172 GB available |
| `kuri-c11` | AMD EPYC 7713P、1 socket、64 core/128 thread | AVX2、AVX-512なし | Ubuntu 24.04.4 / 7.0.0-28 | 約439 GB available |

3ノードとも `x86_64` だが、Intel/AMD と命令セットに差がある。したがって共有 DIALS
runtime は AMD node でも起動確認し、AVX-512 必須でないことを実機で確認する必要がある。

## パスと一時領域

3代表ノードすべてで次を確認した。

- submit cwd `/staff/Common/kuntaro/kamodev/kamo` が同じ絶対パスで見える。
- `/staff` と `/user` は login host と同じ Ceph filesystem ID の read-write mount。
- repository 配下に一時ファイルを作成・削除できる。
- `TMPDIR=/tmp`。`/tmp` は各ジョブ専用の `/tmp/slurm-<jobid>/tmp` を参照する
  node-local Btrfs subvolumeで、作成・削除できる。
- `/tmp` の容量はノード間で異なるため、必要容量を確認せず一律に使用できるとは扱わない。

最初の3ジョブ終了直後、`sacct` は completed を返した一方で、submit host の glob では
ログが一時的に列挙されなかった。その後 `rg --files` と個別確認では全ログが見えた。
CephFS の可視化遅延と断定はしないが、ジョブ完了直後のログ回収には短い遅延があり得る観測として残す。

## Job と終了状態

| job | node | 内容 | state | exit | elapsed |
| ---: | --- | --- | --- | --- | --- |
| 550709 | kuri05 | OS、共有 path、`/tmp` | COMPLETED | 0:0 | 1 s |
| 550710 | kuri-c09 | OS、共有 path、`/tmp` | COMPLETED | 0:0 | 0 s |
| 550711 | kuri-c11 | OS、共有 path、`/tmp` | COMPLETED | 0:0 | 0 s |
| 550712 | kuri05 | 上記 + `lscpu` | COMPLETED | 0:0 | 0 s |
| 550713 | kuri-c09 | 上記 + `lscpu` | COMPLETED | 0:0 | 0 s |
| 550714 | kuri-c11 | 上記 + `lscpu` | COMPLETED | 0:0 | 0 s |

投入形:

```bash
sbatch --parsable --partition=kuri --nodelist=<representative-node> \
  doc/operations/evidence/20260911-kuri-node-survey.sbatch
```

状態確認には `sacct` と `scontrol show job -o` を使用した。ノード構成は
`sinfo -N` と `scontrol show nodes -o` から採取した。全コマンドは終了コード0。

## Evidence

- probe: `evidence/20260911-kuri-node-survey.sbatch`
- 初回ログ: job 550709–550711
- CPU情報追加ログ: job 550712–550714

各ログには OS、CPU、mount source/options、容量の実機観測値が含まれる。mount secret は
`findmnt` により `<hidden>` と表示され、秘密情報そのものは保存されていない。
正確な checksum は保存直前の `sha256sum` 出力で確認し、commit 後は Git object でも固定する。

## 判断

`/staff/Common/kuntaro/kamodev/` は、稼働中の3ノード系統すべてから同一絶対パスで
read-write 利用できた。共有 DIALS/KAMO runtime の固定配置先として現実的である。

一方、runtime は最も命令セットの狭い AMD EPYC 系でも検証する。処理の一時作業領域は
共有 CephFS と job-local `/tmp` を用途別に設計し、`/tmp` から必要成果物をジョブ終了前に
共有領域へ回収する。停止ノードの回復後の確認、DIALS/Python の実行互換性、HDF5 plugin、
KAMO dispatcher の絶対パス再現は未実施であり、次段階で確認する。

