# Fork と本家の差分調査（2026-09-11）

## 対象

GitHub から fetch して確認した。

- Fork: kuntaro0524/kamo_mycomments、main = 662864d474c87d67e351c3599e44a57debc86239
- 本家: keitaroyam/yamtbx、master = b4b12bd979886e50a537e28ab78ad13050776205（2026-09-02）
- 調査用 clone: /home/kuntaro/kamodev/kamo-merge-review
- 既存運用 checkout と GitHub 上の branch は変更していない。

## 履歴上の注意

Fork main は a89f92c を root とする計6コミットで、本家との merge-base がない。
shallow clone ではない。通常の ahead/behind を「351コミット遅れ」と解釈するのは誤り。

Fork の root のツリーは、本家 d619df5（2023-12-13）と比較して
cc_clustering.py のコメント・空白追加のみが異なる。他ファイルは一致する。
このため、コード内容の比較基準として d619df5 を用いた。
本家にはその後24コミットある。ただし Fork の後続変更に本家修正の一部が含まれるため、
24コミットすべてが丸ごと未反映という意味ではない。

## 差分と判断

本家最新と Fork main のツリー差分は48ファイル。
2023-12-13 の比較基準と Fork main の差分は5ファイル（197行追加、13行削除）。

Fork 側の変更対象:

- kuntest/list_in.py
- yamtbx/dataproc/auto/cc_clustering.py
- yamtbx/dataproc/auto/command_line/auto_multi_merge.py
- yamtbx/dataproc/auto/command_line/multi_merge.py
- yamtbx/dataproc/auto/multi_merging/xscale.py

独自変更の中心は説明コメント、cctable.dat の出力精度、新しい XSCALE 向けの
huge_large_wedge_merge / 相関出力抑制 / 補正画像出力抑制 / 補正項指定。
これらの XSCALE オプションは既定 False / None である。

本家の更新には wxPython GUI、Slurm の sacct による状態判定・メモリ指定、
AutoJobManager、処理の deadlock、XDS June 2024 の出力対応、LIB=、Eiger、
Python 3 / NumPy 互換性修正が含まれる。影響を「ほぼない」とは断定できない。
一方、変更範囲は確認可能で、本家更新を取り込んでから baseline を確立する方針は妥当。

cctable.dat の精度改善は本家 e7ac5d0 にも取り込まれている。
統合時は独自コメントを残しつつ、本家の %13.11f を基準に重複を整理するのが適切。

## 統合方針

1. 現 Fork commit を保存する。
2. 作業ブランチで本家最新版を土台に、上記5ファイルの独自差分を照合して統合する。
   共通祖先がないため、単純な通常 merge はできない。
3. 本家履歴を今後追跡できるようにする。既存 main を force-push する方式は避ける。
4. installation check と小規模実処理を行い、統合結果を検証する。
5. 合格した統合 commit を開発開始時の baseline とする。

この調査時点では merge commit 作成、push、環境切替、科学的処理は未実施。

再確認コマンド（調査用 clone 内）:

```bash
git fetch origin
git fetch upstream
git merge-base origin/main upstream/master
git diff d619df5 a89f92c
git log --oneline d619df5..upstream/master
git diff --stat d619df5 origin/main
git diff --stat upstream/master origin/main
```
