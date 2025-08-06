import os
import collections
from yamtbx.dataproc.xds.xds_ascii import XDS_ASCII
from yamtbx.dataproc.auto.command_line.multi_merge import merge_datasets
from cctbx import sgtbx

def load_clusters_txt(path):
    clusters = {}
    with open(path) as f:
        for line in f:
            if line.strip().startswith("ClNumber") or not line.strip():
                continue
            parts = line.strip().split()
            clid = int(parts[0])
            clheight = float(parts[2])
            ids = list(map(int, parts[3:]))
            clusters[clid] = [clheight, ids]
    return clusters

def load_filenames_lst(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]

def guess_cells_and_spacegroup(xds_files):
    cells = collections.OrderedDict()
    laues = {}
    for f in xds_files:
        symm = XDS_ASCII(f, read_data=False).symm
        cells[f] = symm.unit_cell().parameters()
        laue = symm.space_group().build_derived_reflection_intensity_group(False).info()
        laues.setdefault(str(laue), {}).setdefault(symm.space_group_info().type().number(), []).append(f)

    if len(laues) != 1:
        raise RuntimeError("More than one Laue group detected")
    
    sg_number = list(laues.values())[0].keys()
    sg_number = list(sg_number)[0]
    space_group = sgtbx.space_group_info(sg_number).group()
    return cells, space_group

def main(cc_dir="cc_clustering", out_root="merge_result", params=None):
    clusters = load_clusters_txt(os.path.join(cc_dir, "CLUSTERS.txt"))
    filenames = load_filenames_lst(os.path.join(cc_dir, "filenames.lst"))

    all_files = [filenames[i - 1] for ids in clusters.values() for i in ids[1]]
    cells, space_group = guess_cells_and_spacegroup(all_files)

    for clid, (clheight, ids) in clusters.items():
        cluster_name = f"cluster_{clid:04d}"
        workdir = os.path.join(out_root, cluster_name)
        os.makedirs(workdir, exist_ok=True)
        xds_files = [filenames[i - 1] for i in ids]
        print(f"Running merge_datasets for {cluster_name} ({len(xds_files)} files)")

        # 実行
        results = merge_datasets(params, workdir, xds_files, cells, space_group)

        if not results:
            print(f"Failed: {cluster_name}")
        else:
            print(f"Done: {cluster_name}")

# ここで params を読み込み（たとえば pickle から）あるいは外部で作って渡す必要がある
if __name__ == "__main__":
    import pickle
    # auto_multi_merge.py などで作った params を保存しておいたものを使う
    with open("params.pkl", "rb") as f:
        params = pickle.load(f)
    main(cc_dir="cc_clustering", out_root="merge_result", params=params)

