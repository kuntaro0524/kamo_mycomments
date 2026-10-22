# Kay 特殊 XDS/XSCALE の個人管理領域利用 — 2026-09-11

ユーザー判断: Kay 氏が個別にコンパイルした特殊 XDS/XSCALE build は、利用条件に反しない
ことを確認したうえで、ユーザー管理の `/staff/Common/kuntaro/kamodev/` 配下に専用 directory
として置き、本人の解析に使用する方針。

これは Git repository への binary 追加や一般配布を意味しない。binary は専用 directory に
保管し、Git には wrapper、activation、version、checksum、取得元と利用条件だけを記録する。
Slurm 計算ノードから同じ絶対パスで見えることを確認し、実行中の更新を避ける。
Kay 氏の許諾範囲、binary の有効期限、source/build 情報は未確認であり、取得時に記録する。

現時点では binary の配置、faketime 導入、Slurm 本処理は未実施。
