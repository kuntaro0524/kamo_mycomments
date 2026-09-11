# XDS / XSCALE 実体調査と移植方針 — 2026-09-11

対象ホスト: robo04。調査は読み取りのみ。KAMO / DIALS runtime、共有 `/oys`、
XDS binary は変更していない。実データ処理も行っていない。

## 現在の参照

現在の PATH は `/oys/xtal/xds/xds_faketime_wrapper` を先頭に置き、以下を参照する。

| command | wrapper | wrapper の実体指定 |
| --- | --- | --- |
| xds, xds_par, xscale | `/oys/xtal/xds/xds_faketime_wrapper/{xds,xds_par,xscale}` | `/oys/xtal/xds/XDS-INTEL64_Linux_x86_64/Original/` |
| xscale_par | `/oys/xtal/xds/xds_faketime_wrapper/xscale_par` | `/oys/xtal/xds/kay_20250823_xscale/` |

`/oys/xtal/xds/XDS-INTEL64_Linux_x86_64` は
`XDS-INTEL64_Linux_x86_64_20250401` への symlink。実体 directory には
XDS 一式と 2025-04-30 build の binary がある。`xscale_par` は別の
`kay_20250823_xscale` directory に単独で存在する。

引数なし起動で、XDS は `VERSION Jan 19, 2025 BUILT=20250430`、XSCALE は
`VERSION Jan 19, 2025 BUILT=20250823` を表示した。wrapper の既定
`XDS_FAKETIME` は `2026-03-30 12:00:00`。libfaketime は wrapper が
`/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1` 等から探索する。

主要 binary の SHA-256:

```text
xds       a461a813c0cb76d16903de6a0240b6348aab049a189e1936ff28bdbfdf105e60
xds_par   b0b95f97c84cf73cb877e1e021a98210ae74830545c19c34b313bb9d7b8c0aad
xscale    f9c9a638d32d16e9b50bccb622e0f2fc48e3c8f826df612e19706f58b789050d
xscale_par 783892522b0980edd925da462db7c9734cd610bdad6e0338e922fa2ec7e429d7
```

各 binary は ELF x86-64。`ldd` では libc、libm、libgomp、libgcc_s、libquadmath、
libpthread、libdl、loader 等の OS library を参照し、XDS/XSCALE 専用の同梱 shared
library は確認できない。xscale_par は libubsan と libstdc++ も参照する。

## 移植できる範囲と制約

binary の起動メッセージに作者の `No redistribution.` が含まれる。したがって、
この repository や `/staff/Common/kuntaro/kamodev/` へ binary をコピーして配布することはしない。
移植は「同じ版の binary を正規の入手経路・利用条件で対象環境に配置し、checksum と
実体 path を記録する」方式にする。利用許諾と期限を無視して faketime で延長する構成は採用しない。

移植先で必要なもの:

1. XDS の配布元から正規に取得した XDS 一式（xds, xds_par, xscale 等）。
2. 希望する XSCALE build（通常 XDS 一式の xscale、特別 build の xscale_par）と入手条件。
3. x86-64 対応 OS、glibc、libgomp、libstdc++ 等の runtime compatibility。
4. `xds_par` / `xscale_par` の実体を指すユーザー管理 wrapper または PATH。
5. 実体 checksum、表示された version / build、license 期限、node 種別を記録。

wrapper は現在、コメントでは `XDS_REAL_BIN_DIR` の user override を案内しているが、
実際には先に `export XDS_REAL_BIN_DIR=...` しているため、環境変数での上書きができない。
移植用に再利用する場合は、サイト配布 wrapper を変更せず、ユーザー管理領域に別 wrapper を
作り、実体 directory をその wrapper に固定する。faketime を使う場合は、作者の明示許可、
対象 binary、固定時刻、libfaketime の実体と checksum、計算ノードでの動作を別記録にする。

## 次回の実装候補

クラスタの共有 runtime では、当面 `xds/20260610` のサイト提供 module を使用する方針が
先行記録にある。robo04 の `/oys` wrapper を kuri へコピーしない。
XDS/XSCALE を自分で管理する必要がある場合は、まず管理者・配布元から正規 binary の
取得方法と利用条件を確認し、runtime 内ではなく共有ユーザー領域の専用 directory に置く。
その directory と wrapper を Slurm の最小 probe で確認してから KAMO に使わせる。

本調査で「移植可能」と確認できたのは、依存が主に OS library であること、wrapper の
構成、実体の version / checksum を再現できることまで。binary を持ち運べる権利、
2025-08 build の現在の利用可否、faketime の運用可否は未確認である。
