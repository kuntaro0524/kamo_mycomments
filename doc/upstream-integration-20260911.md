# Upstream integration, 2026-09-11

Integrates upstream `b4b12bd979886e50a537e28ab78ad13050776205` with fork
`662864d474c87d67e351c3599e44a57debc86239` on `integration/upstream-20260911`.
The original fork is preserved at `archive/fork-before-upstream-20260911`.

The repositories have unrelated Git histories. The fork root matches upstream
`d619df5` except for comments/whitespace in cc_clustering.py. Integration used
that tree as a content comparison base, retained the full upstream tree, and
applied the fork changes in five files. Both histories are recorded as merge
parents; no history was rewritten. The initial `ours` merge was only used to
establish parents: its tree was replaced with the reviewed integration tree.

Preserved: Japanese comments, kuntest/list_in.py, optional large-wedge XSCALE
settings and their propagation from auto_multi_merge. The CC output precision
conflict uses upstream `%13.11f` instead of fork `%12.7f`. The clustering AST
matches upstream exactly. XSCALE options remain disabled by default.

## Validation on robo04

- DIALS 3.23.0, Python 3.11.11. Tests used `dials.python -B` with this checkout
  inserted first in sys.path. Existing shared installation was not reconfigured.
- multi_merge and auto_multi_merge import from this checkout successfully.
- multi_merge PHIL parses; huge_large_wedge_merge defaults to False.
- XscaleCycles constructed in temporary directories with the large-wedge option
  False and True. Correlation/correction-image suppression headers were absent
  and present respectively; fixed corrections were None and DECAY ABSORPTION.
  No XSCALE processing was launched by this check.
- Changed Python files parse except
  yamtbx/dataproc/crystfel/command_line/stats_stream_savememory.py:178,
  which has a Python 2-style raise statement in upstream itself. This file is
  unchanged relative to upstream and was not repaired in this integration.
- kamo_test_installation reported three failures: Rscript, XDSSTAT, ADXV.
  XDS, CCP4, DIALS, H5ToXds and Python library checks passed. These are preliminary
  dependency checks, not scientific validation. Its resource-location check
  still resolves the installed shared yamtbx via libtbx, so that check does not
  establish standalone installation of this checkout.
- git diff --cached --check against the old fork reports whitespace already
  present in upstream initlp.py and batchjob.py; upstream content was preserved.

Full installation output is tracked at
[operations/evidence/20260911-installation.txt](operations/evidence/20260911-installation.txt).
The original local copy is validation/installation.log. No real diffraction processing or
scientific baseline comparison was run. This commit is an integration candidate,
not a validated production baseline. Resolve dependency setup, install this
checkout in an isolated environment, then run the selected baseline dataset.

No GitHub push or production environment switch was performed.
