"""
(c) RIKEN 2015. All rights reserved. 
Author: Keitaro Yamashita

This software is released under the new BSD License; see LICENSE.
"""
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from yamtbx.dataproc.xds.xds_ascii import XDS_ASCII
from yamtbx.util.xtal import format_unit_cell
from cctbx import crystal
from cctbx.crystal import reindex
from cctbx.array_family import flex
from cctbx import sgtbx
from libtbx.utils import null_out
from libtbx import easy_mp
from libtbx import adopt_init_args
from cctbx.merging import brehm_diederichs

import os
import copy
import multiprocessing
import time
import numpy
import json

def calc_cc(a1, a2):
    a1, a2 = a1.common_sets(a2, assert_is_similar_symmetry=False)
    corr = flex.linear_correlation(a1.data(), a2.data())

    if corr.is_well_defined():# and a1.size() > 20:
        return corr.coefficient()
    else:
        return float("nan")
# calc_cc()

class ReindexResolver:
    def __init__(self, xac_files=None, stream_files=None, space_group=None, d_min=3, min_ios=3, nproc=1, max_delta=5, log_out=null_out()):
        adopt_init_args(self, locals())
        assert xac_files or stream_files
        assert not (xac_files and stream_files)
        self.arrays = []
        self.best_operators = None
        self._representative_xs = None
        self.bad_files = []
    # __init__()

    def representative_crystal_symmetry(self): return self._representative_xs

    def read_xac_files(self, from_p1=False):
        op_to_p1 = None
        if from_p1:
            """
            This option is currently for multi_determine_symmetry.
            Do not use this for ambiguity resolution! op_to_p1 is not considered when writing new HKL files.
            """
            self.log_out.write("\nAveraging symmetry of all inputs..\n")
            cells = []
            sgs = []
            for f in self.xac_files:
                xac =  XDS_ASCII(f, read_data=False)
                cells.append(xac.symm.unit_cell().parameters())
                sgs.append(xac.symm.space_group().build_derived_reflection_intensity_group(True))
            print(set(map(lambda x: str(x.info()), sgs)))
            assert len(set(sgs)) < 2
            avg_symm = crystal.symmetry(list(numpy.median(cells, axis=0)), space_group=sgs[0])
            op_to_p1 = avg_symm.change_of_basis_op_to_niggli_cell()
            self.log_out.write("  Averaged symmetry: %s (%s)\n" % (format_unit_cell(avg_symm.unit_cell()), sgs[0].info()))
            self.log_out.write("  Operator to Niggli cell: %s\n" % op_to_p1.as_hkl())
            self.log_out.write("        Niggli cell: %s\n" % format_unit_cell(avg_symm.unit_cell().change_basis(op_to_p1)))

        print("\nReading", file=self.log_out)
        cells = []
        bad_files, good_files = [], []
        for i, f in enumerate(self.xac_files):
            print("%4d %s" % (i, f), file=self.log_out)
            xac = XDS_ASCII(f, i_only=True)
            self.log_out.write("     d_range: %6.2f - %5.2f" % xac.i_obs().resolution_range())
            self.log_out.write(" n_ref=%6d" % xac.i_obs().size())
            xac.remove_rejected()
            a = xac.i_obs().resolution_filter(d_min=self.d_min)
            if self.min_ios is not None: a = a.select(a.data()/a.sigmas()>=self.min_ios)
            self.log_out.write(" n_ref_filtered=%6d" % a.size())
            if from_p1:
                a = a.change_basis(op_to_p1).customized_copy(space_group_info=sgtbx.space_group_info("P1"))
            a = a.as_non_anomalous_array().merge_equivalents(use_internal_variance=False).array()
            self.log_out.write(" n_ref_merged=%6d\n" % a.size())
            if a.size() < 2:
                self.log_out.write("     !! WARNING !! number of reflections is dangerously small!!\n")
                bad_files.append(f)
            else:
                self.arrays.append(a)
                cells.append(a.unit_cell().parameters())
                good_files.append(f)

        if bad_files:
            self.xac_files = good_files
            self.bad_files = bad_files

        assert len(self.xac_files) == len(self.arrays) == len(cells)
            
        print("", file=self.log_out)

        self._representative_xs = crystal.symmetry(list(numpy.median(cells, axis=0)),
                                                   space_group_info=self.arrays[0].space_group_info())
    # read_xac_files()

    def read_stream_files(self, from_p1=False, space_group=None):
        from yamtbx.dataproc.crystfel.stream import stream_iterator
        op_to_p1 = None
        if from_p1:
            """
            This option is currently for multi_determine_symmetry.
            Do not use this for ambiguity resolution! op_to_p1 is not considered when writing new HKL files.
            """
            self.log_out.write("\nAveraging symmetry of all inputs..\n")
            cells = []
            sgs = []
            for f in self.stream_files:
                for chunk in stream_iterator(f, read_reflections=False):
                    if space_group is None:
                        symm = chunk.indexed_symmetry()
                    else:
                        symm = crystal.symmetry(chunk.cell, space_group, assert_is_compatible_unit_cell=False)
                        
                    cells.append(symm.unit_cell().parameters())
                    sgs.append(symm.space_group())
            assert len(set(sgs)) < 2
            avg_symm = crystal.symmetry(list(numpy.median(cells, axis=0)), space_group=sgs[0])
            op_to_p1 = avg_symm.change_of_basis_op_to_niggli_cell()
            self.log_out.write("  Averaged symmetry: %s (%s)\n" % (format_unit_cell(avg_symm.unit_cell()), sgs[0].info()))
            self.log_out.write("  Operator to Niggli cell: %s\n" % op_to_p1.as_hkl())
            self.log_out.write("        Niggli cell: %s\n" % format_unit_cell(avg_symm.unit_cell().change_basis(op_to_p1)))

        self.log_out.write("\nReading\n")
        cells = []
        bad_files, good_files = [], []
        self.stream_valid_idxes = []
        idx = 0
        for i, f in enumerate(self.stream_files):
            self.log_out.write("%4d %s\n" % (i, f))
            for j, chunk in enumerate(stream_iterator(f)):
                self.log_out.write(" %4d %s %s\n" % (j, chunk.filename, chunk.event))
                if space_group is None:
                    symm = chunk.indexed_symmetry()
                else:
                    symm = crystal.symmetry(chunk.cell, space_group, assert_is_compatible_unit_cell=False)

                i_obs = chunk.data_array(symm.space_group(), anomalous_flag=False)
                self.log_out.write("     d_range: %6.2f - %5.2f" % i_obs.resolution_range())
                self.log_out.write(" n_ref=%6d" % i_obs.size())

                a = i_obs.resolution_filter(d_min=self.d_min)
                if self.min_ios is not None: a = a.select(a.data()/a.sigmas()>=self.min_ios)
                self.log_out.write(" n_ref_filtered=%6d" % a.size())
                if from_p1:
                    a = a.change_basis(op_to_p1).customized_copy(space_group_info=sgtbx.space_group_info("P1"))
                a = a.as_non_anomalous_array().merge_equivalents(use_internal_variance=False).array()
                self.log_out.write(" n_ref_merged=%6d\n" % a.size())
                if a.size() < 2:
                    self.log_out.write("     !! WARNING !! number of reflections is dangerously small!!\n")
                    bad_files.append(f)
                else:
                    self.arrays.append(a)
                    cells.append(a.unit_cell().parameters())
                    good_files.append(f)
                    self.stream_valid_idxes.append(idx)
                idx += 1

        #if bad_files:
        #    self.xac_files = good_files
        #    self.bad_files = bad_files

        #assert len(self.xac_files) == len(self.arrays) == len(cells)
            
        self.log_out.write("\n")

        self._representative_xs = crystal.symmetry(list(numpy.median(cells, axis=0)),
                                                   space_group_info=self.arrays[0].space_group_info())
    # read_stream_files()

    def read_assigned_operators(self, json_in):
        obj = json.load(open(json_in))
        reidx_ops = [sgtbx.change_of_basis_op(x) for x in obj["operators"]]
        self.best_operators = [reidx_ops[x] for x in obj["assignments"]]
    # read_assigned_operators()

    def show_assign_summary(self, log_out=None):
        if not log_out: log_out = self.log_out
        if not self.best_operators:
            log_out.write("ERROR: Operators not assigned.\n")
            return

        unique_ops = set(self.best_operators)
        op_count = [(x, self.best_operators.count(x)) for x in unique_ops]
        op_count.sort(key=lambda x: x[1])
        log_out.write("Assigned operators:\n")
        for op, num in reversed(op_count):
            log_out.write("  %10s: %4d\n" % (op.as_hkl(), num))
        log_out.write("\n")
    # show_assign_summary()

    def find_reindex_ops(self):
        symm = self.representative_crystal_symmetry()
        cosets = reindex.reindexing_operators(symm, symm, max_delta=self.max_delta)
        reidx_ops = cosets.combined_cb_ops()
        return reidx_ops
    # find_reindex_ops()

    def modify_xds_ascii_files(self, suffix="_reidx", cells_dat_out=None):
        #ofs_lst = open("for_merge_new.lst", "w")
        if cells_dat_out: cells_dat_out.write("file a b c al be ga\n")

        new_files = []
        print("Writing reindexed files..", file=self.log_out)
        assert len(self.xac_files) == len(self.best_operators)
        for i, (f, op) in enumerate(zip(self.xac_files, self.best_operators)):
            xac = XDS_ASCII(f, read_data=False)
            if op.is_identity_op():
                new_files.append(f)
                if cells_dat_out:
                    cell = xac.symm.unit_cell().parameters()
                    cells_dat_out.write(f+" "+" ".join(["%7.3f"%x for x in cell])+"\n")

                continue

            newf = f.replace(".HKL", suffix+".HKL") if ".HKL" in f else os.path.splitext(f)[0]+suffix+".HKL"
            print("%4d %s" % (i, newf), file=self.log_out)

            cell_tr = xac.write_reindexed(op, newf, space_group=self.arrays[0].crystal_symmetry().space_group())
            #ofs_lst.write(newf+"\n")
            new_files.append(newf)

            if cells_dat_out:
                cells_dat_out.write(newf+" "+" ".join(["%7.3f"%x for x in cell_tr.parameters()])+"\n")

        return new_files
    # modify_xds_ascii_files()

    def modify_stream_files(self, output):
        from yamtbx.dataproc.crystfel.stream import stream_iterator, stream_header

        self.log_out.write("Writing reindexed stream..\n")
        assert len(self.stream_valid_idxes) == len(self.best_operators)
        ofs = open(output, "w")
        ofs.write(stream_header())
        best_ops = copy.copy(self.best_operators)
        idx = 0
        for f in self.stream_files:
            for chunk in stream_iterator(f):
                if idx in self.stream_valid_idxes:
                    op = best_ops.pop(0)
                    print(" %4d %s %s %s" % (idx, chunk.filename, chunk.event, op.as_hkl()))
                    chunk.change_basis(op)
                    ofs.write(chunk.make_lines())
                else:
                    print(" %4d %s %s skipped" % (idx, chunk.filename, chunk.event))
                idx += 1

        assert not best_ops
        ofs.close()
    # modify_stream_files()

    def debug_write_mtz(self):
        arrays = self.arrays
        
        merge_org = arrays[0].deep_copy()
        for a in arrays[1:]: merge_org = merge_org.concatenate(a, assert_is_similar_symmetry=False)
        merge_org = merge_org.merge_equivalents(use_internal_variance=False).array()
        merge_org.as_mtz_dataset(column_root_label="I").mtz_object().write(file_name="noreindex.mtz")

        merge_new = None
        for a, op in zip(arrays, self.best_operators):
            if not op.is_identity_op(): a = a.customized_copy(indices=op.apply(a.indices()))

            if merge_new is None: merge_new = a
            else: merge_new = merge_new.concatenate(a, assert_is_similar_symmetry=False)

        merge_new = merge_new.merge_equivalents(use_internal_variance=False).array()
        merge_new.as_mtz_dataset(column_root_label="I").mtz_object().write(file_name="reindexed.mtz")
    # debug_write_mtz()
# class ReindexResolver

def kabsch_selective_breeding_worker(args):
    ref, i, tmp, new_ops = args
    global kabsch_selective_breeding_worker_dict
    nproc = kabsch_selective_breeding_worker_dict["nproc"]
    arrays = kabsch_selective_breeding_worker_dict["arrays"]
    reindexed_arrays = kabsch_selective_breeding_worker_dict["reindexed_arrays"]
    reidx_ops = kabsch_selective_breeding_worker_dict["reidx_ops"]

    if ref==i: return None
    
    if nproc > 1:
        tmp2 = reindexed_arrays[new_ops[ref]][ref]
    else:                                
        if reidx_ops[new_ops[ref]].is_identity_op(): tmp2 = arrays[ref]
        else: tmp2 = arrays[ref].customized_copy(indices=reidx_ops[new_ops[ref]].apply(arrays[ref].indices())).map_to_asu()

    cc = calc_cc(tmp, tmp2)
    if cc==cc: return cc
    return None
# work_local()

class KabschSelectiveBreeding(ReindexResolver):
    """
    Reference: W. Kabsch "Processing of X-ray snapshots from crystals in random orientations" Acta Cryst. (2014). D70, 2204-2216
    http://dx.doi.org/10.1107/S1399004714013534
    If I understand correctly...
    """

    def __init__(self, xac_files=None, stream_files=None, space_group=None, d_min=3, min_ios=3, nproc=1, max_delta=5, from_p1=False, log_out=null_out()):
        ReindexResolver.__init__(self, xac_files, stream_files, space_group, d_min, min_ios, nproc, max_delta, log_out)
        self._final_cc_means = [] # list of [(op_index, cc_mean), ...]
        self._reidx_ops = []
        if xac_files:
            self.read_xac_files(from_p1=from_p1)
        else:
            self.read_stream_files(from_p1=from_p1, space_group=space_group)
        # __init__()

    def final_cc_means(self): return self._final_cc_means
    def reindex_operators(self): return self._reidx_ops

    def assign_operators(self, reidx_ops=None, max_cycle=100):
        arrays = self.arrays
        self.best_operators = None

        if reidx_ops is None: reidx_ops = self.find_reindex_ops()

        print("Reindex operators:", file=self.log_out)
        for i, op in enumerate(reidx_ops): print(" %2d: %s" % (i, op.as_hkl()), file=self.log_out)
        print("", file=self.log_out)

        reidx_ops.sort(key=lambda x: not x.is_identity_op()) # identity op to first
        self._reidx_ops = reidx_ops

        if self.nproc > 1:
            # consumes much memory.. (but no much benefits)
            reindexed_arrays = [arrays]
            for op in reidx_ops[1:]:
                reindexed_arrays.append([x.customized_copy(indices=op.apply(x.indices())).map_to_asu() for x in arrays])
        else:
            reindexed_arrays = None

        old_ops = [0 for x in range(len(arrays))]
        new_ops = [0 for x in range(len(arrays))]

        global kabsch_selective_breeding_worker_dict
        kabsch_selective_breeding_worker_dict = dict(nproc=self.nproc, arrays=arrays,
                                                     reindexed_arrays=reindexed_arrays,
                                                     reidx_ops=reidx_ops) # constants during cycles
        pool = multiprocessing.Pool(self.nproc)
        for ncycle in range(max_cycle):
            #new_ops = copy.copy(old_ops) # doesn't matter
            self._final_cc_means = []

            for i in range(len(arrays)):
                cc_means = []
                a = arrays[i]
                #ttt=time.time()
                for j, op in enumerate(reidx_ops):
                    cc_list = []
                    if self.nproc > 1:
                        tmp = reindexed_arrays[j][i]
                    else:
                        if op.is_identity_op(): tmp = a
                        else: tmp = a.customized_copy(indices=op.apply(a.indices())).map_to_asu()
                    
                    """
                    def work_local(ref): # XXX This function is very slow when nproc>1...
                        if ref==i: return None

                        if self.nproc > 1:
                            tmp2 = reindexed_arrays[new_ops[ref]][ref]
                        else:                                
                            if reidx_ops[new_ops[ref]].is_identity_op(): tmp2 = arrays[ref]
                            else: tmp2 = arrays[ref].customized_copy(indices=reidx_ops[new_ops[ref]].apply(arrays[ref].indices())).map_to_asu()

                        cc = calc_cc(tmp, tmp2)
                        if cc==cc: return cc
                        return None
                    # work_local()

                    cc_list = easy_mp.pool_map(fixed_func=work_local,
                                               args=range(len(arrays)),
                                               processes=self.nproc)
                    """
                    cc_list = pool.map(kabsch_selective_breeding_worker,
                                       ((k, i, tmp, new_ops) for k in range(len(arrays))))
                    cc_list = [x for x in cc_list if x is not None]

                    if len(cc_list) > 0:
                        cc_means.append((j, sum(cc_list)/len(cc_list)))
                        #print  >>self.log_out, "DEBUG:", i, j, cc_list, cc_means[-1]

                if cc_means:
                    max_el = max(cc_means, key=lambda x:x[1])
                    print("%3d %s" % (i, " ".join(["%s%d:% .4f" % ("*" if x[0]==max_el[0] else " ", x[0], x[1]) for x in cc_means])), file=self.log_out)
                    self._final_cc_means.append(cc_means)
                    #print "%.3f sec" % (time.time()-ttt)
                    new_ops[i] = max_el[0]
                else:
                    print("%3d %s Error! cannot calculate CC" % (i, " ".join([" %d:    nan" % x for x in range(len(reidx_ops))])), file=self.log_out)
                    # XXX append something to self._final_cc_means?

            print("In %4d cycle" % (ncycle+1), file=self.log_out)
            print("  old",old_ops, file=self.log_out)
            print("  new",new_ops, file=self.log_out)
            print("  number of different assignments:", len([x for x in zip(old_ops,new_ops) if x[0]!=x[1]]), file=self.log_out)
            print("", file=self.log_out)
            if old_ops==new_ops:
                self.best_operators = [reidx_ops[x] for x in new_ops]
                print("Selective breeding is finished in %d cycles" % (ncycle+1), file=self.log_out)
                return

            old_ops = copy.copy(new_ops)

        print("WARNING:: Selective breeding is not finished. max cycles reached.", file=self.log_out)
        self.best_operators = [reidx_ops[x] for x in new_ops] # better than nothing..
    # assign_operators()
# class KabschSelectiveBreeding

class ReferenceBased(ReindexResolver):
    def __init__(self, xac_files=None, stream_files=None, space_group=None, ref_array=None, d_min=3, min_ios=3,  nproc=1, max_delta=5, log_out=null_out()):
        ReindexResolver.__init__(self, xac_files, stream_files, space_group, d_min, min_ios, nproc, max_delta, log_out)
        assert ref_array
        if xac_files:
            self.read_xac_files()
        else:
            self.read_stream_files(space_group=space_group)

        self.ref_array = ref_array.resolution_filter(d_min=d_min).as_non_anomalous_array().merge_equivalents(use_internal_variance=False).array()
        
    # __init__()

    def assign_operators(self, reidx_ops=None):
        arrays = self.arrays
        self.best_operators = None

        if reidx_ops is None: reidx_ops = self.find_reindex_ops()

        print("Reindex operators:", [str(x.as_hkl()) for x in reidx_ops], file=self.log_out)
        print("", file=self.log_out)

        reidx_ops.sort(key=lambda x: not x.is_identity_op()) # identity op to first

        new_ops = [0 for x in range(len(arrays))]

        for i, a in enumerate(arrays):
            cc_list = []
            a = arrays[i]

            for j, op in enumerate(reidx_ops):
                if op.is_identity_op(): tmp = a
                else: tmp = a.customized_copy(indices=op.apply(a.indices())).map_to_asu()

                cc = calc_cc(tmp, self.ref_array)
                if cc==cc: cc_list.append((j,cc))

            if len(cc_list) == 0:
                self.log_out.write("%3d failed\n" % i)
            else:
                max_el = max(cc_list, key=lambda x:x[1])
                self.log_out.write("%3d %s\n" % (i, " ".join(map(lambda x: "%s%d:% .4f" % ("*" if x[0]==max_el[0] else " ", x[0], x[1]), cc_list))))
                new_ops[i] = max_el[0]

        print("  operator:", new_ops, file=self.log_out)
        print("  number of different assignments:", len([x for x in new_ops if x!=0]), file=self.log_out)
        print("", file=self.log_out)

        self.best_operators = [reidx_ops[x] for x in new_ops]
    # assign_operators()
# class ReferenceBased

class BrehmDiederichs(ReindexResolver):
    def __init__(self, xac_files=None, stream_files=None, space_group=None, d_min=3, min_ios=3, nproc=1, max_delta=5, log_out=null_out()):
        ReindexResolver.__init__(self, xac_files, stream_files, space_group, d_min, min_ios, nproc, max_delta, log_out)
        if xac_files:
            self.read_xac_files()
        else:
            self.read_stream_files(space_group=space_group)
    # __init__()

    def assign_operators(self, reidx_ops=None):
        arrays = self.arrays
        self.best_operators = None

        if reidx_ops is None: reidx_ops = self.find_reindex_ops()

        print("Reindex operators:", [str(x.as_hkl()) for x in reidx_ops], file=self.log_out)
        print("", file=self.log_out)

        reidx_ops.sort(key=lambda x: not x.is_identity_op()) # identity op to first

        data = None
        latt_id = flex.int([])

        for i, a in enumerate(arrays):
            if data is None: data = a
            else: data = data.concatenate(a, assert_is_similar_symmetry=False)

            latt_id.extend(flex.int(a.size(), i))

        latt_id = data.customized_copy(data=latt_id.as_double())
        result = brehm_diederichs.run(L=[data, latt_id], nproc=self.nproc, verbose=True)

        self.best_operators = [None for x in range(len(arrays))]
        for op in result:
            idxes = list(map(int, result[op]))
            print(" %s num=%3d idxes= %s" %(op, len(result[op]), idxes), file=self.log_out)
            for idx in idxes:
                self.best_operators[idx] = sgtbx.change_of_basis_op(op)
    # assign_operators()

# class BrehmDiederichs

if __name__ == "__main__":
    import sys
    lst = sys.argv[1]
    xac_files = [x.strip() for x in open(lst)]

    ksb = KabschSelectiveBreeding(xac_files, log_out=sys.stdout)

    
    if 1: # debug code
        from cctbx import sgtbx
        import random
        debug_op = sgtbx.change_of_basis_op("k,h,l")
        idxes = list(range(len(ksb.arrays)))
        random.shuffle(idxes)
        for i in idxes[:len(ksb.arrays)//2]:
            ksb.arrays[i] = ksb.arrays[i].customized_copy(indices=debug_op.apply(ksb.arrays[i].indices()))

        print("altered:", idxes)

    ksb.assign_operators([debug_op, sgtbx.change_of_basis_op("h,k,l")])
    print("right?:", [i for i, x in enumerate(ksb.best_operators) if not x.is_identity_op()])
    #ksb.debug_write_mtz()
    #ksb.modify_xds_ascii_files()

    quit()

    arrays = []
    for f in xac_files:
        print("Reading", f)
        xac = XDS_ASCII(f, i_only=True)
        xac.remove_rejected()
        a = xac.i_obs().resolution_filter(d_min=3)
        a = a.merge_equivalents(use_internal_variance=False).array()
        arrays.append(a)

    symm = arrays[0].crystal_symmetry()
    cosets = reindex.reindexing_operators(symm, symm)
    reidx_ops = cosets.combined_cb_ops()
    reidx_ops.sort(key=lambda x: not x.is_identity_op())
    print(" Possible reindex operators:", [str(x.as_hkl()) for x in reidx_ops])

    determined = set([0,])
    old_ops = [0 for x in range(len(arrays))]

    for ncycle in range(100):  # max cycle
        new_ops = [0 for x in range(len(arrays))]
        for i in range(len(arrays)):
            cc_list = []
            a = arrays[i]
            for j, op in enumerate(reidx_ops):
                tmp = a.customized_copy(indices=op.apply(a.indices())).map_to_asu()
                for ref in determined:
                    if ref==i: continue
                    tmp2 = arrays[ref].customized_copy(indices=reidx_ops[new_ops[ref]].apply(arrays[ref].indices())).map_to_asu()
                    cc = calc_cc(tmp, tmp2)
                    #print "%d reindex= %10s cc=.%4f" % (i, op.as_hkl(), cc)
                    if cc==cc:
                        #cc_list.setdefault(op, []).append(cc)
                        cc_list.append((j,cc))
            if len(cc_list) == 0: continue
            max_el = max(cc_list, key=lambda x:x[1])
            print(i, max_el, sum(map(lambda x:x[1], cc_list))/len(cc_list))
            new_ops[i] = max_el[0]
            #arrays[i] = a.customized_copy(indices=reidx_ops[max_el[0]].apply(a.indices())).map_to_asu()
            determined.add(i)

        print("In %4d cycle" % ncycle)
        print("old",old_ops)
        print("new",new_ops)
        print("eq?", old_ops==new_ops)
        print() 
        if old_ops==new_ops: break
        old_ops = new_ops

    # Junk
    merge_org = arrays[0].deep_copy()
    for a in arrays[1:]: merge_org = merge_org.concatenate(a, assert_is_similar_symmetry=False)
    merge_org = merge_org.merge_equivalents(use_internal_variance=False).array()
    merge_org.as_mtz_dataset(column_root_label="I").mtz_object().write(file_name="noreindex.mtz")

    merge_new = None
    for a, opi in zip(arrays, new_ops):
        a = a.customized_copy(indices=reidx_ops[opi].apply(a.indices()))
        if merge_new is None: merge_new = a
        else: merge_new = merge_new.concatenate(a, assert_is_similar_symmetry=False)

    merge_new = merge_new.merge_equivalents(use_internal_variance=False).array()
    merge_new.as_mtz_dataset(column_root_label="I").mtz_object().write(file_name="reindexed.mtz")
