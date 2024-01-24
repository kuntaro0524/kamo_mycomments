# cc_clustering.py に含まれている処理を確認するためのファイル

# 15個のリストを作成。各養素はランダムな整数の３つの配列
arrays = []
for i in range(20):
    arrays.append([i, i+1, i+2])

print(len(arrays))

nans = [(3,6),(3,15),(4,5),(10,15),(1,10),(4,10)]

idx=3

idx_bad = {}

idx_bad[1] = 1
idx_bad[3] = 2
idx_bad[4] = 2
idx_bad[5] = 1
idx_bad[6] = 1
idx_bad[10] = 3
idx_bad[15] = 2

remove_idxes = set()

# listに変換してからsortする
idx_bad = list(idx_bad.items())
idx_bad.sort(key=lambda x:x[1])

for idx, badcount in reversed(idx_bad):
    print("Current nans: ", nans)
    print("processing idx: ", idx)
    if len([x for x in nans if idx in x]) == 0: continue
    print("GOGOGOGOG")
    remove_idxes.add(idx)

    nans = [x for x in nans if idx not in x]
    if len(nans) == 0: break

print(remove_idxes)

# use_indxes 
use_idxs = [x for x in range(len(arrays)) if x not in remove_idxes]
print(use_idxs)

# Make table: original index (in file list) -> new index (in matrix)
count = 0
import collections
org2now = collections.OrderedDict()
for i in range(len(arrays)):
    if i in remove_idxes: continue
    org2now[i] = count
    count += 1

print(org2now)