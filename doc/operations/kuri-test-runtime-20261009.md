# kuri KAMO 試験版 runtime 構築 — 2026-10-09

## 作業情報

| 項目 | 値 |
| --- | --- |
| 日時 | 2026-10-09 16:05–16:30 JST |
| 構築 host | `kuri04.spring8.or.jp` |
| 目的 | 共通版（`runtimes/current`）を変えずに、KAMO の修正を試験できる runtime を用意する |
| 記録 repository branch | `feature/KAMO-002-rescut-fit-fallback` |
| 対象 KAMO code commit | `3946eb03d8d45b4052d61502ec082098f93aef2c` |
| 解析データ | 使用していない |
| 管理 | zoo-hub work-item `KAMO-002`。利用者（kuntaro）が作成を了承 |

## 構築した配置

```text
/staff/Common/kuntaro/kamodev/
├── activate-kamo-test.sh                 試験版の launcher（新規）
├── checkouts/kamo-test/                  独立 clone（新規）。試験したい版へ checkout し直して使う
└── runtimes/
    ├── dials-3.23.0-kamo-test/           /opt/dials/dials-v3-23-0 の cp -a コピー（新規、2.5 GB）
    ├── test -> dials-3.23.0-kamo-test    （新規）
    └── current -> dials-3.23.0-kamo-c811f9f…   変更していない
```

手順は `kuri-shared-runtime-20260911.md` と同じ。`cp -a` の後、`/tmp` を current directory にして
`configure-local-runtime.py --runtime runtimes/dials-3.23.0-kamo-test --checkout checkouts/kamo-test`
を実行し、`Done.` で終了した。`activate-kamo-test.sh` は `activate-kamo.sh` を写し、source する先を
`runtimes/test/activate.sh` に替えたもの（`module load xds/20260610` は同じ）。

共通版と違い、`checkouts/kamo-test` は固定しない。試験する版へ `git -C checkouts/kamo-test checkout …` /
`pull` で切り替える。実行中の job があるときは切り替えない。試験結果には必ず
`git -C checkouts/kamo-test rev-parse HEAD` を記録する。新しい command-line script を足した場合は
`libtbx.configure yamtbx` のやり直しが要る。

## 起動方法

```bash
source /staff/Common/kuntaro/kamodev/activate-kamo-test.sh
```

Bash 専用。`/bin/sh` から source しない。activation 前に `set -u` しない。source checkout 直下を
current directory にして起動しない（`kuri-shared-runtime-20260911.md` と同じ注意）。

## 検証結果

Slurm job `551222`（kuri-c08、1 CPU、`COMPLETED`、1分25秒）。probe は
`~/Staff/kuntaro/kamo_test_runtime_probe/probe.sh`、log は同 directory の `probe-551222.log`。

- `dials.version`: DIALS 3.23.0-g7aff524e7-release / Python 3.11.11、試験版 runtime 内
- `kamo`、`kamo.auto_multi_merge`、`python`: 試験版 runtime の `build/bin`
- `kamo --help`: 終了コード 0
- `sys.executable`: 試験版 runtime の `conda_base/bin/python`
- `yamtbx.__file__`: 試験版 runtime の `modules/yamtbx`（`checkouts/kamo-test` への symlink）
- checkout: `3946eb0`、clean
- `rescut.fit_fallback`（既定 `none`）と `rescut.skip_no_signal`（既定 `False`）が phil parameter にある
- `xscale_par`、`xds_par`: `/opt/xtal/xds/XDS-gfortran_Linux_x86_64_20260610/`、`BUILT=20260610`
- `yamtbx/dataproc/auto/tests`: 13 passed

## 未実施

- KAMO installation check、実データでの処理（この記録は起動確認まで）
- AMD node、kuri05 系での確認（今回は kuri-c08 の 1 node だけ）
- 試験版を使った auto_multi_merge の実行
