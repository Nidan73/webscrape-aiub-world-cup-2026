import threading
from dashboard.jobs import RefreshJob


def test_runs_to_done():
    ran = []
    job = RefreshJob(runner=lambda: ran.append(1))
    assert job.start() is True
    job._thread.join(timeout=2)
    assert ran == [1]
    assert job.status()["state"] == "done" and job.status()["error"] is None


def test_error_is_captured():
    def boom():
        raise RuntimeError("nope")
    job = RefreshJob(runner=boom)
    job.start()
    job._thread.join(timeout=2)
    st = job.status()
    assert st["state"] == "error" and "nope" in st["error"]


def test_single_flight():
    gate = threading.Event()
    job = RefreshJob(runner=lambda: gate.wait(2))
    assert job.start() is True
    assert job.start() is False          # already running
    assert job.status()["state"] == "running"
    gate.set()
    job._thread.join(timeout=2)
    assert job.status()["state"] == "done"
