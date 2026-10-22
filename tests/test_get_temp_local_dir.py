"""Tests for yamtbx.util.get_temp_local_dir fallback when a temp dir cannot be created (KAMO-004)."""
import errno
import os
import sys
import tempfile
import unittest
from unittest import mock

from yamtbx import util

RAMDISK = "/dev/shm"


def _mkdtemp_failing_for(bad_dir, err):
    real = tempfile.mkdtemp

    def fake(prefix=None, dir=None, **kw):
        if dir == bad_dir:
            raise OSError(err, os.strerror(err), os.path.join(dir, "%sXXXX" % prefix))
        return real(prefix=prefix, dir=dir, **kw)
    return fake


class GetTempLocalDirTest(unittest.TestCase):
    def setUp(self):
        self.fallback = tempfile.mkdtemp(prefix="kamo004fb")
        patches = [
            mock.patch("os.path.isdir", lambda p: True if p == RAMDISK else os.path.exists(p)),
            mock.patch.object(util, "check_disk_free_bytes", lambda d: 10**12),
            mock.patch("tempfile.gettempdir", lambda: self.fallback),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(lambda: os.path.isdir(self.fallback) and __import__("shutil").rmtree(self.fallback, True))
        self.created = []

    def _call(self, mkdtemp, **kw):
        err = tempfile.TemporaryFile("w+")
        with mock.patch("tempfile.mkdtemp", mkdtemp), mock.patch.object(sys, "stderr", err):
            try:
                r = util.get_temp_local_dir("xdstest", **kw)
            finally:
                err.seek(0)
                self.stderr = err.read()
        if r:
            self.created.append(r)
            self.addCleanup(lambda d=r: __import__("shutil").rmtree(d, True))
        return r

    def test_normal_uses_ramdisk_without_warning(self):
        real = tempfile.mkdtemp
        # emulate a working /dev/shm by redirecting it into a scratch dir but reporting the RAMDISK path
        seen = []
        def spy(prefix=None, dir=None, **kw):
            seen.append(dir)
            return real(prefix=prefix, dir=self.fallback, **kw)
        r = self._call(spy)
        self.assertEqual(seen, [RAMDISK])
        self.assertTrue(os.path.isdir(r))
        self.assertEqual(self.stderr, "")

    def _check_fallback(self, err):
        r = self._call(_mkdtemp_failing_for(RAMDISK, err))
        self.assertIsNotNone(r)
        self.assertEqual(os.path.dirname(r), self.fallback)
        self.assertIn("WARNING", self.stderr)
        self.assertIn(RAMDISK, self.stderr)

    def test_fallback_when_missing_enoent(self):
        self._check_fallback(errno.ENOENT)

    def test_fallback_when_permission_denied(self):
        self._check_fallback(errno.EACCES)

    def test_fallback_when_no_space(self):
        self._check_fallback(errno.ENOSPC)

    def test_all_candidates_failing_raises(self):
        def always_fail(prefix=None, dir=None, **kw):
            raise OSError(errno.ENOENT, "No such file or directory", dir)
        with self.assertRaises(OSError):
            self._call(always_fail)

    def test_no_ramdisk_goes_to_next_without_warning(self):
        real = tempfile.mkdtemp
        with mock.patch("os.path.isdir", lambda p: False if p == RAMDISK else os.path.exists(p)):
            r = self._call(real)
        self.assertEqual(os.path.dirname(r), self.fallback)
        self.assertEqual(self.stderr, "")

    def test_returns_none_when_no_candidate_has_enough_space(self):
        with mock.patch.object(util, "check_disk_free_bytes", lambda d: 0):
            r = self._call(tempfile.mkdtemp, min_gb=1)
        self.assertIsNone(r)


if __name__ == "__main__":
    unittest.main()
