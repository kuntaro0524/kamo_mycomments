# 別環境での再開手順

これは統合版の調査・基本チェックを再開する手順。独立した KAMO 本番インストール手順は未確立。

## ソース取得と版確認

2026-09-11 時点で integration branch はまだ GitHub に push していない。
現時点では下記 GitHub clone だけで統合版を取得することはできない。
push 後に branch の存在を確認して実行する。先に転送する場合は Git 履歴を含む bundle 等で渡し、
対象 commit と文書 commit の両方を保存する。

```bash
git clone https://github.com/kuntaro0524/kamo_mycomments.git kamo
cd kamo
git fetch origin
git switch --track origin/integration/upstream-20260911
git remote add upstream https://github.com/keitaroyam/yamtbx.git
git status --short --branch
git rev-parse HEAD
git merge-base --is-ancestor c811f9f21a177bc97e9f21066d3585474aa880a1 HEAD
```

HEAD は追加の文書 commit で進む場合がある。コードの厳密な再現対象は上記統合 commit。
remote upstream が存在する場合は重複追加せず URL を確認する。

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

## 基本チェックの再実行

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

1. 必要な外部依存を確認・有効化し、不合格項目を解消する。
2. 共有稼働環境とは別の構成で、この checkout の libtbx 登録・dispatcher を整える。
3. 初期調査記録のデータ候補を確認し、入力 checksum と全パラメータを保存する。
4. 小規模処理、実データ処理、同条件再実行を行い、科学的 baseline を確立する。

別ホストに入力データがあるとは仮定しない。未解決事項は統合記録を参照する。
