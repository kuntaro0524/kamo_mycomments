"""
Tests for the initial resolution estimate used by kamo.auto_multi_merge.
Run with the KAMO runtime python: python -m pytest yamtbx/dataproc/auto/tests
"""
from __future__ import division
from __future__ import print_function

import io
import numpy
from yamtbx.dataproc.auto import resolution_cutoff as rc


def shells(d_max, d_min, n):
    return numpy.linspace(1./d_max**2, 1./d_min**2, n)

def estimate(s2, cc, cc_half_min, fit_fallback="shells"):
    return rc.initial_estimate_from_shells(s2, cc, cc_half_min, io.StringIO(), fit_fallback)


def test_usable_fit_is_unchanged():
    s2 = shells(50., 1.5, 200)
    cc = rc.fun_ed_aimless(s2, 1./2.5**2, 0.03)
    d_min, (d0, r) = estimate(s2, cc, 0.5)
    assert abs(d_min - 2.5) < 0.02
    # identical to the expression before the fallback was added
    assert d_min == 1./numpy.sqrt(numpy.arctanh(1.-2.*0.5)*r + d0)

def test_resolution_fitted_rejects_non_positive_crossing():
    assert numpy.isnan(rc.resolution_fitted(-0.3, 0.001, 0.35))
    assert numpy.isnan(rc.resolution_fitted(float("nan"), float("nan"), 0.5))
    assert abs(rc.resolution_fitted(0.04, 0.02, 0.5) - 5.0) < 1e-9

def test_shell_estimate_stops_at_first_shell_below_threshold():
    s2 = [1/36., 1/25., 1/16., 1/9., 1/4.]
    cc = [0.99, 0.80, 0.40, 0.70, 0.05]
    assert abs(rc.resolution_by_shells(s2, cc, 0.5) - 5.0) < 1e-9
    assert abs(rc.resolution_by_shells(s2, cc, 0.35) - 3.0) < 1e-9

def test_shell_estimate_without_valid_shell():
    s2 = [1/36., 1/25., 1/16.]
    assert rc.resolution_by_shells(s2, [0.08, 0.28, 0.28], 0.35) is None
    assert rc.resolution_by_shells(s2, [float("nan"), 0.9, 0.9], 0.35) is None
    assert rc.resolution_by_shells([], [], 0.35) is None

def test_fit_works_for_clean_step():
    s2 = shells(50., 1.31, 200)
    cc = numpy.where(numpy.arange(200) < 10, 0.9, 0.0)
    d_min, (d0, r) = estimate(s2, cc, 0.35)
    assert numpy.isfinite(rc.resolution_fitted(d0, r, 0.35))
    assert 6.0 <= d_min < 6.2

def test_fallback_when_fit_is_not_usable():
    # Signal only in the lowest resolution shells of a wide range and a
    # non-zero noise floor elsewhere: the fitted curve becomes flat (d0 < 0).
    s2 = shells(50., 1.31, 200)
    cc = numpy.where(numpy.arange(200) < 10, 0.9, 0.1)
    d_min, (d0, r) = estimate(s2, cc, 0.35)
    assert d0 < 0
    assert numpy.isnan(rc.resolution_fitted(d0, r, 0.35))
    assert abs(d_min - 1./numpy.sqrt(s2[9])) < 1e-9
    # without the option, the estimate is not decided (as before, NaN)
    d_min, _ = estimate(s2, cc, 0.35, fit_fallback="none")
    assert numpy.isnan(d_min)

def test_no_estimate_when_all_shells_are_noise():
    s2 = shells(50., 1.65, 200)
    cc = numpy.full(200, 0.15)
    d_min, (d0, r) = estimate(s2, cc, 0.35)
    assert numpy.isnan(d_min)

def test_too_few_shells():
    d_min, _ = estimate([0.01, 0.02], [0.9, 0.8], 0.5)
    assert abs(d_min - 1./numpy.sqrt(0.02)) < 1e-9
    d_min, _ = estimate([0.01, 0.02], [0.1, 0.1], 0.5)
    assert numpy.isnan(d_min)

def test_phil_option_default_is_none():
    import iotbx.phil
    from yamtbx.dataproc.auto.command_line import auto_multi_merge
    params = iotbx.phil.parse(auto_multi_merge.gui_phil_str).extract()
    assert params.rescut.fit_fallback == "none"
    assert params.rescut.skip_no_signal is False
    params = iotbx.phil.parse(auto_multi_merge.gui_phil_str).fetch(iotbx.phil.parse("rescut.fit_fallback=shells")).extract()
    assert params.rescut.fit_fallback == "shells"


SUMMARY = """\
# d_min= 1.650 A
     cluster    ClH run Redun CC1/2 CC1/2.ou CC1/2.in
cluster_0050   1.74   1  18.2  13.8      4.6     77.8
cluster_0050   1.74   3   7.1   8.1      3.5     98.6
cluster_0049   1.00   2  11.0  13.8      1.2      9.0
cluster_0047   0.98   3   6.8  11.7      3.7     98.5
cluster_0046   0.84   3   6.5   9.7      2.5     98.4
cluster_0048   1.00   2   6.4   9.2      3.0      6.6
cluster_0043   0.59   3   4.7  13.4      3.6     98.5
cluster_0040   0.53   3   3.7  21.5      5.1     98.5
cluster_0039   0.48   3   2.9   5.3      4.8     98.1
"""

def write_summary(tmp_path, text=SUMMARY):
    f = tmp_path / "cluster_summary.dat"
    f.write_text(text)
    return str(f)

def test_choose_best_result_default_is_unchanged(tmp_path):
    from yamtbx.dataproc.auto.command_line.auto_multi_merge import choose_best_result
    best = choose_best_result(write_summary(tmp_path), io.StringIO())
    # top half by redundancy, then the highest overall CC1/2: a cluster without signal
    assert best.endswith("cluster_0049/run_02/xscale.hkl")

def test_choose_best_result_skips_results_without_inner_signal(tmp_path):
    from yamtbx.dataproc.auto.command_line.auto_multi_merge import choose_best_result
    best = choose_best_result(write_summary(tmp_path), io.StringIO(), min_cchalf_in=35.)
    assert best.endswith("cluster_0047/run_03/xscale.hkl")

def test_choose_best_result_none_when_no_result_has_inner_signal(tmp_path):
    from yamtbx.dataproc.auto.command_line.auto_multi_merge import choose_best_result
    assert choose_best_result(write_summary(tmp_path), io.StringIO(), min_cchalf_in=99.) is None

def test_choose_best_result_falls_back_to_the_rest_when_first_half_has_no_signal(tmp_path):
    from yamtbx.dataproc.auto.command_line.auto_multi_merge import choose_best_result
    text = """\
     cluster    ClH run Redun CC1/2 CC1/2.ou CC1/2.in
cluster_0003   1.00   2  11.0  13.8      1.2      9.0
cluster_0002   1.00   2  10.0   9.2      3.0      6.6
cluster_0001   0.50   3   3.0  11.7      3.7     98.5
cluster_0000   0.40   3   2.0  21.5      5.1     98.5
"""
    best = choose_best_result(write_summary(tmp_path, text), io.StringIO(), min_cchalf_in=35.)
    assert best.endswith("cluster_0000/run_03/xscale.hkl")
