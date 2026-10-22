# Decision Log（KAMO fork）

このforkのコードに関する決定の記録。利用者が決めた方針と、その理由・影響を残す。

- 記録は日本語で書く。新しい決定は上に足す。
- ここに書くのは、このrepositoryのコードの決定である。repositoryをまたぐ決定、運用の決定、作業の経緯と試験の詳細は
  `zoo-hub`（`git@github.com:kuntaro0524/zoo-hub.git`）の`docs/development/decision-log.md`と`docs/work-items/`にある。
  詳細は二重に書かず、下の「詳細」から参照する。
- 未承認の提案や推測は決定として書かない。決まっていないことは`UNDECIDED`と書く。
- 記録を始めたのは2026-10-20。それ以前の決定のうち、直近の3件（KAMO-002、003、004）だけを最初に書いた。

## 2026-10-20 — 分解能探索を代表clusterだけで行う案（KAMO-003）は実装しない（見送り）

### 決定

`kamo.auto_multi_merge`が分解能を決める間、代表clusterだけをmergeして時間を減らす案は、実装しない。
状態は見送り（`PAUSED`）で、よい案が出たら立ち返る。branchは作っていない。

### 理由

代表を1つにすると、全clusterで決めた分解能からずれる。標本約180条件（cc 91条件、blend、30度データと10度データ）で、
ccは約8%、blendは11〜27%の条件が、利用者の許容（分解能に依存し、約5%）を超えた。
3.8→4.0 Åは許容、1.8→1.6 Åや2.0→1.8 Åのような高分解能側の動きは嫌、という基準である。
データセット数・格子のばらつき・完全性・冗長度で条件を足す案は、標本によって改善と悪化が逆になった。
「最後に全clusterをmergeするので`_final`の質は変わらない」は誤りだった。2回目の分解能が変わると`_final`の分解能が変わる。

### 影響

- コードは変わっていない。
- 再開の条件（`UNDECIDED`）: 代表で決めた分解能と全clusterの分解能のずれを実行中に検出する案、10度など別のwedgeの標本の追加、
  ほかの方法（cluster並列化）で時間が足りなくなること。「2つ程度の代表clusterで決める」案は、調べていない。

### 詳細

zoo-hub `docs/work-items/KAMO-003.md`（比較結果と再現手順）、`docs/development/decision-log.md`の同日の項。

## 2026-10-20 — `/dev/shm`に一時directoryを作れないときは、次の候補へ進み、警告を出す（KAMO-004）

### 決定

`yamtbx/util/__init__.py`の`get_temp_local_dir`は、候補の一時directoryの作成（`mkdtemp`）が`OSError`で失敗したら、
次の候補（`tempfile.gettempdir()`など）へ進む。救済したときは、標準エラーへ目立つ警告を出す。すべての候補が失敗したときは、
従来どおり例外にする。`/dev/shm`が正常なときの動作と出力は変えない。

### 理由

2026-10-19、`/dev/shm`にdirectoryを作れず、`check_xds_version()`が`FileNotFoundError`で止まり、blendのmergeが`_failed`になった
（全clusterのエラー出力に同じ例外）。それまでは候補の失敗を捕まえて次へ進む処理がなく、`xscale.use_tmpdir_if_available`もこの箇所に効かなかった。
修正前の再現と、修正後に`_final`と警告が出ることを、実際の流れで確かめた。

### 影響

- `integration/upstream-20260911`へfast-forwardで採用済み（commit `3525b3f`）。PRは作っていない。
- 共通runtimeには反映していない（試験版runtimeにだけ入っている）。
- `/dev/shm`が使えなくなった根本原因は調べていない。

### 詳細

zoo-hub `docs/work-items/KAMO-004.md`。

## 2026-10-09 — 分解能を決められないとき、殻からの推定を選べるようにし、決められなければ`_failed`にする（KAMO-002）

### 決定

- `rescut.fit_fallback`を追加した。`none`（既定）は、CC(1/2)の曲線の当てはめが使えないとき、分解能を決めない。
  `shells`は、低分解能側の殻から順に見て、CC(1/2)が基準を下回る最初の殻の手前を初期値にして、既存の走査と二分法へ渡す。
- 分解能を決められなかったmergeは、`_final`にせず、directory名の末尾を`_failed`にする。
  **これは設定に関係なく効く既定動作の変更である。** 変更前は、例外で止まるか、その時点のdirectoryを`_final`にしていた。
- `rescut.skip_no_signal`を追加した。分解能の判定に使う結果の選び方（冗長度の上位半分のうちCC(1/2)最大）は変えずに、
  最も内側の殻にCC(1/2)の信号がない結果を、選ぶ候補から外す。

### 理由

開始分解能が高いと、当てはめの値が負になり、`CCTBX_ASSERT(d_min > 0)`で止まっていた（旧mergeで`_final`ができなかった5件）。
殻からの推定で、4件は同じ試料の別方式の旧最終分解能に近い値になり、1件（全殻でCC(1/2)が基準未満）は決められないと判定された。
殻からの推定は、頑健さの評価が難しいため、既定にはしなかった。`_failed`という名前は利用者の提案である。
`skip_no_signal`は、全体のCC(1/2)が信号のない殻に支配され、中身のない3 datasetのclusterが選ばれていた例を直す。

### 影響

- `integration/upstream-20260911`へfast-forwardで採用済み（2026-10-09）。`main`は上流統合前の古い系列のため、採用先にしていない。
- 共通runtime（`/staff/Common/kuntaro/kamodev/runtimes/current`）には反映していない（利用者の決定、2026-10-09）。
  反映すると`_failed`の既定動作の変更が他の利用者の処理に及ぶため、影響は未確認。反映の検討は`UNDECIDED`。
- KAMO-002入りのKAMOに`fit_fallback`と`skip_no_signal`を渡すと有効になる。入っていないKAMOに渡すと、知らない設定として
  扱われ、`kamo.auto_multi_merge`は`_final`も`_failed`も作らずに終了する。
- 開始分解能が高いと、低分解能域に入る殻が1〜2個しかなく、殻からの推定は粗くなる（未対応）。

### 詳細

zoo-hub `docs/work-items/KAMO-002.md`、`docs/development/decision-log.md`の2026-10-09の各項（「KAMOの分解能決定に殻からの推定をoptionで加え…」「KAMO-002をupstream統合branchへ…」）。
