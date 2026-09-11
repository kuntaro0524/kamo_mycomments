# 別環境での再開手順

これは統合版の独立検証環境を再構築する手順。robo04 で構築・起動確認済み。
実データ baseline は未確立のため、本番検証済みの環境とは扱わない。

コピー元を利用できない環境や module 管理のクラスタには、このコピー手順をそのまま
適用しない。[クラスタ環境の調査・起動設計](cluster-environment-design.md)を先に参照する。

## ソース取得と版確認

integration branch はGitHubのForkへpush済み。2026-09-11の同期修正前に公開確認した
HEADは `79b1f55ffd8943c6dff1b9e9ba4f7ce209781bb5`。この文書を含む後続commitで進むため、
取得後の `git log -1` とremote tracking branchの一致を正とする。

```bash
git clone https://github.com/kuntaro0524/kamo_mycomments.git kamo
cd kamo
git fetch origin
git switch integration/upstream-20260911 2>/dev/null || \
  git switch --track origin/integration/upstream-20260911
git pull --ff-only origin integration/upstream-20260911
git remote get-url upstream 2>/dev/null || \
  git remote add upstream https://github.com/keitaroyam/yamtbx.git
git status --short --branch
git rev-parse HEAD
git merge-base --is-ancestor c811f9f21a177bc97e9f21066d3585474aa880a1 HEAD
```

HEAD は追加の文書 commit で進む場合がある。コードの厳密な再現対象は上記統合 commit。
既存upstreamのURLが期待値と異なる場合は、自動変更せず確認する。

ホスト固有の指示ファイルは、そのホストに存在する場合だけ読む。kuri04では
`/user/target/CLAUDE.md` を確認したが、robo04には `~/CLAUDE.md` が存在しないとの
報告があるため、robo04再開の必須ファイルにしない。repository内の `AGENTS.md` と
`doc/operations/` を共通の入口にする。

## 環境確認

対象ホストで OS、architecture、空き容量と既存 DIALS の配置を調べる。
robo04 では DIALS 3.23.0 / Python 3.11.11 を使用した。他 version は別途検証する。
見つけた DIALS の dials_env.sh を明示的に source した後、以下を保存する。

```bash
hostname
uname -a
cat /etc/os-release
dials.version
command -v kamo
command -v xds_par
command -v xdsstat
command -v Rscript
command -v adxv
```

robo04 の XDS は faketime wrapper 経由だった。別環境でその設定を自動的に再現せず、
実体 version と利用可否を調査する。ホスト固有パスは初期調査記録を参照。

## 独立した DIALS / KAMO 環境の作成

コピー元として利用可能な DIALS binary installation を用意する。
robo04 では 3.23.0 の modules / build / conda_base を含む約3.5 GBをコピーした。
以下の変数は実環境に合わせる。出力先は未使用のディレクトリとする。

```bash
KAMO_DIALS_SOURCE="<existing-DIALS-installation>"
KAMO_RUNTIME="<new-private-runtime-directory>"
KAMO_CHECKOUT="<absolute-path-to-this-checkout>"
test ! -e "$KAMO_RUNTIME" || exit 1
cp -a "$KAMO_DIALS_SOURCE" "$KAMO_RUNTIME"
python3 "$KAMO_CHECKOUT/doc/operations/configure-local-runtime.py" \
  --runtime "$KAMO_RUNTIME" --checkout "$KAMO_CHECKOUT"
source "$KAMO_RUNTIME/activate.sh"
command -v kamo
dials.version
kamo --help
dials.python -B - <<'PY'
import os, sys, yamtbx
from yamtbx import util
print('Python:', sys.executable)
print('KAMO:', os.path.realpath(yamtbx.__file__))
print('Resources:', os.path.realpath(util.yamtbx_module_root()))
PY
```

configure helper には必ず私有コピーを指定する。既存環境を上書きしない。
コピー内の元 yamtbx は original-yamtbx に退避し、modules/yamtbx を対象 checkout にリンクする。
libtbx.configure はコピー内の Python / libtbx 環境で dispatcher を再生成する。
DIALS と xia2 の editable 登録もコピー内で更新されるが、C++ の再ビルドは行わない。
元環境の絶対パスが残り得る dispatcher include の DIALS 設定も更新する。

activate.sh / dials_env.sh はこの環境向けの Bash 用ファイル。
csh 用の起動ファイルは本手順では更新・検証していない。
checkout は開発用リンクなので branch 切替やソース変更が直ちに反映される。
解析前に commit と dirty state を記録し、固定版での解析には専用 checkout を用いる。
このコピー手順の検証範囲は上記 DIALS binary layout に限る。

robo04 の構築記録: [独立 runtime](runtime-20260911.md)。

## 旧来の import のみの基本チェック（参考）

リポジトリのルートで実行する。これにより Python import をこの checkout に向ける。
既存 libtbx の resource 登録や dispatcher を切り替える操作ではない。

```bash
dials.python -B - <<'PY'
import os, sys
sys.path.insert(0, os.getcwd())
import yamtbx
print('Loaded:', yamtbx.__file__)
from yamtbx.command_line import kamo_test_installation
sys.exit(0 if kamo_test_installation.run() else 1)
PY
```

終了コードと全出力を記録する。robo04 の結果は R / XDSSTAT / ADXV の3項目不合格。
resource-location check は旧インストールを参照したため、それだけで新 checkout の
インストール成功と判断しない。

## 次に行う作業

1. ユーザーが試料・測定由来・用途を確認して明示したデータだけを候補にする。
2. 合意後、入力 checksum と全パラメータ、commit、runtime、出力先を先に保存する。
3. 小規模処理、実データ処理、同条件再実行を行い、科学的 baseline を確立する。

2026-09-11、ユーザーの判断により R / XDSSTAT / ADXV の不合格解消を前提とせず進める。
これは各項目の合格を意味しない。実処理が必要な依存で失敗した場合はその時点で調査する。

別ホストに入力データがあるとは仮定しない。未解決事項は統合記録を参照する。
