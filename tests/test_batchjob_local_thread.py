"""KAMO-005: the sh engine must not lose a job that ends while it is being checked.

``LocalThread.run`` used to call ``Popen.poll()`` twice per child: once to mark the
job FINISHED and once to drop it from the running list.  A child that ended between
the two calls was dropped without ever being marked FINISHED, so
``JobManager.wait_all`` waited forever.
"""
import importlib.util
import os
import threading
import time

import pytest

_PATH = os.path.join(os.path.dirname(__file__), "..", "yamtbx", "util", "batchjob.py")
_spec = importlib.util.spec_from_file_location("batchjob_under_test", _PATH)
batchjob = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(batchjob)


class FakeProcess:
    """poll() says "still running" for the first `running_polls` calls, then 0."""

    def __init__(self, running_polls):
        self.running_polls = running_polls
        self.calls = 0

    def poll(self):
        self.calls += 1
        return None if self.calls <= self.running_polls else 0

    def kill(self):
        pass


class FakeJob:
    def __init__(self):
        self.state = batchjob.STATE_RUNNING


def run_thread_for(thread, seconds):
    runner = threading.Thread(target=thread.run, daemon=True)
    runner.start()
    time.sleep(seconds)
    thread._stopevent.set()
    runner.join(5)
    assert not runner.is_alive()


@pytest.mark.parametrize("running_polls", [1, 2, 3])
def test_a_job_that_ends_between_two_checks_is_still_marked_finished(running_polls):
    thread = batchjob.LocalThread(num_jobs=1)
    job = FakeJob()
    thread.p_list = [(job, FakeProcess(running_polls))]
    run_thread_for(thread, 0.6)
    assert job.state == batchjob.STATE_FINISHED
    assert thread.p_list == []


def test_a_job_that_is_still_running_is_kept_and_not_marked_finished():
    thread = batchjob.LocalThread(num_jobs=1)
    job = FakeJob()
    thread.p_list = [(job, FakeProcess(running_polls=10**9))]
    run_thread_for(thread, 0.4)
    assert job.state == batchjob.STATE_FAILED  # stopped while running, as before
    assert len(thread.p_list) == 1


def test_wait_all_returns_when_every_job_ends_even_if_one_ends_between_checks():
    manager = batchjob.ExecLocal.__new__(batchjob.ExecLocal)
    batchjob.JobManager.__init__(manager)
    manager.num_jobs = 1
    manager._thread = batchjob.LocalThread(num_jobs=1)
    jobs = [FakeJob(), FakeJob()]
    manager._thread.p_list = [(jobs[0], FakeProcess(1)), (jobs[1], FakeProcess(2))]
    manager._thread.start()
    try:
        assert manager.wait_all(jobs, interval=0.1, timeout=5) is True
    finally:
        manager._thread._stopevent.set()


def test_real_short_jobs_all_finish(tmp_path):
    script = tmp_path / "job.sh"
    script.write_text("#!/bin/sh\ntrue\n")
    script.chmod(0o755)
    manager = batchjob.ExecLocal(max_parallel=4)
    jobs = []
    for _ in range(60):
        job = FakeJob()
        job.script_name, job.wdir = "job.sh", str(tmp_path)
        job.state = batchjob.STATE_WAITING
        manager.submit(job)
        jobs.append(job)
    try:
        assert manager.wait_all(jobs, interval=0.2, timeout=60) is True
    finally:
        manager._thread._stopevent.set()
