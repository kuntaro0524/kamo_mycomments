# kuri Ubuntu 共有 DIALS/KAMO runtime 構築 — 2026-09-11

## 作業情報

| 項目 | 値 |
| --- | --- |
| 日時 | 2026-09-11 14:50–15:03 JST |
| 構築 host | `kuri04.spring8.or.jp` |
| 目的 | Ubuntu login/compute nodeから同一絶対パスで起動する共有DIALS/KAMO環境を作る |
| 記録 repository branch | `integration/upstream-20260911` |
| 記録開始時 HEAD | `d98677cd6dbfa39df802d9688377910fb406bcde` |
| 対象 KAMO code commit | `c811f9f21a177bc97e9f21066d3585474aa880a1` |
| 開始時 dirty state | clean |
| 解析データ | 使用していない |

## 構築した配置

```text
/staff/Common/kuntaro/kamodev/
├── checkouts/
│   └── kamo-c811f9f21a177bc97e9f21066d3585474aa880a1/
└── runtimes/
    ├── dials-3.23.0-kamo-c811f9f21a177bc97e9f21066d3585474aa880a1/
    └── current -> dials-3.23.0-kamo-c811f9f21a177bc97e9f21066d3585474aa880a1
```

KAMO checkout は既存repositoryから `--no-hardlinks --no-checkout` で独立cloneし、
detached HEADで対象commitへ固定した。作業treeはclean。runtimeは
`/opt/dials/dials-v3-23-0` の私有コピーを作り、既存
`doc/operations/configure-local-runtime.py` でコピー内だけを再設定した。

| component | 構築前 | 構築後 |
| --- | --- | --- |
| DIALS | `/opt/dials/dials-v3-23-0` | 共有版固定runtime、DIALS 3.23.0-g7aff524e7-release |
| Python | source runtimeの3.11.11 | 共有runtimeのPython 3.11.11 |
| KAMO | source runtimeに含まれる版 | 固定checkout `c811f9f…` |
| runtime size | source観測 2.7 GB | 構築後観測 2.5 GB |

`libtbx.configure yamtbx` は終了コード0。途中にDIALS refresh由来の
`fatal: not a git repository` が2回表示されたが、configure全体は `Done.` で終了した。
この表示だけを成功根拠にせず、後述の別起動試験で合否を判定した。

## 起動方法

Bashで次を実行する。

```bash
source /staff/Common/kuntaro/kamodev/activate-kamo.sh
dials.version
kamo --help
```

`/staff/Common/kuntaro/kamodev/activate-kamo.sh` は、module機能を初期化し、
`xds/20260610` を明示的にロードしてから `runtimes/current/activate.sh` をsourceする
kuri用ランチャー。2026-09-11 15:14時点のSHA-256は
`72dbd08902de4b59c8f5675745bf14c7f97ff455038a844915e4b456ea0ba468`。

`activate.sh` はBash専用。`/bin/sh` からsourceしない。また、生成されたDIALS
`setpaths.sh` は `set -u` が先に有効なshellでは失敗するため、activation後に
`set -u` を有効にする。再現記録では `current` だけでなく
`readlink -f /staff/Common/kuntaro/kamodev/runtimes/current` の結果も保存する。

repository rootからPythonを起動するとカレントディレクトリの開発版 `yamtbx` が
importされ得る。検証・本処理の起動場所にはsource checkout直下を使用せず、実行時に
`yamtbx.__file__` とresource pathを確認する。

## 検証結果

### login host

`/tmp` から実行し、次を確認した。

- `dials.version`: DIALS 3.23.0-g7aff524e7-release / Python 3.11.11
- `kamo --help`: 成功
- `sys.executable`: 共有runtimeの `conda_base/bin/python`
- `yamtbx.__file__`: 固定checkout
- `util.yamtbx_module_root()`: 固定checkout
- checkout: commit一致、clean

最初に記録repository直下から試した際は `yamtbx.__file__` が開発checkoutを指した。
`/tmp` からの再試験で固定checkoutを指すことを確認した。

### Intel compute node

正式開放が未確認のAMD nodeは対象外とし、Intel 2系統でSlurm probeを実行した。

| job | node | result | elapsed | 備考 |
| ---: | --- | --- | ---: | --- |
| 550715 | kuri05 | FAILED 127:0 | 0 s | `/bin/sh` からBash専用activationをsource |
| 550716 | kuri-c09 | FAILED 127:0 | 0 s | 同上 |
| 550717 | kuri05 | FAILED 1:0 | 0 s | activation前の `set -u` |
| 550718 | kuri-c09 | FAILED 1:0 | 0 s | 同上 |
| 550719 | kuri05 | COMPLETED 0:0 | 18 s | 修正後、全基本check成功 |
| 550720 | kuri-c09 | COMPLETED 0:0 | 17 s | 修正後、全基本check成功 |

成功した2ジョブではDIALS/KAMO/Python dispatcher、DIALS version、`kamo --help`、
`yamtbx.__file__`、resource path、checkout commit/clean stateがすべて指定共有版と一致した。

## Installation check

login hostの `/tmp` で実データなしのKAMO installation checkを実行し、終了コード1。

- OK: runtime location、R、NumPy 1.26.4、SciPy 1.15.0、networkx 3.4.2、
  Matplotlib 3.10.0、wxPython 4.2.2、XDSSTAT、CCP4、DIALS、ADXV
- NG: XDS（license expired）
- NG: H5ToXds（存在するが動作しない）
- Eiger geometry recognition: warningを表示したがcheck上はOK

参照実体は `xds_par=/opt/xtal/xds/XDS-gfortran_Linux_x86_64_20250714/xds_par`、
`H5ToXds=/opt/xtal/xds/extra_bin/H5ToXds`。基本起動は合格したが、XDS/HDF5を使う
実処理が可能とはまだ扱わない。ユーザー指定データによる試験も未実施。

### XDS期限切れの切り分け（15:10 JST）

期限切れは共有DIALS runtimeに同梱されたXDSではなく、shellでロード済みだった
`xds/20250714` module由来だった。modulefileは
`/opt/xtal/xds/XDS-gfortran_Linux_x86_64_20250714` をPATHへ追加する。
KAMOのcheckはPATH上の `xds_par` を引数なしで実行し、stdoutの
`license expired` を判定している。

`module load xds/20260610` を明示してから共有runtimeをactivateすると、
`xds_par` は
`/opt/xtal/xds/XDS-gfortran_Linux_x86_64_20260610/xds_par` を指し、
XDS単独checkは終了コード0で `OK` になった。共有runtimeのactivationはXDSを
選択・変更しないため、利用時に有効なXDS moduleを別途固定する必要がある。
この時点ではactivationへのmodule操作の埋め込みは行っていない。

### 2025/07版 XDS・XSCALE の継続利用要望と実測

ユーザーはXDS/XSCALEについて `xds/20250714` の利用を希望。入力なしでmodule内の
`xds_par` と `xscale_par` を個別に起動したところ、両方とも
`Sorry, license expired on 1-Aug-2026` を表示し、処理を開始しなかった。
両コマンドのprocess exit codeは0だったため、終了コードだけでは利用可能と判定できない。

期限回避は行っていない。2025/07版を厳密に固定するには、サイト管理者またはXDS配布元に
正規に利用可能な同版binaryの有無・利用条件を確認する必要がある。それまでは
`xds/20250714` を本処理可能とは扱わず、2026/06版で代替した結果を2025/07版の
再現結果とも扱わない。

### 当面の共有ランチャーと将来のfaketime構成

ユーザー判断により、当面は実行可能な `xds/20260610` を使用する。共有ランチャーを作成し、
login host、`kuri05`、`kuri-c09` でXDS単独check、DIALS version、KAMO helpを確認した。

| job | node | state / exit | elapsed |
| ---: | --- | --- | ---: |
| 550721 | kuri05 | COMPLETED / 0:0 | 31 s |
| 550722 | kuri-c09 | COMPLETED / 0:0 | 31 s |

両ノードで `xds_par` は2026/06版、DIALS/KAMOは共有固定runtimeを指した。
probeは `evidence/20260911-kuri-shared-launcher.sbatch`、ログは同名のnode/job別ファイル。

ユーザー申告では、作者から旧binaryの利用にfaketimeを用いる案内を受けている。
将来、2025/07版を使うfaketime構成を当面の2026/06版とは別に導入する意向。
今回はfaketimeの導入・時刻指定・wrapper作成を行っていない。導入時は作者の案内内容、
対象binary、固定日時、実体checksum、wrapper、ジョブへ伝播するPATHを記録し、
2026/06版の結果と混同しない。

### 計算ノード上のH5ToXds PATH切り分け

ユーザーの質問を受け、共有ランチャーをsourceした `kuri05` と `kuri-c09` で
`command -v H5ToXds` と実行権限を確認した。両ノードとも終了コード0で、
`/opt/xtal/xds/extra_bin/H5ToXds` を指した。したがってinstallation check不合格は
計算ノードでPATHが通っていないことが原因ではない。

`H5ToXds` は289 byteのBash wrapperで、実体として
`eiger2cbf_applyflatfield_maskbad` を呼び、stderrを `/dev/null` へ捨てる。
この下位コマンドも `kuri04`、`kuri05`、`kuri-c09` の全てで
`/opt/xtal/xds/extra_bin/eiger2cbf_applyflatfield_maskbad` としてPATH上に存在した。
未解決点は、KAMOが生成する合成HDF5をこのwrapperがCBFへ変換できない理由である。
stderr抑止を外した隔離試験はまだ実施していない。

## Evidence

- `evidence/20260911-kuri-shared-runtime.sbatch`
- failure logs: jobs 550715–550718
- successful logs: jobs 550719–550720

最終probe SHA-256:
`21bb75990eee3b5b9892439871cfd55ba4c11810ee105d89bb0d569add424b56`。
成功ログは kuri05 が
`4cb68ab6ed172e4139e37c6740c244c436c83d8371ad74918f09b2cf3b7926d1`、
kuri-c09 が
`d5fc6525b7476dc18fa7d54c9c5a6be5aa2e0ed447ae0b6b080bab2880923ffd`。
runtime `activate.sh` は
`40351f812ce92aba965731fb550bed45c2c0bfd23688fa2133618558d4bdae96`。

## 未完了事項

- 有効なXDS moduleを起動手順へ固定（`xds/20260610` の単独checkは合格）
- 希望する `xds/20250714` の正規に利用可能なbinary・運用条件を確認
- 作者の案内内容を確認したうえで、2025/07版用faketime環境を別構成として検討
- H5ToXds不合格の解消
- H5ToXds wrapperのstderrを保存する合成データ試験で変換失敗原因を特定
- サイト側で正式利用対象と確認されたノード範囲での追加確認
- KAMO生成ジョブが同じ絶対Python/runtimeを再現することの確認
- ユーザーが由来・用途・入力パスを指定した後の実データbaseline

runtimeと固定checkoutは実行中に更新しない。次版は別ディレクトリへ構築し、検証後に
`current` symlinkを切り替える。
