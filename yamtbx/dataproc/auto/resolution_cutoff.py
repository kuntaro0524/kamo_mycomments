"""
(c) RIKEN 2015-2017. All rights reserved. 
Author: Keitaro Yamashita

This software is released under the new BSD License; see LICENSE.
"""
from __future__ import division
from __future__ import print_function

import sys
from libtbx import slots_getstate_setstate
from iotbx import merging_statistics
from libtbx.utils import null_out
from libtbx import adopt_init_args
import numpy

def fun_ed_aimless(s, d0, r):
    # CC1/2 fitting equation used in Aimless, suggested by Ed Pozharski
    return 0.5 * (1 - numpy.tanh((s-d0)/r))
# fun_ed_aimless()

def resolution_fitted(d0, r, cchalf_min=0.5):
    return 1./numpy.sqrt((numpy.arctanh(1.-2.*cchalf_min)*r + d0))
# resolution_fitted()

def fit_curve_for_cchalf(s2_list, cc_list, log_out, verbose=True):
    import scipy.optimize

    def fun(x, s, cc):
        d0, r = x
        return fun_ed_aimless(s,d0,r) - cc
    # fun()

    if not isinstance(s2_list, numpy.ndarray): s2_list = numpy.array(s2_list)
    if not isinstance(cc_list, numpy.ndarray): cc_list = numpy.array(cc_list)

    # Remove NaN
    sel_notnan = (cc_list==cc_list)&(s2_list==s2_list)
    s2_list = s2_list[sel_notnan]
    cc_list = cc_list[sel_notnan]

    # Check size here!!
    if len(s2_list) < 3:
        log_out.write("  Error! number of elements too small (%d)\n" % len(s2_list))
        return float("nan"), float("nan")
    
    x0 = [0.5*min(s2_list), 1.] #Initial d0, r
    log_out.write("  Initial d0, r = %s\n" % x0)
    lsq = scipy.optimize.least_squares(fun, x0, args=(s2_list, cc_list), loss="soft_l1", f_scale=.3)
    #lsq = fit_ed(s_list, cc_list)

    if verbose:
        log_out.write("""  Least-square result:
      message: %s
         nfev: %s
         njev: %s
   optimality: %s
       status: %s
      success: %s
""" % (lsq.message, lsq.nfev, lsq.njev, lsq.optimality, lsq.status, lsq.success))

    d0, r = lsq.x
    log_out.write("  Final d0, r = %s\n" % lsq.x)
    return lsq.x
# fit_curve_for_cchalf()

def initial_estimate_byfit_cchalf(i_obs, cc_half_min, anomalous_flag, log_out):
    # Up to 200 bins. If few reflections, 50 reflections per bin. At least 9 shells.
    n_bins = max(min(int(i_obs.size()/50. + .5), 200), 9)
    log_out.write("Using %d bins for initial estimate\n" % n_bins)

    i_obs.setup_binner(n_bins=n_bins)
    bins = []

    s_list, cc_list = [], []
    for bin in i_obs.binner().range_used():
      unmerged = i_obs.select(i_obs.binner().selection(bin))
      try:
        bin_stats = merging_statistics.merging_stats(unmerged,
                                                     anomalous=anomalous_flag)
        s_list.append(1./bin_stats.d_min**2)
        cc_list.append(bin_stats.cc_one_half)
      except RuntimeError: # complains that no reflections left after sigma-filtering.
        continue

    d0, r = fit_curve_for_cchalf(s_list, cc_list, log_out)
    shells_and_fit = (s_list, cc_list, (d0, r))

    d_min = resolution_fitted(d0, r, cc_half_min)
    return d_min, shells_and_fit
# initial_estimate_byfit_cchalf()


class estimate_resolution_based_on_cc_half(object):
  def __init__(self, i_obs, cc_half_min, cc_half_tol, n_bins, anomalous_flag=False, log_out=null_out()):
    adopt_init_args(self, locals())
    log_out.write("estimate_resolution_based_on_cc_half: cc_half_min=%.4f, cc_half_tol=%.4f n_bins=%d\n" % (cc_half_min, cc_half_tol, n_bins))
    self.d_min_data = i_obs.d_min()
    self.shells_and_fit = ()
    self.d_min, self.cc_at_d_min = self.estimate_resolution()
  # __init__()

  def show_plot(self, show=True, filename=None):
    if not self.shells_and_fit: return

    import matplotlib
    matplotlib.use('Agg') # Allow to work without X
    import pylab
    from matplotlib.ticker import FuncFormatter

    s2_formatter = lambda x,pos: "inf" if x == 0 else "%.2f" % (1./numpy.sqrt(x))
    s_list, cc_list, (d0, r) = self.shells_and_fit
    fitted = fun_ed_aimless(s_list, d0, r)
    
    fig, ax1 = pylab.plt.subplots()

    pylab.plot(s_list, cc_list, label="CC1/2", marker="o", color="blue")
    pylab.plot(s_list, fitted, label="(1-tanh((s^2%+.2e)/%.2e))/2"%(-d0,r), marker=None, color="red")
    
    pylab.legend()
    pylab.xlabel("resolution (d^-2)")
    pylab.ylabel("CC1/2")
    pylab.gca().xaxis.set_major_formatter(FuncFormatter(s2_formatter))

    if filename: pylab.savefig(filename)
    if show: pylab.show()
  # show_plot()

  def cc_outer_shell(self, d_min):
    binner = self.i_obs.setup_binner(d_min=d_min, n_bins=self.n_bins)
    bin_stats = merging_statistics.merging_stats(self.i_obs.select(binner.selection(binner.range_used()[-1])), anomalous=False)
    return bin_stats.cc_one_half
  # cc_outer_shell()

  def estimate_resolution(self):
    if self.i_obs.size() == 0:
      self.log_out.write("No reflections.\n")
      return None, None

    d_min, self.shells_and_fit = initial_estimate_byfit_cchalf(self.i_obs, self.cc_half_min, self.anomalous_flag, self.log_out)
    d_min = float("%.2f"%d_min)
    
    if d_min < self.d_min_data:
      self.log_out.write("Warning: Initial estimate is higher than the limit of data (%.4f A < %.4f A)\n" %(d_min, self.d_min_data))
      d_min = self.d_min_data

    cc = self.cc_outer_shell(d_min)
    self.log_out.write("Initial estimate: %.4f A (CC1/2= %.4f)\n" %(d_min, cc))

    if cc >= self.cc_half_min and abs(cc - self.cc_half_min) < self.cc_half_tol:
      return d_min, cc

    if cc > self.cc_half_min + self.cc_half_tol:
      upper_bound = d_min
      lower_bound = d_min

      for i in range(1,300):
        if d_min-.01*i <= self.d_min_data: break
        lower_bound = d_min-.01*i
        cc = self.cc_outer_shell(lower_bound)
        self.log_out.write("  CC1/2= %.4f at %.4f A\n" %(cc, d_min-.01*i))
        if cc < self.cc_half_min:
          break
    else:
      lower_bound = d_min
      for i in range(1,300):
        upper_bound = d_min+.01*i
        cc = self.cc_outer_shell(upper_bound)
        self.log_out.write("  CC1/2= %.4f at %.4f A\n" %(cc, d_min+.1*i))
        if cc >= self.cc_half_min:
          break

    self.log_out.write("  Lower, Upper bound: %.4f, %.4f\n" %(lower_bound, upper_bound))

    lb, ub = lower_bound, upper_bound
    tmp_last = None

    while True:
      tmp = float("%.2f"%((lb+ub)/2.))
      if tmp_last is not None and tmp == tmp_last: return ub, cc
      tmp_last = tmp

      cc = self.cc_outer_shell(tmp)
      self.log_out.write("  CC1/2= %.4f at %.4f A\n" %(cc, tmp))

      if cc < self.cc_half_min:
        lb = tmp
      elif (cc - self.cc_half_min) > self.cc_half_tol:
        ub = tmp
      else:
        return tmp, cc
  # estimate_resolution_based_on_cc_half()    



class estimate_crude_resolution_cutoffs (slots_getstate_setstate) :
  # Original code from iotbx/merging_statistics.py
  """
  Uses incredibly simplistic criteria to determine the approximate
  resolution limit of the data based on the merging statistics (using much
  smaller bins than normal).  Not really appropriate for routine use, but
  useful for the pedantic and just-curious.
  """
  cutoffs_attr = ["i_over_sigma_cut", "r_merge_cut", "r_meas_cut",
    "completeness_cut_conservative", "completeness_cut_permissive",
    "cc_one_half_cut",]
  __slots__ = ["n_bins", "i_over_sigma_min", "r_merge_max", "r_meas_max",
    "completeness_min_conservative", "completeness_min_permissive",
    "cc_one_half_min", "d_min_overall",] + cutoffs_attr
  def __init__ (self,
      i_obs,
      crystal_symmetry=None,
      n_bins=None,
      i_over_sigma_min=2.0,
      r_merge_max=0.5,
      r_meas_max=0.5,
      completeness_min_conservative=0.9,
      completeness_min_permissive=0.5,
      cc_one_half_min=0.5) :
    self.n_bins = n_bins
    self.i_over_sigma_min = i_over_sigma_min
    self.r_merge_max = r_merge_max
    self.r_meas_max = r_meas_max
    self.completeness_min_conservative = completeness_min_conservative
    self.completeness_min_permissive = completeness_min_permissive
    self.cc_one_half_min = cc_one_half_min
    for attr in self.cutoffs_attr :
      setattr(self, attr, None)

    # Decide n_bins
    if n_bins is None:
        n_bins = min(200, int(i_obs.complete_set().indices().size()/500.+.5)) # not well tested.
        print("n_bins=",n_bins)

    i_obs.setup_binner(n_bins=n_bins)
    bins = []
    
    for bin in i_obs.binner().range_used():
      unmerged = i_obs.select(i_obs.binner().selection(bin))
      try:
        bin_stats = merging_statistics.merging_stats(unmerged,
                                                     anomalous=False)
        bins.append(bin_stats)
      except RuntimeError: # complains that no reflections left after sigma-filtering.
        continue

    self.d_min_overall = bins[-1].d_min
    d_min_last = float("inf")
    for bin in bins :
      if (self.i_over_sigma_cut is None) :
        if (bin.i_over_sigma_mean < self.i_over_sigma_min) :
          self.i_over_sigma_cut = d_min_last
      if (self.cc_one_half_cut is None) :
        if (bin.cc_one_half < self.cc_one_half_min) :
          self.cc_one_half_cut = d_min_last
      if (self.r_merge_cut is None) :
        if (bin.r_merge > self.r_merge_max) :
          self.r_merge_cut = d_min_last
      if (self.r_meas_cut is None) :
        if (bin.r_meas > self.r_meas_max) :
          self.r_meas_cut = d_min_last
      if (self.completeness_cut_conservative is None) :
        if (bin.completeness < completeness_min_conservative) :
          self.completeness_cut_conservative = d_min_last
      if (self.completeness_cut_permissive is None) :
        if (bin.completeness < completeness_min_permissive) :
          self.completeness_cut_permissive = d_min_last
      d_min_last = bin.d_min

  def show (self, out=sys.stdout, prefix="") :
    def format_d_min (value) :
      if (value is None) :
        return "(use all data)" #% self.d_min_overall
      return "%7.3f" % value
    print(prefix + "Crude resolution cutoff estimates:", file=out)
    print(prefix + "  resolution of all data          : %7.3f" % \
      self.d_min_overall, file=out)
    if (self.cc_one_half_min is not None) :
      print(prefix + "  based on CC(1/2) > %-6g       : %s" % \
        (self.cc_one_half_min, format_d_min(self.cc_one_half_cut)), file=out)
    if (self.i_over_sigma_min is not None) :
      print(prefix + "  based on mean(I/sigma) > %-6g : %s" % \
        (self.i_over_sigma_min, format_d_min(self.i_over_sigma_cut)), file=out)
    if (self.r_merge_max is not None) :
      print(prefix + "  based on R-merge < %-6g       : %s" % \
        (self.r_merge_max, format_d_min(self.r_merge_cut)), file=out)
    if (self.r_meas_max is not None) :
      print(prefix + "  based on R-meas < %-6g        : %s" % \
        (self.r_meas_max, format_d_min(self.r_meas_cut)), file=out)
    if (self.completeness_min_conservative is not None) :
      print(prefix + "  based on completeness > %-6g  : %s" % \
        (self.completeness_min_conservative,
         format_d_min(self.completeness_cut_conservative)), file=out)
    if (self.completeness_min_permissive is not None) :
      print(prefix + "  based on completeness > %-6g  : %s" % \
        (self.completeness_min_permissive,
         format_d_min(self.completeness_cut_permissive)), file=out)

