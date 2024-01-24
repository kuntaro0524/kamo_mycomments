# LIBTBX_SET_DISPATCHER_NAME kamo.resolve_indexing_ambiguity
"""
(c) RIKEN 2015. All rights reserved. 
Author: Keitaro Yamashita

This software is released under the new BSD License; see LICENSE.
"""
from __future__ import print_function
from __future__ import unicode_literals

from yamtbx.dataproc.auto.multi_merging.resolve_reindex import ReindexResolver, ReferenceBased, BrehmDiederichs, KabschSelectiveBreeding
from yamtbx.util import read_path_list
from libtbx.utils import multi_out
import iotbx.phil
import libtbx.phil
import sys
import os

master_params_str = """
lstin = None
 .type = path
 .help = list of XDS_ASCII.HKL
streamin = None
 .type = path
 .help = crystfel stream files
 .multiple = true
precalc = None
 .type = path
 .help = "json file"
space_group = None
 .type = str
 .help = "Space group for stream files"
method = brehm_diederichs *selective_breeding reference precalc
 .type = choice(multi=False)
 .help = Method to resolve ambiguity
logfile = "reindexing.log"
 .type = path
 .help = logfile name
nproc = 1
 .type = int
 .help = number of processors
dry_run = False
 .type = bool
 .help = If true, do not modify files
skip_bad_files = False
 .type = bool
 .help = "Set true if you want to ignore bad files (too few reflections)"

d_min = 3
 .type = float
 .help = high resolution cutoff used in the method
min_ios = None
 .type = float
 .help = minimum I/sigma(I) cutoff used in the method
max_delta = 5
 .type = float
 .help = maximum obliquity used in determining the lattice symmetry, using a modified Le-Page algorithm.

max_cycles = 100
 .type = int(value_min=1)
 .help = Maximum number of cycles for selective_breeding algorithm.

reference_file = None
 .type = path
 .help = Only needed when method=reference
reference_label = None
 .type = str
 .help = data label of reference_file
"""

def run(params):
    log_out = multi_out()
    log_out.register("log", open(params.logfile, "w"), atexit_send_to=None)
    log_out.register("stdout", sys.stdout)

    libtbx.phil.parse(master_params_str).format(params).show(out=log_out, prefix=" ")

    xac_files = []
    if params.lstin:
        xac_files = read_path_list(params.lstin, only_exists=True, err_out=log_out)

        if len(xac_files) == 0:
            print("No (existing) files in the list: %s" % params.lstin, file=log_out)
            return

    elif not params.streamin:
        print("Give either listin= or streamin=.", file=log_out)
        return
        
    
    if params.method == "brehm_diederichs":
        rb = BrehmDiederichs(xac_files, params.streamin, params.space_group, max_delta=params.max_delta,
                             d_min=params.d_min, min_ios=params.min_ios,
                             nproc=params.nproc, log_out=log_out)
    elif params.method == "selective_breeding":
        rb = KabschSelectiveBreeding(xac_files, params.streamin, params.space_group, max_delta=params.max_delta,
                                     d_min=params.d_min, min_ios=params.min_ios,
                                     nproc=params.nproc, log_out=log_out)
    elif params.method == "reference":
        import iotbx.file_reader

        ref_file = iotbx.file_reader.any_file(params.reference_file)
        if ref_file.file_type == "hkl":
            ref_arrays = ref_file.file_server.miller_arrays
            if not ref_arrays:
                raise "No arrays in reference file"
            if params.reference_label is not None:
                ref_arrays = [x for x in ref_arrays if params.reference_label in x.info().labels]
                if not ref_arrays: raise "No arrays matched to specified label (%s)" % params.reference_label
                ref_array = ref_arrays[0].as_intensity_array()
            else:
                ref_array = None
                for array in ref_arrays:
                    if array.is_xray_intensity_array():
                        ref_array = array
                        print("Using %s as reference data" % array.info().label_string(), file=log_out)
                        break
                    elif array.is_xray_amplitude_array():
                        ref_array = array.f_as_f_sq()
                        print("Using %s as reference data" % array.info().label_string(), file=log_out)
                        break
        elif ref_file.file_type == "pdb":
            import mmtbx.utils
            xrs = ref_file.file_content.xray_structure_simple()
            fmodel_params = mmtbx.command_line.fmodel.fmodel_from_xray_structure_master_params.extract()
            fmodel_params.fmodel.k_sol = 0.35
            fmodel_params.fmodel.b_sol = 50
            fmodel_params.high_resolution = params.d_min
            ref_array = mmtbx.utils.fmodel_from_xray_structure(xray_structure=xrs, params=fmodel_params).f_model.as_intensity_array()
        else:
            raise "input file type invalid"

        if ref_array is None:
            raise "suitable reference data not found"

        rb = ReferenceBased(xac_files, params.streamin, params.space_group, ref_array, max_delta=params.max_delta,
                            d_min=params.d_min, min_ios=params.min_ios,
                            nproc=params.nproc, log_out=log_out)
    elif params.method == "precalc":
        if params.precalc is None:
            raise SystemExit("Give a json file to precalc=")
        rb = ReindexResolver(xac_files, params.streamin, params.space_group,
                             log_out=log_out)
        if xac_files:
            rb.read_xac_files()
        else:
            rb.read_stream_files(space_group=params.space_group)
    else:
        raise "Unknown method: %s" % params.method

    if rb.bad_files:
        print("%s: %d bad files are included:" % ("WARNING" if params.skip_bad_files else "ERROR", len(rb.bad_files)))
        for f in rb.bad_files: print("  %s" % f)
        if not params.skip_bad_files:
            print()
            print("You may want to change d_min= or min_ios= parameters to include these files.")
            print("Alternatively, specify skip_bad_files=true to ignore these files (they are not included in output files)")
            return

    if params.method == "precalc":
        rb.read_assigned_operators(params.precalc)
    elif params.method == "selective_breeding":
        rb.assign_operators(max_cycle=params.max_cycles)
    else:
        rb.assign_operators()

    rb.show_assign_summary()

    if params.dry_run:
        print("This is dry-run. Exiting here.", file=log_out)
    else:
        if xac_files:
            out_prefix = os.path.splitext(os.path.basename(params.lstin))[0]
            ofs_cell = open(out_prefix+"_reindexed_cells.dat", "w")
            new_files = rb.modify_xds_ascii_files(cells_dat_out=ofs_cell)
            lstout = out_prefix + "_reindexed.lst"
            ofs = open(lstout, "w")
            ofs.write("\n".join(new_files)+"\n")
            ofs.close()
            print("Reindexing done. For merging, use %s instead!" % lstout, file=log_out)
        else:
            rb.modify_stream_files("reindexed.stream")
            
    if params.method == "brehm_diederichs":
        print("""
CCTBX-implementation (by Richard Gildea) of the "algorithm 2" of the following paper was used.
For publication, please cite:
 Brehm, W. and Diederichs, K. Breaking the indexing ambiguity in serial crystallography.
 Acta Cryst. (2014). D70, 101-109
 http://dx.doi.org/10.1107/S1399004713025431""", file=log_out)
    elif params.method == "selective_breeding":
        print("""
"Selective breeding" algorithm was used. For publication, please cite:
 Kabsch, W. Processing of X-ray snapshots from crystals in random orientations.
 Acta Cryst. (2014). D70, 2204-2216
 http://dx.doi.org/10.1107/S1399004714013534""", file=log_out)

# run()

def show_help():
    print("""
Use this command to resolve indexing ambiguity

Case 1) Reference-based (when you have isomorphous data)
  kamo.resolve_indexing_ambiguity formerge.lst method=reference reference_file=yourdata.mtz [d_min=3]

Case 2) Using selective-breeding algorithm (when you don't have reference data)
  kamo.resolve_indexing_ambiguity formerge.lst method=selective_breeding [d_min=3]

Case 3) Using Brehm & Diederichs algorithm (when you don't have reference data)
  kamo.resolve_indexing_ambiguity formerge.lst method=brehm_diederichs [d_min=3]

You can also give min_ios= to cutoff data by I/sigma(I).
""")
    iotbx.phil.parse(master_params_str).show(prefix="  ", attributes_level=1)
    print() 
# show_help()

if __name__ == "__main__":
    import sys

    if "-h" in sys.argv or "--help" in sys.argv:
        show_help()
        quit()
  
    cmdline = iotbx.phil.process_command_line(args=sys.argv[1:],
                                              master_string=master_params_str)
    params = cmdline.work.extract()
    args = cmdline.remaining_args

    for arg in args:
        if os.path.isfile(arg) and ".stream" in arg:
            params.streamin.append(arg)
        elif os.path.isfile(arg) and params.lstin is None:
            params.lstin = arg

    if not params.lstin and not params.streamin:
        show_help()
        print("Error: Give .lst of XDS_ASCII files or stream files")
        quit()

    if params.method is None:
        show_help()
        print("Error: Give method=")
        quit()

    if params.method == "reference" and params.reference_file is None:
        show_help()
        print("Error: Give reference_file= when you use params.method=reference")
        quit()

    if params.method == "brehm_diederichs" and params.reference_file is not None:
        show_help()
        print("Error: You can't give reference_file= when you use params.method=brehm_diederichs")
        quit()
        
    run(params)
