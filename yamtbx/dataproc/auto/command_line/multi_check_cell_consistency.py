"""
(c) RIKEN 2015. All rights reserved. 
Author: Keitaro Yamashita

This software is released under the new BSD License; see LICENSE.
"""
from __future__ import print_function
from __future__ import unicode_literals
import iotbx.phil
from cctbx import uctbx
from cctbx import sgtbx
from cctbx import crystal
from cctbx.crystal import reindex
from cctbx.uctbx.determine_unit_cell import NCDist
from cctbx.sgtbx import pointgroup_tools
from yamtbx.dataproc.xds.xparm import XPARM
from yamtbx.dataproc.xds.xds_ascii import XDS_ASCII
from yamtbx.dataproc import pointless
from yamtbx.dataproc.xds import correctlp
from yamtbx.dataproc.dials.command_line import run_dials_auto
from yamtbx import util
from yamtbx.util import xtal

import os
import sys
import networkx as nx
import numpy

master_params_str = """
topdir = None
 .type = path
xdsdir = None
 .type = path
 .multiple = true
 .help = Either topdir= or (multiple) xdsdir= should be specified.
tol_length = 0.1
 .type = float
 .help = relative_length_tolerance
tol_angle = 5
 .type = float
 .help = absolute_angle_tolerance in degree
do_pointless = False
 .type = bool
 .help = Run pointless for largest group data to determine symmetry
"""

class CellGraph(object):
    def __init__(self, tol_length=None, tol_angle=None):
        self.tol_length = tol_length if tol_length else 0.1
        self.tol_angle = tol_angle if tol_angle else 5

        self.G = nx.Graph()
        self.p1cells = {} # key->p1cell
        self.dirs = {} # key->xdsdir
        self.symms = {} # key->symms
        self.cbops = {} # (key1,key2) = cbop
    # __init__()

    def get_p1cell_and_symm(self, xdsdir):
        dials_hkl = os.path.join(xdsdir, "DIALS.HKL")
        xac_file = util.return_first_found_file(("XDS_ASCII.HKL", "XDS_ASCII.HKL.org",
                                                 "XDS_ASCII_fullres.HKL.org", "XDS_ASCII_fullres.HKL",
                                                 "XDS_ASCII.HKL_noscale.org", "XDS_ASCII.HKL_noscale"),
                                                wd=xdsdir)

        p1cell, xs = None, None

        if xac_file:
            correct_lp = util.return_first_found_file(("CORRECT.LP_noscale", "CORRECT.LP"), wd=xdsdir)
            if not correct_lp:
                print("CORRECT.LP not found in %s" % xdsdir)
                return None, None
            p1cell = correctlp.get_P1_cell(correct_lp, force_obtuse_angle=True)
            try:
                xac = XDS_ASCII(xac_file, read_data=False)
            except:
                print("Invalid XDS_ASCII format:", xac_file)
                return None, None
            xs = xac.symm

        elif os.path.isfile(dials_hkl): # DIALS
            xs = run_dials_auto.get_most_possible_symmetry(xdsdir)
            if xs is None:
                print("Cannot get crystal symmetry:", xdsdir)
                return None, None

            p1cell = list(xs.niggli_cell().unit_cell().parameters())
            # force obtuse angle
            tmp = [(x[0]+3,abs(90.-x[1])) for x in enumerate(p1cell[3:])] # Index and difference from 90 deg
            tmp.sort(key=lambda x: x[1], reverse=True)
            if p1cell[tmp[0][0]] < 90:
                tmp = [(x[0]+3,90.-x[1]) for x in enumerate(p1cell[3:])] # Index and 90-val.
                tmp.sort(key=lambda x: x[1], reverse=True)
                for i,v in tmp[:2]: p1cell[i] = 180.-p1cell[i]

            p1cell = uctbx.unit_cell(p1cell)
        
        return p1cell, xs

    # get_p1cell_and_symm()

    def add_proc_result(self, key, xdsdir):
        if key in self.G: return #G.remove_node(key)

        p1cell, symm = self.get_p1cell_and_symm(xdsdir)
        if None in (p1cell, symm): return

        self.p1cells[key] = p1cell
        self.dirs[key] = xdsdir
        self.symms[key] = symm

        connected_nodes = []

        for node in self.G.nodes():
            other_cell = self.p1cells[node]
            if other_cell.is_similar_to(p1cell, self.tol_length, self.tol_angle):
                connected_nodes.append(node)
            else:
                cosets = reindex.reindexing_operators(crystal.symmetry(other_cell, 1),
                                                      crystal.symmetry(p1cell, 1),
                                                      self.tol_length, self.tol_angle)
                if cosets.double_cosets is not None:
                    self.cbops[(node,key)] = cosets.combined_cb_ops()[0]
                    print(p1cell, other_cell, self.cbops[(node,key)], other_cell.change_basis(self.cbops[(node,key)]))
                    connected_nodes.append(node)

        # Add nodes and edges
        self.G.add_node(key)
        for node in connected_nodes:
            self.G.add_edge(node, key)

    # add_proc_result()

    def _transformed_cells(self, keys):
        cells = [self.p1cells[keys[0]].parameters()]
        for key in keys[1:]:
            cell = self.p1cells[key]
            if (keys[0], key) in self.cbops:
                cell = cell.change_basis(self.cbops[(keys[0], key)])
            elif (key, keys[0]) in self.cbops:
                cell = cell.change_basis(self.cbops[(key, keys[0])].inverse()) # correct??

            cells.append(cell.parameters())
        return cells
    # _transformed_cells()
    
    def _average_p1_cell(self, keys):
        cells = numpy.array(self._transformed_cells(keys))
        return [cells[:,i].mean() for i in range(6)]
    # _average_p1_cell()

    def group_xds_results(self, out, show_details=True):
        print("Making groups from %d results\n" % len(self.p1cells), file=out) # Show total and failed!!
        
        self.groups = [list(g) for g in nx.connected_components(self.G)]
        self.groups.sort(key=lambda x:-len(x))
        self.grouped_dirs = []
        self.reference_symmetries = []

        #details_str = "group file a b c al be ga\n"
        #ofs_debug = open("cell_debug.dat", "w")
        #ofs_debug.write("group xdsdir a b c al be ga\n")

        for i, keys in enumerate(self.groups):
            self.reference_symmetries.append([])
            avg_cell = uctbx.unit_cell(self._average_p1_cell(keys))
            print("[{:2d}] {} members:".format(i+1, len(keys)), file=out)
            print(" Averaged P1 Cell=", " ".join(["%.2f"%x for x in avg_cell.parameters()]), file=out)

            #from yamtbx.util.xtal import format_unit_cell
            #for xd, uc in zip(map(lambda k:self.dirs[k], keys), self._transformed_cells(keys)):
            #    ofs_debug.write("%3d %s %s\n" % (i, xd, format_unit_cell(uc)))
            
            #print >>out, " Members=", keys
            if show_details:
                # by explore_metric_symmetry
                sg_explorer = pointgroup_tools.space_group_graph_from_cell_and_sg(avg_cell,  sgtbx.space_group_info(b"P1").group(), max_delta=10)
                tmp = []
                for obj in list(sg_explorer.pg_graph.graph.node_objects.values()):
                    pg = obj.allowed_xtal_syms[0][0].space_group().build_derived_reflection_intensity_group(True).info()
                    cbop = obj.allowed_xtal_syms[0][1]
                    trans_cell = avg_cell.change_basis(cbop)

                    if pg.group() == sgtbx.space_group_info(b"I2").group():
                        print("Warning!! I2 cell was given.", file=out) # this should not happen..

                    # Transform to best cell
                    fbc = crystal.find_best_cell(crystal.symmetry(trans_cell, space_group_info=pg,
                                                                  assert_is_compatible_unit_cell=False),
                                                 best_monoclinic_beta=False) # If True, C2 may result in I2..
                    cbop = fbc.cb_op() * cbop
                    trans_cell = trans_cell.change_basis(fbc.cb_op())
                    #print "debug:: op-to-best-cell=", fbc.cb_op()

                    # If beta<90 in monoclinic system, force it to have beta>90
                    if pg.group().crystal_system() == "Monoclinic" and trans_cell.parameters()[4] < 90:
                        op = sgtbx.change_of_basis_op("-h,-k,l")
                        cbop = op * cbop
                        trans_cell = trans_cell.change_basis(op)

                    tmp.append([0, pg, trans_cell, cbop, pg.type().number()])

                # Calculate frequency
                for pgnum in set([x[-1] for x in tmp]):
                    sel = [x for x in range(len(tmp)) if tmp[x][-1]==pgnum]
                    pgg = tmp[sel[0]][1].group()

                    if len(sel) == 1:
                        freq = len([x for x in keys if self.symms[x].space_group().build_derived_reflection_intensity_group(True) == pgg])
                        tmp[sel[0]][0] = freq
                    else:
                        trans_cells = [numpy.array(tmp[x][2].parameters()) for x in sel]
                        
                        for key in keys:
                            if self.symms[key].space_group().build_derived_reflection_intensity_group(True) != pgg: continue
                            cell = numpy.array(self.symms[key].unit_cell().parameters())
                            celldiffs = [sum(abs(tc-cell)) for tc in trans_cells]
                            min_key = celldiffs.index(min(celldiffs))
                            tmp[sel[min_key]][0] += 1

                print(" Possible symmetries:", file=out)
                print("   freq symmetry     a      b      c     alpha  beta   gamma reindex", file=out)
                for freq, pg, trans_cell, cbop, pgnum in sorted(tmp, key=lambda x:x[-1]):
                    print("   %4d %-10s %s %s" % (freq, pg, " ".join(["%6.2f"%x for x in trans_cell.parameters()]), cbop), file=out)
                    self.reference_symmetries[i].append((pg, trans_cell, freq))
                print("", file=out)

            dirs = [self.dirs[x] for x in keys]
            self.grouped_dirs.append(dirs)
    # group_xds_results()

    def get_reference_symm(self, group_idx, rs_idx):
        # XXX should be able to specify space group with screws

        if group_idx >= len(self.reference_symmetries):
            return None
        if rs_idx >= len(self.reference_symmetries[group_idx]):
            return None

        pg, cell, freq = self.reference_symmetries[group_idx][rs_idx]

        return crystal.symmetry(cell,
                                space_group_info=pg,
                                assert_is_compatible_unit_cell=False)
    # get_reference_symm()

    def get_selectable_symms(self, group_idx):
        if group_idx >= len(self.reference_symmetries):
            return []

        return self.reference_symmetries[group_idx]
    # get_selectable_symms()


    def get_most_frequent_symmetry(self, group_idx):
        # Should call after self.group_xds_results()

        symms = [x for x in self.reference_symmetries[group_idx] if x[2]>0]
        symms.sort(key=lambda x: x[2], reverse=True)

        if len(symms) == 0: return None

        if len(symms) > 1 and symms[0][0].group() == sgtbx.space_group_info("P1").group():
            return crystal.symmetry(symms[1][1], space_group_info=symms[1][0],
                                    assert_is_compatible_unit_cell=False)
        else:
            return crystal.symmetry(symms[0][1], space_group_info=symms[0][0],
                                    assert_is_compatible_unit_cell=False)
        
    # get_most_frequent_symmetry()

    def get_symmetry_reference_matched(self, group_idx, ref_cs):
        ref_pg = ref_cs.space_group().build_derived_reflection_intensity_group(True)
        ref_cell = ref_cs.unit_cell()

        symms = [x for x in self.reference_symmetries[group_idx] if x[0].group()==ref_pg]
        if len(symms) == 0: return None

        if len(symms) > 1:
            # TODO if different too much?
            celldiffs = [s[1].bases_mean_square_difference(ref_cell) for s in symms]
            min_idx = celldiffs.index(min(celldiffs))
            return crystal.symmetry(symms[min_idx][1], space_group_info=symms[min_idx][0],
                                    assert_is_compatible_unit_cell=False)
        else:
            return crystal.symmetry(symms[0][1], space_group_info=symms[0][0],
                                    assert_is_compatible_unit_cell=False)

    # get_symmetry_reference_matched()

    def get_group_symmetry_reference_matched(self, ref_cs):
        ref_v6 = xtal.v6cell(ref_cs.niggli_cell().unit_cell())
        ncdists = []
        for i, keys in enumerate(self.groups):
            v6 = xtal.v6cell(uctbx.unit_cell(self._average_p1_cell(keys)).niggli_cell())
            ncdists.append(NCDist(v6, ref_v6))
            print("Group %d: NCDist to reference: %f" % (i+1, ncdists[-1]))

        return ncdists.index(min(ncdists))+1
    # get_group_symmetry_reference_matched()

    def is_all_included(self, keys):
        all_nodes = set(self.G.nodes())
        return all_nodes.issuperset(keys)
    # is_all_included()

    def get_subgraph(self, keys):
        copied_obj = CellGraph(self.tol_length, self.tol_angle)
        copied_obj.G = self.G.subgraph(keys)
        copied_obj.p1cells = dict((k, self.p1cells[k]) for k in keys)
        copied_obj.dirs = dict((k, self.dirs[k]) for k in keys)
        copied_obj.symms = dict((k, self.symms[k]) for k in keys)
        copied_obj.cbops = dict((k, self.cbops[k]) for k in self.cbops if k[0] in keys or k[1] in keys) # XXX may be slow
        return copied_obj
    # get_subgraph()
# class CellGraph

def run(params, out=sys.stdout):
    cm = CellGraph(tol_length=params.tol_length, tol_angle=params.tol_angle)

    if not params.xdsdir and params.topdir:
        params.xdsdir = [x[0] for x in [x for x in os.walk(params.topdir) if any([y.startswith("XDS_ASCII.HKL") for y in x[2]]) or "DIALS.HKL" in x[2]]]
        
    for i, xdsdir in enumerate(params.xdsdir):
        cm.add_proc_result(i, xdsdir)

    cm.group_xds_results(out)
    ret = cm.grouped_dirs

    if len(ret) == 0:
        return cm
    
    print(file=out)
    print("About the largest group:", file=out)
    for idx, wd in enumerate(ret[0]):
        xac_hkl = os.path.join(wd, "XDS_ASCII.HKL")
        correct_lp = os.path.join(wd, "CORRECT.LP")
        print("%.3d %s" % (idx, os.path.relpath(wd, params.topdir) if params.topdir is not None else wd), end=' ', file=out)
        if not os.path.isfile(xac_hkl):
            print("Unsuccessful", file=out)
            continue
        
        sg = XDS_ASCII(xac_hkl, read_data=False).symm.space_group_info()
        clp = correctlp.CorrectLp(correct_lp)
        if "all" in clp.table:
            cmpl = clp.table["all"]["cmpl"][-1]
        else:
            cmpl = float("nan")
        ISa = clp.a_b_ISa[-1]
        print("%10s ISa=%5.2f Cmpl=%5.1f " % (sg, ISa, cmpl), file=out)

    if params.do_pointless:
        worker = pointless.Pointless()
        files = [os.path.join(x, "INTEGRATE.HKL") for x in ret[0]]
        #print files
        files = [x for x in files if os.path.isfile(x)]
        
        print("\nRunning pointless for the largest member.", file=out)
        result = worker.run_for_symm(xdsin=files, 
                                     logout="pointless.log",
                                     tolerance=10, d_min=5)
        if "symm" in result:
            print(" pointless suggested", result["symm"].space_group_info(), file=out)


    if 0:
        import pylab
        pos = nx.spring_layout(G)
        #pos = nx.spectral_layout(G)
        #pos = nx.circular_layout(G)

        #nx.draw_networkx_nodes(G, pos, node_size = 100, nodelist=others, node_color = 'w')
        nx.draw_networkx_nodes(G, pos, node_size = 100, node_color = 'w')
        nx.draw_networkx_edges(G, pos, width = 1)
        nx.draw_networkx_labels(G, pos, font_size = 12, font_family = 'sans-serif', font_color = 'r')

        pylab.xticks([])
        pylab.yticks([])
        pylab.savefig("network.png")
        pylab.show()

    return cm
# run()

def run_from_args(argv):
    cmdline = iotbx.phil.process_command_line(args=argv,
                                              master_string=master_params_str)
    params = cmdline.work.extract()
    args = cmdline.remaining_args
    
    for arg in args:
        if os.path.isdir(arg) and params.topdir is None:
            params.topdir = arg

    if not params.xdsdir and params.topdir is None:
        params.topdir = os.getcwd()

    run(params)
# run_from_args()

if __name__ == "__main__":
    import sys
    run_from_args(sys.argv[1:])
