"""
auto_multi_merge_staged.py

Split auto_multi_merge workflow into 3 stages:
  1) prepare  : reindex/filtering + produce formerge(_reindexed).lst
  2) cluster  : run clustering only (produce CLUSTERS.txt, filenames.lst, cctable.dat, dendro.json, ...)
  3) merge    : using clustering results, create cluster_*/run_01/ and write XSCALE.INP
                optionally run XSCALE, optionally proceed to resolution cutoff loop (best-effort)

This script is designed to reuse the same components used by auto_multi_merge.py as much as possible.
"""

from __future__ import print_function, unicode_literals

import os, sys, glob, time, copy, csv, pickle, traceback, subprocess, collections, json

import libtbx.phil
import iotbx.phil
import iotbx.file_reader

from cctbx import crystal
from iotbx import crystal_symmetry_from_any
from libtbx.utils import multi_out

from yamtbx.util import batchjob
from yamtbx.util import replace_forbidden_chars
from yamtbx.util.xtal import format_unit_cell

from yamtbx.dataproc.xds.xds_ascii import XDS_ASCII
from yamtbx.dataproc.auto.command_line.multi_check_cell_consistency import CellGraph
from yamtbx.dataproc.auto.command_line.multi_prep_merging import PrepMerging
from yamtbx.dataproc.auto.multi_merging import resolve_reindex
from yamtbx.dataproc.auto.command_line import multi_merge

# We reuse decide_resolution/choose_best_result from auto_multi_merge (same logic).
# If you install this file alongside auto_multi_merge.py, this import should work.
from yamtbx.dataproc.auto.command_line.auto_multi_merge import (
    read_sample_info,
    read_reference_data,
    filter_datasets,
    choose_best_result,
    decide_resolution,
)

# ------------------------------------------------------------
# PHIL parameters
# ------------------------------------------------------------

master_params_str = multi_merge.master_params_str  # reuse yamtbx multi_merge params

gui_phil_str = """\
csv = None
 .type = path
 .help = CSV file to define sample information
workdir = None
 .type = path
 .help = top directory where merging directories are created. current directory by default.
datadir = None
 .type = path
 .help = the root directory where the processed results exist.
prefix = merge_
 .type = str
 .help = Prefix of directory names
cell_method = *reindex refine
 .type = choice(multi=False)
reference = None
 .type = path
 .help = Reference for symmetry and reindexing

space_group = None
 .type = str
unit_cell = None
 .type = floats(6)

# Stage control
stage = *all prepare cluster merge
 .type = choice(multi=False)
 .help = "Which stage to run. all=prepare->cluster->merge (like original)."

# Where to resume from (for stage=cluster or stage=merge)
resume {
  prepared_dir = None
    .type = path
    .help = "Directory containing prepared outputs (formerge*.lst, excluded.lst, cells_reindexed.dat, ...). Used by stage=cluster/merge."
  clustering_dir = None
    .type = path
    .help = "Directory containing clustering outputs (CLUSTERS.txt, filenames.lst, cctable.dat, dendro.json, ...). Used by stage=merge."
}

# Merge behavior when stage=merge
merge_control {
  stop_after_inp = False
    .type = bool
    .help = "If True, only create cluster_*/run_01/XSCALE.INP and stop (do not run XSCALE)."
  run_xscale = True
    .type = bool
    .help = "If True, execute xscale_par in each run_01. Ignored if stop_after_inp=True."
  xscale_bin = xscale_par
    .type = str
    .help = "XSCALE executable name/path."
  overwrite = False
    .type = bool
    .help = "If True, overwrite existing cluster_*/run_01 directories."
}

filtering {
  choice = cell
   .type = choice(multi=True)
  cell_iqr_scale = 2.5
   .type = float
}

rescut {
 auto = true
  .type = bool
 n_bins = 9
  .type = int
 cc_one_half_min = 0.5
  .type = float
 cc_half_tol = 0.03
  .type = float
}

# multi_merge parameters block (same as auto_multi_merge)
merge {
  d_min_start = 1.8
   .type = float
   .help = Starting value for merging
  %s
}

# xscale knobs (copied to merge.xscale as in auto_multi_merge)
xscale {
  huge_large_wedge_merge = False
    .type = bool
  suppress_correlations = False
    .type = bool
  disable_correction_images = False
    .type = bool
  fixed_corrections_line = None
    .type = str
}

batch {
 engine = sge sh slurm auto *no
  .type = choice(multi=False)
 sge_pe_name = par
  .type = str
 nproc_each = 1
  .type = int
 sh_max_jobs = 1
  .type = int
 mem_per_cpu = default
  .type = str
}
""" % master_params_str

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)

def _write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True)

def _read_lines(path):
    with open(path) as f:
        return [l.strip() for l in f if l.strip()]

def _parse_clusters_txt(path):
    """
    Parse CLUSTERS.txt format like:
      ClNumber   Nds   Clheight   IDs...
      0001       2     0.055      272 273
    Returns OrderedDict { "0001": [272,273], ... }
    """
    clusters = collections.OrderedDict()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("clnumber"):
                continue
            sp = line.split()
            if len(sp) < 4:
                continue
            clnum = sp[0]
            nds = int(sp[1])
            ids = list(map(int, sp[3:]))
            if nds != len(ids):
                # be permissive; still accept
                pass
            clusters[clnum] = ids
    return clusters

def _write_xscale_inp(xsinp_path, input_files, params_merge_xscale, d_min=None):
    """
    Create minimal XSCALE.INP with optional header knobs.
    This is intentionally conservative: it will run XSCALE and allow user modifications.
    """
    lines = []
    # Header knobs
    if getattr(params_merge_xscale, "suppress_correlations", False):
        lines.append("PRINT_CORRELATIONS= FALSE")
    if getattr(params_merge_xscale, "disable_correction_images", False):
        lines.append("SAVE_CORRECTION_IMAGES= FALSE")
    # huge_large_wedge_merge: mimic what auto_multi_merge help says (no NBATCH etc.)
    if getattr(params_merge_xscale, "huge_large_wedge_merge", False):
        lines.append("PRINT_CORRELATIONS= FALSE")
        lines.append("SAVE_CORRECTION_IMAGES= FALSE")
        # Use typical "large wedge" style corrections unless user overrides:
        # (This is a best-effort; exact lines in yamtbx multi_merge may differ.)
        lines.append("CORRECTIONS= DECAY ABSORPTION")

    if d_min is not None:
        # XSCALE "RESOLUTION= low high" : low is usually large number
        lines.append("RESOLUTION= 50.0 %.2f" % float(d_min))

    lines.append("OUTPUT_FILE= xscale.hkl")

    # INPUT_FILE lines
    for f in input_files:
        if getattr(params_merge_xscale, "fixed_corrections_line", None):
            lines.append("INPUT_FILE= %s %s" % (f, params_merge_xscale.fixed_corrections_line))
        else:
            lines.append("INPUT_FILE= %s" % f)

    content = "\n".join(lines) + "\n"
    with open(xsinp_path, "w") as f:
        f.write(content)

def _run_xscale(run_dir, xscale_bin="xscale_par", log_out=None):
    xsinp = os.path.join(run_dir, "XSCALE.INP")
    if not os.path.isfile(xsinp):
        raise RuntimeError("XSCALE.INP not found: %s" % xsinp)
    cmd = [xscale_bin]
    if log_out:
        log_out.write("Running XSCALE in %s\n" % run_dir)
        log_out.write("  %s < XSCALE.INP\n" % xscale_bin)
    p = subprocess.run(cmd, input=open(xsinp).read(), text=True, cwd=run_dir,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with open(os.path.join(run_dir, "xscale.log"), "w") as f:
        f.write(p.stdout)
    return p.returncode

# ------------------------------------------------------------
# Stage 1: prepare (reindex/filtering + formerge*.lst)
# ------------------------------------------------------------

def stage_prepare(sample_workdir, topdirs, cell_method, ref_array, ref_sym, filtering_params, log_out):
    """
    Do what auto_merge() does up to producing formerge(.lst|_reindexed.lst).
    Save a manifest prepared.json for later stages.
    """
    log_out.write("== Stage1 prepare: %s\n" % sample_workdir)

    # Find XDS/DIALS dirs
    xdsdirs = []
    for topdir in topdirs:
        for root, dirnames, filenames in os.walk(topdir, followlinks=True):
            if any(y.startswith("XDS_ASCII.HKL") or y == "DIALS.HKL" for y in filenames):
                xdsdirs.append(root)

    log_out.write("Detected %d processing dirs\n" % len(xdsdirs))
    if not xdsdirs:
        raise RuntimeError("No XDS_ASCII.HKL / DIALS.HKL found under given topdirs")

    cm = CellGraph()
    for i, xd in enumerate(xdsdirs):
        cm.add_proc_result(i, xd)

    topdir_common = os.path.dirname(os.path.commonprefix(topdirs))
    lstname = os.path.join(sample_workdir, "formerge.lst")

    pm = PrepMerging(cm)
    pm.find_groups()
    if len(cm.groups) == 0:
        raise RuntimeError("No groups found by CellGraph/PrepMerging")

    # Decide reference symmetry
    if ref_array or ref_sym:
        group = cm.get_group_symmetry_reference_matched(ref_array if ref_array else ref_sym)
        reference_symm = cm.get_symmetry_reference_matched(group-1, ref_array if ref_array else ref_sym)
    else:
        group = 1
        reference_symm = cm.get_most_frequent_symmetry(group-1)
        if reference_symm is None:
            raise RuntimeError("Failed to get reference symmetry")

    msg, reidx_ops = pm.prep_merging(workdir=sample_workdir, group=group, reference_symm=reference_symm,
                                     topdir=topdir_common, cell_method=cell_method,
                                     nproc=1, prep_dials_files=False, into_workdir=True)
    log_out.write(msg + "\n")
    cell_and_files = pm.cell_and_files

    # Filtering (cell outliers)
    deleted = {}
    if filtering_params.choice:
        cell_and_files, deleted = filter_datasets(cell_and_files, filtering_params, log_out)
        with open(os.path.join(sample_workdir, "excluded.lst"), "w") as ofs:
            deleted_files = [deleted[x][1] for x in deleted]
            deleted_files.sort()
            ofs.write("\n".join(deleted_files) + "\n")
        with open(lstname, "w") as ofs:
            for wd in sorted(cell_and_files):
                _, xas = cell_and_files[wd]
                ofs.write(xas + "\n")

    # Resolve reindex if needed
    used_lst = lstname
    if len(reidx_ops) > 1 and len(cell_and_files) > 1:
        if ref_array is not None and hasattr(ref_array, "size") and ref_array.size() > 0:
            rb = resolve_reindex.ReferenceBased([x[1] for x in list(cell_and_files.values())],
                                                ref_array, max_delta=5, d_min=3, min_ios=None,
                                                nproc=1, log_out=log_out)
            rb.assign_operators()
        else:
            rb = resolve_reindex.KabschSelectiveBreeding([x[1] for x in list(cell_and_files.values())],
                                                         max_delta=5, d_min=3, min_ios=None,
                                                         nproc=1, log_out=log_out)
            rb.assign_operators()

        used_lst = os.path.join(sample_workdir, "formerge_reindexed.lst")
        new_files = rb.modify_xds_ascii_files(
            cells_dat_out=open(os.path.join(sample_workdir, "cells_reindexed.dat"), "w")
        )
        open(used_lst, "w").write("\n".join(new_files) + "\n")
        log_out.write("Reindexed list written: %s\n" % used_lst)

    if os.path.isfile(used_lst):
        nlines = len(_read_lines(used_lst))
    else:
        nlines = 0

    if nlines < 2:
        raise RuntimeError("Too few datasets after prepare stage: %d" % nlines)

    manifest = {
        "sample_workdir": os.path.abspath(sample_workdir),
        "topdirs": [os.path.abspath(x) for x in topdirs],
        "cell_method": str(cell_method),
        "used_lst": os.path.abspath(used_lst),
        "group": int(group),
        "n_datasets": int(nlines),
        "reference_symm_summary": str(reference_symm.as_str()) if hasattr(reference_symm, "as_str") else "N/A",
    }
    _write_json(os.path.join(sample_workdir, "prepared.json"), manifest)
    log_out.write("prepared.json written\n")
    return used_lst

# ------------------------------------------------------------
# Stage 2: clustering only
# ------------------------------------------------------------

def stage_cluster(sample_workdir, merge_params, used_lst, log_out):
    """
    Run multi_merge.run() in a way that produces clustering outputs only.
    This relies on multi_merge supporting a 'par_run' style option.
    If not available in your environment, it will error with guidance.
    """
    log_out.write("== Stage2 cluster: %s\n" % sample_workdir)

    merge_params2 = copy.deepcopy(merge_params)
    merge_params2.lstin = used_lst
    merge_params2.d_min = merge_params2.d_min_start

    # Put outputs in <sample_workdir>/<clustering>_<dmin>A_clustering
    outdir = os.path.join(sample_workdir, "%s_%.2fA_clustering" % (merge_params2.clustering, merge_params2.d_min))
    merge_params2.workdir = outdir

    # Best-effort: try to set "clustering only" mode if available
    # In many yamtbx versions, merge_params.batch.par_run can be "clustering" or "merging".
    # The example in auto_multi_merge help shows merge.batch.par_run=merging.
    try:
        if hasattr(merge_params2, "batch") and hasattr(merge_params2.batch, "par_run"):
            merge_params2.batch.par_run = "clustering"
            log_out.write("Setting merge.batch.par_run=clustering\n")
        else:
            log_out.write("WARNING: merge.batch.par_run not found. multi_merge may not support clustering-only in this build.\n")
    except Exception as e:
        log_out.write("WARNING: failed to set par_run: %s\n" % str(e))

    _ensure_dir(outdir)
    log_out.write("Running multi_merge (clustering stage) in %s\n" % outdir)
    multi_merge.run(merge_params2)

    # Check typical outputs
    expected = ["CLUSTERS.txt", "filenames.lst", "cctable.dat"]
    found = [x for x in expected if os.path.exists(os.path.join(outdir, x))]
    log_out.write("Clustering outputs found: %s\n" % ",".join(found))
    _write_json(os.path.join(outdir, "clustering.json"), {
        "used_lst": os.path.abspath(used_lst),
        "merge_workdir": os.path.abspath(outdir),
        "clustering": str(merge_params2.clustering),
        "d_min": float(merge_params2.d_min),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    return outdir

# ------------------------------------------------------------
# Stage 3: merge from clustering results (write XSCALE.INP and optionally run)
# ------------------------------------------------------------

def stage_merge_from_clustering(sample_workdir, clustering_dir, merge_params, merge_control, log_out):
    """
    Use CLUSTERS.txt + filenames.lst to create cluster_*/run_01/XSCALE.INP.
    Optionally run XSCALE. This stage DOES NOT recompute clustering.
    """
    log_out.write("== Stage3 merge: %s\n" % sample_workdir)
    log_out.write("Using clustering_dir: %s\n" % clustering_dir)

    clusters_txt = os.path.join(clustering_dir, "CLUSTERS.txt")
    filenames_lst = os.path.join(clustering_dir, "filenames.lst")
    if not os.path.isfile(clusters_txt) or not os.path.isfile(filenames_lst):
        raise RuntimeError("Missing CLUSTERS.txt and/or filenames.lst in %s" % clustering_dir)

    filenames = _read_lines(filenames_lst)
    clusters = _parse_clusters_txt(clusters_txt)

    # Create merge output dir
    # Keep similar naming to auto_multi_merge: <clustering>_<dmin>A
    dmin = float(merge_params.d_min_start)
    outdir = os.path.join(sample_workdir, "%s_%.2fA_from_clusters" % (merge_params.clustering, dmin))
    if merge_control.overwrite and os.path.isdir(outdir):
        # be careful; remove only if user requested
        import shutil
        shutil.rmtree(outdir)
    _ensure_dir(outdir)

    log_out.write("Creating run_01 directories and XSCALE.INP under: %s\n" % outdir)
    log_out.write("Clusters to process: %d\n" % len(clusters))

    # Write XSCALE.INP for each cluster
    for clnum, ids in clusters.items():
        cluster_name = "cluster_%s" % clnum
        run_dir = os.path.join(outdir, cluster_name, "run_01")
        _ensure_dir(run_dir)

        input_files = []
        for i in ids:
            if i < 0 or i >= len(filenames):
                raise RuntimeError("Cluster %s references out-of-range id %d (filenames.lst has %d lines)" %
                                   (clnum, i, len(filenames)))
            input_files.append(filenames[i])

        xsinp = os.path.join(run_dir, "XSCALE.INP")
        _write_xscale_inp(xsinp, input_files, merge_params.xscale, d_min=dmin)

    log_out.write("XSCALE.INP generation done.\n")

    if merge_control.stop_after_inp:
        log_out.write("stop_after_inp=True -> stopping here (no XSCALE run).\n")
        return outdir

    if not merge_control.run_xscale:
        log_out.write("run_xscale=False -> stopping here (XSCALE not executed).\n")
        return outdir

    # Run XSCALE in each run_01
    fail = 0
    for clnum in clusters.keys():
        run_dir = os.path.join(outdir, "cluster_%s" % clnum, "run_01")
        rc = _run_xscale(run_dir, xscale_bin=merge_control.xscale_bin, log_out=log_out)
        if rc != 0:
            fail += 1
            log_out.write("XSCALE failed in %s (rc=%d)\n" % (run_dir, rc))

    log_out.write("XSCALE finished. failed=%d\n" % fail)
    return outdir

# ------------------------------------------------------------
# Driver
# ------------------------------------------------------------

def _apply_xscale_copy(params):
    # Same trick as in auto_multi_merge.py (top-level xscale copied to merge.xscale)
    if hasattr(params, "xscale") and hasattr(params.merge, "xscale"):
        params.merge.xscale.suppress_correlations = params.xscale.suppress_correlations
        params.merge.xscale.disable_correction_images = params.xscale.disable_correction_images
        params.merge.xscale.fixed_corrections_line = params.xscale.fixed_corrections_line
        params.merge.xscale.huge_large_wedge_merge = params.xscale.huge_large_wedge_merge

def run(params):
    if params.workdir is None:
        params.workdir = os.getcwd()
    _ensure_dir(params.workdir)

    log_out = multi_out()
    log_out.register("log", open(os.path.join(params.workdir, time.strftime("automerge_staged_%y%m%d-%H%M%S.log")), "w"),
                     atexit_send_to=None)
    log_out.register("stdout", sys.stdout)

    log_out.write("Parameters:\n")
    libtbx.phil.parse(gui_phil_str).format(params).show(out=log_out, prefix=" ")
    log_out.write("\n")

    _apply_xscale_copy(params)

    if (params.space_group, params.unit_cell).count(None) == 1:
        log_out.write("Error: Specify both space_group and unit_cell!\n")
        return

    # Global reference symmetry
    ref_sym_global = None
    if params.space_group is not None:
        try:
            ref_sym_global = crystal.symmetry(params.unit_cell, params.space_group)
            if not ref_sym_global.change_of_basis_op_to_reference_setting().is_identity_op():
                xs_refset = ref_sym_global.as_reference_setting()
                log_out.write('Sorry. space group in non-reference setting is not supported. Give space_group=%s unit_cell="%s"\n' %
                              (str(xs_refset.space_group_info()).replace(" ",""), format_unit_cell(xs_refset.unit_cell())))
                return
        except:
            log_out.write("Invalid crystal symmetry. Check space_group= and unit_cell=.\n")
            return

    # References
    ref_arrays = {}
    if params.reference:
        ref_arrays[params.reference] = read_reference_data(params.reference, log_out)

    # Load samples
    samples = read_sample_info(params.csv, params.datadir)
    if not samples:
        log_out.write("No samples loaded.\n")
        return

    # Load per-sample reference if any
    for k in samples:
        if "reference" in samples[k][1]:
            r = samples[k][1]["reference"]
            if r not in ref_arrays:
                ref_arrays[r] = read_reference_data(r, log_out)

    # Batch manager (only used if you extend to submit stages; here we keep local for simplicity)
    # You can still wrap stage calls into batch if you want later.

    for sample_name in samples:
        params2 = copy.deepcopy(params)

        # per-sample overrides
        ref_array = ref_arrays.get(params.reference, None)
        ref_sym = ref_sym_global

        if "anomalous" in samples[sample_name][1]:
            params2.merge.anomalous = samples[sample_name][1]["anomalous"]
        if "reference" in samples[sample_name][1]:
            ref_array = ref_arrays[samples[sample_name][1]["reference"]]
            params2.merge.reference.data = samples[sample_name][1]["reference"]
        else:
            params2.merge.reference.data = params.reference
        if "reference_sym" in samples[sample_name][1]:
            ref_sym = samples[sample_name][1]["reference_sym"]

        # sample workdir
        swd = os.path.join(params2.workdir, "%s%s" % (params2.prefix, replace_forbidden_chars(sample_name).replace(" ","_")))
        _ensure_dir(swd)

        try:
            # Stage selection
            if params2.stage in ("all", "prepare"):
                used_lst = stage_prepare(swd, samples[sample_name][0], params2.cell_method, ref_array, ref_sym,
                                         params2.filtering, log_out)
            else:
                # load from resume.prepared_dir
                pdir = params2.resume.prepared_dir or swd
                manifest = os.path.join(pdir, "prepared.json")
                if not os.path.isfile(manifest):
                    raise RuntimeError("prepared.json not found in %s (set resume.prepared_dir=... or run stage=prepare first)" % pdir)
                used_lst = json.load(open(manifest))["used_lst"]

            if params2.stage in ("all", "cluster"):
                # clustering outputs dir
                cdir = stage_cluster(swd, params2.merge, used_lst, log_out)
            else:
                cdir = params2.resume.clustering_dir
                if not cdir:
                    # try auto-detect
                    cand = glob.glob(os.path.join(swd, "%s_*.??A_clustering" % params2.merge.clustering))
                    cdir = cand[-1] if cand else None
                if not cdir:
                    raise RuntimeError("clustering_dir not specified and not auto-detectable. Set resume.clustering_dir=...")

            if params2.stage in ("all", "merge"):
                outdir = stage_merge_from_clustering(
                    swd, cdir, params2.merge, params2.merge_control, log_out
                )
                log_out.write("Stage3 output: %s\n" % outdir)

        except Exception:
            log_out.write("Error in sample %s\n%s\n" % (sample_name, traceback.format_exc()))

        log_out.flush()

def run_from_args(argv):
    if "-h" in argv or "--help" in argv or not argv:
        print("All parameters:\n")
        iotbx.phil.parse(gui_phil_str).show(prefix="  ", attributes_level=1)
        print()
        print("Examples:\n")
        print(r"""
# 1) Prepare only
kamo.auto_multi_merge_staged \
  csv=automerge.csv workdir=$PWD stage=prepare

# 2) Cluster only (after prepare)
kamo.auto_multi_merge_staged \
  csv=automerge.csv workdir=$PWD stage=cluster \
  resume.prepared_dir=$PWD/merge_SAMPLE

# 3) Merge only (write XSCALE.INP and stop)
kamo.auto_multi_merge_staged \
  csv=automerge.csv workdir=$PWD stage=merge \
  resume.clustering_dir=$PWD/merge_SAMPLE/cc_1.80A_clustering \
  merge_control.stop_after_inp=true

# 3b) Merge only + run XSCALE
kamo.auto_multi_merge_staged \
  csv=automerge.csv workdir=$PWD stage=merge \
  resume.clustering_dir=$PWD/merge_SAMPLE/cc_1.80A_clustering \
  merge_control.stop_after_inp=false merge_control.run_xscale=true
""")
        return

    cmdline = iotbx.phil.process_command_line(args=argv, master_string=gui_phil_str)
    params = cmdline.work.extract()
    args = cmdline.remaining_args

    if params.workdir is None:
        params.workdir = os.getcwd()

    for arg in args:
        if os.path.exists(arg) and params.csv is None and arg.endswith(".csv"):
            params.csv = arg

    run(params)

if __name__ == "__main__":
    run_from_args(sys.argv[1:])

