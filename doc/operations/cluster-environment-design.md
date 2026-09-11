# クラスタ環境の調査・起動設計（2026-09-11、未実機検証）

> 更新: 本文は実機調査前の設計記録。kuriでの調査と共有runtime構築は完了した。
> 現在状態は [kuri04初期調査](kuri04-environment-survey-20260911.md)、
> [代表ノード調査](kuri-node-survey-20260911.md)、
> [共有runtime構築](kuri-shared-runtime-20260911.md)を参照する。

## 採用方針（ユーザー決定、2026-09-11）

DIALS と Fork KAMO は、ユーザーが管理する共有ディレクトリに固定した環境として配置する。
全対象計算ノードから同じ絶対パスで実行できる構成を第一選択とし、DIALS の module 管理を
必須にしない。下記の既存 module 優先評価案はこの決定で更新された。
サイト側で必須となる依存 module があれば、その初期化と version だけを明示的に記録する。

- robo04 のコピーをクラスタへ移植することは前提にしない。現地に適合する DIALS を導入する。
- runtime / Fork checkout の版を固定し、実行中の環境を更新しない。
- KAMO の生成ジョブが埋め込む Python 絶対パスと環境が計算ノードでも有効か確認する。
- 小さな Slurm ジョブで同一パス・ライブラリ・入力読み込み・出力書き込みを検証してから本処理へ進む。
- 共有領域と対象ノードの実情は未確認であり、この確認は省略しない。

次のローカル作業は robo04 の独立 runtime で小規模の実データ試験。

## 適用範囲と現在の判断

robo04 の runtime コピーは、同じホストで既存 DIALS と統合版 KAMO を分離する検証方法。
別 OS・CPU・module 管理クラスタにそのまま転送して動作するとは扱わない。
クラスタではツールとストレージが共有されている想定だが、まだ確認されていない。
module の実装、利用可能な DIALS、共有 mount、ジョブへの環境伝播は未調査。

まず既存の管理された DIALS module を評価する。使える場合はその環境を生かし、
Fork の登録だけをユーザー側で分離できる方法を調査する。module の管理対象へ勝手に
libtbx.configure を実行しない。分離が難しければ、計算ノードに適合する DIALS を
ユーザー書き込み可能な共有領域へ新規導入する。robo04 のコピーは必須条件にしない。
コンテナ等はサイトの利用可否が確認できた場合の代替であり、現段階で採用しない。

## 現在の KAMO 実装から確認できたこと

対象コード: c811f9f21a177bc97e9f21066d3585474aa880a1。

- yamtbx/util/batchjob.py の Job は copy_environ=True が既定。
  write_script は生成元プロセスの環境変数を export 行として書き出す。
- HDF5_PLUGIN_PATH は生成元で存在するディレクトリだけを残す。
  生成元で見えず計算ノードだけで見える plugin の経路はこの処理で失われ得る。
- auto_data_proc_gui.py の XDS / DIALS ジョブ、multi_merge.py と auto_multi_merge.py の
  merge ジョブは sys.executable の絶対パスを埋め込む。
- Slurm.submit は sbatch に partition、CPU数、任意のメモリ指定を渡す。
  この実装には module 初期化・module load の挿入や --export の明示指定がない。
- 共通スクリプト header は /bin/sh。module を使う shell 初期化は実装されていない。

したがって、計算ノードで後から module load するだけで使用 Python が置き換わるとは
考えない。元の Python 絶対パスが優先され、生成時の PATH / library path も再設定される。
環境フックを追加する場合は、既存 export より前か後か、Python パスの決定と併せて設計する。
現段階では科学的コード・Slurm 実装を変更していない。

## 目標とする実行の流れ

1. ホスト固有の起動設定で必要な shell/module 初期化を行う。
2. 検証対象の明示した DIALS module version またはユーザー管理 DIALS を有効化する。
3. 固定した Fork checkout に対応する libtbx 登録・dispatcher を有効化する。
4. Python、KAMO、resource、外部プログラムの参照先を検査し、記録する。
5. その環境で KAMO を起動し、Slurm ジョブを生成する。
6. 生成したスクリプトの Python パスと環境を確認し、計算ノードで小さな試験を実行する。

KAMO を起動するホストで計算ノード用 Python を実行できない構成なら、
計算ノードの allocation 内で KAMO を起動する方式を候補とする。
ただしジョブ内からの sbatch 可否、GUI の要否、長時間制御プロセスの設置規則を先に確認する。
ログインノードで長時間 KAMO を動かせると決めつけない。

## 現地で調べる内容

ログイン環境で、サイトが案内する shell から以下を採取する。
コマンドが存在するかを先に確認し、module の種類で利用できないものは読み替える。

```bash
hostname
uname -a
cat /etc/os-release
type module
module --version
module list
module avail
```

対象 module が分かったら module show の内容を調べ、必要な親 module / compiler、
PATH / PYTHONPATH / library path の変更、実際の DIALS 配置と version を記録する。
module 名だけでは version 固定を保証しないため、dials.version と実体も保存する。
module purge はサイト側必須 module を外す可能性があるため、調査前に定型手順にしない。

確認する配置・規則:

- login / compute 間で同じ絶対パスが見えるか。home が共有か、scratch が node-local か。
- runtime、Fork、入力・出力、作業ディレクトリ、HDF5 plugin の可視性と権限。
- 対象 partition ごとの OS、CPU architecture、実行互換性。
- module のバージョン固定方法、更新・廃止方針、必要なら旧版の保持方法。
- batch shell の module 初期化方法、環境 export に関するサイト設定。
- account、partition、CPU、メモリ、time limit、ジョブ数などの利用要件。

不明点はまずファイルと利用者向け案内で調べ、必要なサイト固有情報だけを管理者に確認する。

## 計算ノードでの最小合格条件

本処理を行わない小さな Slurm ジョブで、対象 partition / ノード種別ごとに確認する。
投入コマンド・module 初期化・resource 指定の具体形はサイト調査後に確定する。

- hostname、job ID、module list、dials.version、sys.executable を記録できる。
- yamtbx.__file__ と util.yamtbx_module_root() が指定 Fork を指す。
- 生成元と計算ノードで、対象 commit と runtime の参照先・version が一致する。
- 入力を読め、専用出力先と scratch に書ける。
- 代表画像1枚の読み込みが成功する（HDF5 plugin とライブラリの確認を含む）。
- KAMO が実際に生成したスクリプトでも同じ参照先を再現できる。
- ジョブの終了状態に加え、ログと生成物で成功を確認できる。

合格後に小規模処理へ進み、その後に複数ジョブ・複数ノードでの検証を行う。
「共有ディレクトリが見える」だけを実行互換性の合格条件にしない。

## バージョン記録

ホスト/ノード種別、module 初期化手順、正確な module 名と version、module show の出力、
DIALS version と Python 実体、Fork commit / dirty state、libtbx resource path、
XDS 等の依存 version、生成ジョブスクリプト、sbatch 引数、入力識別情報と結果を保存する。
ジョブスクリプトには環境変数が含まれるため、公開リポジトリへ保存する前に秘密情報を除く。
再現に必要な環境設定は残し、省いた内容の種類だけを記録する。

設計時点の状態: 設計・ソース調査のみで、クラスタのmodule調査・Slurm投入は未実施だった。
後続の実施結果は冒頭の更新先を参照する。
