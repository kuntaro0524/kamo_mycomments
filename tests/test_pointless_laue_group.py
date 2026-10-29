"""KAMO-007: a pointless answer of "Laue group" must not stop the XDS sequence.

pointless prints ``Best Solution: Laue group ...`` when it cannot decide the space
group (for example when the top candidates are the same group in different settings).
``parse_pointless_output_for_symm`` asserted ``point`` or ``space`` and raised
``AssertionError``, which ended ``xds_sequence`` before ``pointless_integrate.log`` was
written.  Every caller already treats a result without ``"symm"`` as "pointless failed".

The two data files are the real ``Best Solution`` blocks from pointless 1.x runs on
INTEGRATE.HKL of two datasets (Tosha, oxMIF_28: ``cry00_6001-6300`` and ``cry00_5101-5400``).
"""
import os

import pytest

from yamtbx.dataproc import pointless
from yamtbx import util

DATA = os.path.join(os.path.dirname(__file__), "data")


def read(name):
    with open(os.path.join(DATA, name)) as f:
        return f.read()


LAUE = read("pointless_best_laue_group.txt")
SPACE = read("pointless_best_space_group.txt")


def test_space_group_answer_is_parsed_as_before():
    ret = pointless.parse_pointless_output_for_symm(SPACE)
    assert str(ret["symm"].space_group_info()) == "P 62 2 2"
    assert ret["laue_prob"] == pytest.approx(0.210)
    assert "reindex_op" in ret


def test_laue_group_answer_does_not_raise_and_gives_no_symmetry():
    ret = pointless.parse_pointless_output_for_symm(LAUE)
    assert "symm" not in ret


def test_laue_group_answer_keeps_the_probability_for_the_log():
    ret = pointless.parse_pointless_output_for_symm(LAUE)
    assert ret["laue_prob"] == pytest.approx(0.217)


def test_unknown_group_word_is_also_not_fatal():
    ret = pointless.parse_pointless_output_for_symm(LAUE.replace("Laue group", "weird group"))
    assert "symm" not in ret


def test_run_for_symm_writes_the_log_and_returns_without_symm(tmp_path, monkeypatch):
    xds = tmp_path / "INTEGRATE.HKL"
    xds.write_text("dummy")
    monkeypatch.setattr(util, "call", lambda *a, **k: (0, LAUE, ""))
    log = tmp_path / "pointless_integrate.log"
    ret = pointless.Pointless().run_for_symm(xdsin=str(xds), logout=str(log))
    assert "symm" not in ret
    assert "Laue group C 1 2/m 1" in log.read_text()
