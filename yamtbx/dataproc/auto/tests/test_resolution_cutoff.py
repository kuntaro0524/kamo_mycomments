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

def estimate(s2, cc, cc_half_min):
    # Same steps as initial_estimate_byfit_cchalf() after the shell statistics.
    log = io.StringIO()
    d0, r = rc.fit_curve_for_cchalf(s2, cc, log, verbose=False)
    d_min = rc.resolution_fitted(d0, r, cc_half_min)
    if not numpy.isfinite(d_min):
        d_min = rc.resolution_by_shells(s2, cc, cc_half_min)
    return d_min, (d0, r)


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

def test_no_estimate_when_all_shells_are_noise():
    s2 = shells(50., 1.65, 200)
    cc = numpy.full(200, 0.15)
    d_min, (d0, r) = estimate(s2, cc, 0.35)
    assert d_min is None

def test_too_few_shells():
    d_min, _ = estimate([0.01, 0.02], [0.9, 0.8], 0.5)
    assert abs(d_min - 1./numpy.sqrt(0.02)) < 1e-9
    d_min, _ = estimate([0.01, 0.02], [0.1, 0.1], 0.5)
    assert d_min is None
